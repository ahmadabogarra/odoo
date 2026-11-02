from __future__ import annotations

import hashlib
import threading
import time
from collections import deque

from odoo.addons.web.controllers.home import Home
from odoo.http import request, route


_WINDOW_SECONDS = 15 * 60
_LOCKOUT_SECONDS = 15 * 60
_MAX_FAILURES = 10
_MAX_BUCKETS = 4096

# Odoo currently runs as one Railway replica with the threaded server. Keep the
# limiter process-local and bounded so failed credentials are never persisted in
# tenant databases. If the deployment is scaled to multiple Odoo replicas this
# should be replaced by a shared limiter (for example Redis) before scaling.
_failures: dict[bytes, deque[float]] = {}
_locked_until: dict[bytes, float] = {}
_state_lock = threading.Lock()


def _source_bucket() -> bytes:
    """Key failures by tenant database and effective client address.

    Railway terminates TLS and Odoo runs with --proxy-mode, so Werkzeug's
    remote_addr is the proxy-normalized client address. Including the selected
    database prevents one tenant's mistakes from consuming another tenant's
    budget when both happen to originate behind the same NAT.
    """
    database = str(request.db or request.params.get("db") or "").strip().lower()
    remote_addr = str(request.httprequest.remote_addr or "unknown").strip().lower()
    material = f"{database}\x00{remote_addr}".encode("utf-8", "ignore")[:1024]
    return hashlib.blake2b(material, digest_size=16).digest()


def _prune_bucket(bucket: bytes, now: float) -> None:
    locked_until = _locked_until.get(bucket, 0.0)
    if locked_until and locked_until <= now:
        _locked_until.pop(bucket, None)

    failures = _failures.get(bucket)
    if failures is not None:
        cutoff = now - _WINDOW_SECONDS
        while failures and failures[0] <= cutoff:
            failures.popleft()
        if not failures:
            _failures.pop(bucket, None)


def _prune_global_state(now: float) -> None:
    # Remove expired locks first. Failure buckets are lazily pruned when they are
    # reused. The hard cap prevents source-address churn from growing memory
    # without bound.
    for bucket, deadline in list(_locked_until.items()):
        if deadline <= now:
            _locked_until.pop(bucket, None)
    if len(_failures) <= _MAX_BUCKETS:
        return

    ordered = sorted(
        _failures.items(),
        key=lambda item: item[1][-1] if item[1] else 0.0,
    )
    for bucket, _ in ordered[: len(_failures) - _MAX_BUCKETS]:
        _failures.pop(bucket, None)
        _locked_until.pop(bucket, None)


def _retry_after(bucket: bytes, now: float) -> int:
    _prune_bucket(bucket, now)
    deadline = _locked_until.get(bucket, 0.0)
    if deadline <= now:
        return 0
    return max(1, int(deadline - now + 0.999))


def _record_failure(bucket: bytes, now: float) -> int:
    _prune_bucket(bucket, now)
    failures = _failures.setdefault(bucket, deque())
    failures.append(now)
    if len(failures) < _MAX_FAILURES:
        _prune_global_state(now)
        return 0

    _failures.pop(bucket, None)
    _locked_until[bucket] = now + _LOCKOUT_SECONDS
    _prune_global_state(now)
    return _LOCKOUT_SECONDS


def _clear_failures(bucket: bytes) -> None:
    _failures.pop(bucket, None)
    _locked_until.pop(bucket, None)


def _rate_limited_response(retry_after: int):
    return request.make_response(
        "Too many login attempts. Try again later.",
        headers=[
            ("Content-Type", "text/plain; charset=utf-8"),
            ("Cache-Control", "no-store"),
            ("Retry-After", str(max(1, retry_after))),
        ],
        status=429,
    )


class ChargeXLoginGuard(Home):
    @route()
    def web_login(self, redirect=None, **kw):
        if request.httprequest.method != "POST":
            return super().web_login(redirect=redirect, **kw)

        bucket = _source_bucket()
        now = time.monotonic()
        with _state_lock:
            retry_after = _retry_after(bucket, now)
        if retry_after:
            return _rate_limited_response(retry_after)

        response = super().web_login(redirect=redirect, **kw)

        with _state_lock:
            if request.params.get("login_success"):
                _clear_failures(bucket)
                return response
            retry_after = _record_failure(bucket, time.monotonic())

        if retry_after:
            return _rate_limited_response(retry_after)
        return response
