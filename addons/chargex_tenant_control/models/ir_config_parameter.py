from __future__ import annotations

from odoo import api, models, _
from odoo.exceptions import AccessError


PROTECTED_SUBSCRIPTION_PREFIX = "chargex.subscription."


class IrConfigParameter(models.Model):
    _inherit = "ir.config_parameter"

    def _chargex_check_protected_subscription_keys(self, keys) -> None:
        protected = {
            str(key)
            for key in keys
            if key and str(key).startswith(PROTECTED_SUBSCRIPTION_PREFIX)
        }
        if not protected:
            return
        if self.env.su or self.env.uid == self.env.ref("base.user_admin").id:
            return
        raise AccessError(
            _(
                "ChargeX subscription parameters are managed by the ChargeX control plane and cannot be modified by tenant users."
            )
        )

    @api.model_create_multi
    def create(self, vals_list):
        self._chargex_check_protected_subscription_keys(
            vals.get("key") for vals in vals_list
        )
        return super().create(vals_list)

    def write(self, vals):
        keys = set(self.mapped("key"))
        if "key" in vals:
            keys.add(vals.get("key"))
        self._chargex_check_protected_subscription_keys(keys)
        return super().write(vals)

    def unlink(self):
        self._chargex_check_protected_subscription_keys(self.mapped("key"))
        return super().unlink()
