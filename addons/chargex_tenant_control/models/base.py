from __future__ import annotations

from odoo import api, models, _
from odoo.exceptions import UserError


READ_ONLY_STATUSES = {"suspended", "archived"}
TECHNICAL_WRITE_MODELS = {
    "ir.config_parameter",
    "res.users.log",
    "bus.bus",
    "bus.presence",
    "ir.sessions",
}


class Base(models.AbstractModel):
    _inherit = "base"

    def _chargex_check_subscription_write(self):
        if self.env.su or self.env.context.get("chargex_tenant_control_bypass"):
            return
        if self._name in TECHNICAL_WRITE_MODELS or self._name.startswith("bus."):
            return
        params = self.env["ir.config_parameter"].sudo()
        status = params.get_param("chargex.subscription.status", "active")
        if status in READ_ONLY_STATUSES:
            message = params.get_param(
                "chargex.subscription.message",
                _("The subscription is suspended. This database is currently read-only."),
            )
            raise UserError(message)

    @api.model_create_multi
    def create(self, vals_list):
        self._chargex_check_subscription_write()
        return super().create(vals_list)

    def write(self, vals):
        self._chargex_check_subscription_write()
        return super().write(vals)

    def unlink(self):
        self._chargex_check_subscription_write()
        return super().unlink()

    @api.model
    def search_fetch(self, domain, field_names, offset=0, limit=None, order=None):
        records = super().search_fetch(domain, field_names, offset, limit, order)
        if self._name == "ir.module.module" and "to_buy" in self._fields:
            records = records.filtered(lambda rec: not rec.to_buy)
        elif self._name == "payment.provider" and "module_to_buy" in self._fields:
            records = records.filtered(lambda rec: not rec.module_to_buy)
        return records
