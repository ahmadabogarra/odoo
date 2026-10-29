from __future__ import annotations

from odoo.http import Controller, request, route


PARAM_PREFIX = "chargex.subscription."


class ChargeXTenantControl(Controller):
    @route("/chargex/tenant/status", type="jsonrpc", auth="user")
    def status(self):
        params = request.env["ir.config_parameter"].sudo()
        return {
            key: params.get_str(PARAM_PREFIX + key, "")
            for key in (
                "status",
                "stage",
                "message",
                "subscription_end",
                "grace_end",
                "archived_at",
                "deletion_eligible_at",
            )
        }
