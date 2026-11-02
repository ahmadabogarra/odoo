from __future__ import annotations

import os
import secrets

from werkzeug.exceptions import NotFound

from odoo.http import request, route
from odoo.addons.web.controllers.database import Database


_PRIVATE_DOMAIN_ENV = "RAILWAY_PRIVATE_DOMAIN"


def _is_private_railway_request() -> bool:
    """Allow database-management routes only over Railway private DNS.

    Tenant Management talks to Odoo through ``odoo.railway.internal``. Public
    browser traffic arrives on the Railway public domain and must never expose
    database enumeration or database-management operations.
    """
    expected = str(os.getenv(_PRIVATE_DOMAIN_ENV, "") or "").strip().lower().rstrip(".")
    if not expected:
        return False

    host = str(request.httprequest.host or "").strip().lower()
    # Railway private hostnames are DNS names, not IPv6 literals. Strip only a
    # normal :port suffix and normalize a trailing dot before comparison.
    if ":" in host:
        host = host.split(":", 1)[0]
    host = host.rstrip(".")
    return bool(host) and secrets.compare_digest(host, expected)


def _require_private_railway_request() -> None:
    if not _is_private_railway_request():
        # Return 404 rather than advertising that a privileged control-plane
        # endpoint exists on the public Odoo hostname.
        raise NotFound()


class ChargeXDatabaseGuard(Database):
    @route()
    def selector(self, **kw):
        _require_private_railway_request()
        return super().selector(**kw)

    @route()
    def manager(self, **kw):
        _require_private_railway_request()
        return super().manager(**kw)

    @route()
    def create(self, master_pwd, name, lang, password, **post):
        _require_private_railway_request()
        return super().create(master_pwd, name, lang, password, **post)

    @route()
    def duplicate(self, master_pwd, name, new_name, neutralize_database=False):
        _require_private_railway_request()
        return super().duplicate(master_pwd, name, new_name, neutralize_database)

    @route()
    def drop(self, master_pwd, name):
        _require_private_railway_request()
        return super().drop(master_pwd, name)

    @route()
    def rename(self, master_pwd, name, new_name):
        _require_private_railway_request()
        return super().rename(master_pwd, name, new_name)

    @route()
    def backup(self, master_pwd, name, backup_format="zip", filestore=True):
        _require_private_railway_request()
        return super().backup(master_pwd, name, backup_format, filestore)

    @route()
    def restore(self, master_pwd, backup_file, name, copy=False, neutralize_database=False):
        _require_private_railway_request()
        return super().restore(master_pwd, backup_file, name, copy, neutralize_database)

    @route()
    def change_password(self, master_pwd, master_pwd_new):
        _require_private_railway_request()
        return super().change_password(master_pwd, master_pwd_new)

    @route()
    def list(self):
        _require_private_railway_request()
        return super().list()
