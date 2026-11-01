from odoo import fields, models


class MrpProduction(models.Model):
    _inherit = "mrp.production"

    chargex_pos_order_line_id = fields.Many2one(
        "pos.order.line",
        string="ChargeX POS Order Line",
        copy=False,
        readonly=True,
        index=True,
        ondelete="restrict",
    )

    _chargex_pos_order_line_unique = models.Constraint(
        "UNIQUE (chargex_pos_order_line_id)",
        "A ChargeX POS order line can only be linked to one manufacturing order.",
    )


class PosOrderLine(models.Model):
    _inherit = "pos.order.line"

    chargex_production_ids = fields.One2many(
        "mrp.production",
        "chargex_pos_order_line_id",
        string="ChargeX Manufacturing Orders",
        readonly=True,
    )
