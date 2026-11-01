from odoo import _, models
from odoo.exceptions import UserError
from odoo.tools import float_compare


CHARGEX_PRODUCT_PREFIX = "CHARGEX:"
CHARGEX_BOM_PREFIX = "CHARGEX-BOM:"


class PosOrder(models.Model):
    _inherit = "pos.order"

    def _chargex_managed_manufacture_bom(self, line):
        product = line.product_id
        default_code = product.default_code or ""
        if not default_code.startswith(CHARGEX_PRODUCT_PREFIX):
            return self.env["mrp.bom"]

        suffix = default_code[len(CHARGEX_PRODUCT_PREFIX):]
        if not suffix:
            return self.env["mrp.bom"]

        boms = self.env["mrp.bom"].sudo().search([
            ("code", "=", f"{CHARGEX_BOM_PREFIX}{suffix}"),
            ("active", "=", True),
            ("type", "=", "normal"),
            ("product_tmpl_id", "=", product.product_tmpl_id.id),
            "|", ("product_id", "=", False), ("product_id", "=", product.id),
            "|", ("company_id", "=", False), ("company_id", "=", self.company_id.id),
        ], limit=2)
        if len(boms) > 1:
            raise UserError(_(
                "ChargeX found more than one managed manufacturing BoM for product %(product)s.",
                product=product.display_name,
            ))
        return boms

    def _chargex_complete_production(self, line, bom):
        Production = self.env["mrp.production"].sudo().with_company(self.company_id)
        production = Production.search([
            ("chargex_pos_order_line_id", "=", line.id),
        ], limit=2)
        if len(production) > 1:
            raise UserError(_(
                "ChargeX found duplicate manufacturing orders for POS line %(line)s.",
                line=line.id,
            ))

        if production:
            if production.state == "done":
                return production
            if (
                production.product_id != line.product_id
                or production.bom_id != bom
                or float_compare(
                    production.product_qty,
                    line.qty,
                    precision_rounding=line.product_id.uom_id.rounding,
                ) != 0
            ):
                raise UserError(_(
                    "Existing ChargeX manufacturing order %(mo)s does not match POS line %(line)s.",
                    mo=production.display_name,
                    line=line.id,
                ))
            if production.state not in ("draft", "confirmed"):
                raise UserError(_(
                    "ChargeX manufacturing order %(mo)s is in state %(state)s and cannot be resumed automatically.",
                    mo=production.display_name,
                    state=production.state,
                ))
        else:
            vals = {
                "product_id": line.product_id.id,
                "product_qty": line.qty,
                "product_uom_id": line.product_id.uom_id.id,
                "bom_id": bom.id,
                "company_id": self.company_id.id,
                "origin": f"{self.name} / POS line {line.id}",
                "chargex_pos_order_line_id": line.id,
            }
            picking_type = self.config_id.picking_type_id
            warehouse = picking_type.warehouse_id if picking_type else self.env["stock.warehouse"]
            if warehouse and warehouse.manu_type_id:
                vals["picking_type_id"] = warehouse.manu_type_id.id
                vals["location_src_id"] = warehouse.lot_stock_id.id
                vals["location_dest_id"] = warehouse.lot_stock_id.id
            production = Production.create(vals)

        if production.state == "draft":
            production.action_confirm()
        if production.state != "confirmed":
            raise UserError(_(
                "ChargeX manufacturing order %(mo)s did not reach the confirmed state.",
                mo=production.display_name,
            ))

        production.qty_producing = line.qty
        production.button_mark_done()
        if production.state != "done":
            raise UserError(_(
                "ChargeX manufacturing order %(mo)s was not completed automatically.",
                mo=production.display_name,
            ))
        return production

    def _chargex_create_manufacturing_orders(self):
        for order in self:
            if order.state not in ("paid", "done") or order.is_refund:
                continue
            for line in order.lines:
                if line.qty <= 0 or line.refunded_orderline_id:
                    continue
                bom = order._chargex_managed_manufacture_bom(line)
                if not bom:
                    continue
                if not line.product_id.is_storable:
                    raise UserError(_(
                        "ChargeX managed manufacture product %(product)s must track inventory before it can be sold in POS.",
                        product=line.product_id.display_name,
                    ))
                order._chargex_complete_production(line, bom)

    def _set_product_qty_available(self):
        # point_of_sale calls this after action_pos_order_paid(); pos_stock's
        # implementation creates the outgoing POS picking. Complete ChargeX
        # manufacturing first so the finished goods exist before that picking.
        self._chargex_create_manufacturing_orders()
        return super()._set_product_qty_available()
