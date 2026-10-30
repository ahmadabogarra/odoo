from __future__ import annotations

from odoo import api, models, _
from odoo.exceptions import AccessError, UserError


class ChargeXTenantAccountingSetup(models.AbstractModel):
    _name = "chargex.tenant.accounting.setup"
    _description = "ChargeX Tenant Accounting Setup"

    @api.model
    def load_lebanon_chart(self):
        """Load Odoo's official Lebanon accounting template for this tenant.

        This is intentionally a narrow RPC bridge. The actual chart creation is
        still performed entirely by Odoo's standard account.chart.template
        loader; this wrapper only returns a non-None value so it can be called
        through Odoo's external RPC layer.
        """
        if not self.env.user.has_group("base.group_system"):
            raise AccessError(_("Only an Odoo administrator can prepare tenant accounting."))

        company = self.env.company
        if not company:
            raise UserError(_("No active company is available."))
        if not company.country_id or company.country_id.code != "LB":
            raise UserError(_("The active company must be in Lebanon before loading the Lebanon chart."))

        if company.chart_template:
            if company.chart_template != "lb":
                raise UserError(
                    _("A different accounting chart is already installed; ChargeX will not replace it.")
                )
        else:
            self.env["account.chart.template"].try_loading(
                "lb",
                company,
                install_demo=False,
                force_create=True,
            )
            company.invalidate_recordset(["chart_template", "account_fiscal_country_id"])

        if company.chart_template != "lb":
            raise UserError(_("The Lebanon accounting chart did not finish loading."))
        if not company.account_fiscal_country_id or company.account_fiscal_country_id.code != "LB":
            raise UserError(_("The fiscal country is not Lebanon after chart loading."))

        return {
            "ok": True,
            "company_id": company.id,
            "chart_template": company.chart_template,
            "fiscal_country_code": company.account_fiscal_country_id.code,
        }
