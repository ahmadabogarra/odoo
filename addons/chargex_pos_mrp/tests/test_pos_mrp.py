from odoo.tests import tagged
from odoo.addons.point_of_sale.tests.common import CommonPosTest


@tagged("post_install", "-at_install")
class TestChargeXPosMrp(CommonPosTest):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.pos_config_usd.open_ui()
        cls.session = cls.pos_config_usd.current_session_id
        cls.warehouse = cls.pos_config_usd.picking_type_id.warehouse_id

        cls.component = cls.env["product.product"].create({
            "name": "ChargeX Component",
            "default_code": "CHARGEX-STOCK-WHISH",
            "is_storable": True,
            "purchase_ok": True,
            "sale_ok": False,
        })
        cls.byproduct = cls.env["product.product"].create({
            "name": "ChargeX By-product",
            "default_code": "CHARGEX-STOCK-ALFA",
            "is_storable": True,
            "purchase_ok": True,
            "sale_ok": False,
        })
        cls.finished = cls.env["product.product"].create({
            "name": "ChargeX Alfa 1 Month",
            "default_code": "CHARGEX:alfa_1_month_days",
            "is_storable": True,
            "sale_ok": True,
            "available_in_pos": True,
            "list_price": 10.0,
        })
        cls.bom = cls.env["mrp.bom"].create({
            "code": "CHARGEX-BOM:alfa_1_month_days",
            "product_tmpl_id": cls.finished.product_tmpl_id.id,
            "product_qty": 1.0,
            "type": "normal",
            "uom_id": cls.finished.uom_id.id,
            "bom_line_ids": [(0, 0, {
                "product_id": cls.component.id,
                "product_qty": 3.0,
            })],
            "byproduct_ids": [(0, 0, {
                "product_id": cls.byproduct.id,
                "product_qty": 0.5,
                "cost_share": 20.0,
            })],
        })
        cls.env["stock.quant"]._update_available_quantity(
            cls.component,
            cls.warehouse.lot_stock_id,
            100.0,
        )

    def _make_order(self, product=None, qty=2.0):
        product = product or self.finished
        order = self.env["pos.order"].create({
            "session_id": self.session.id,
            "state": "paid",
            "amount_tax": 0.0,
            "amount_total": product.list_price * abs(qty),
            "amount_paid": product.list_price * abs(qty),
            "amount_return": 0.0,
        })
        line = self.env["pos.order.line"].create({
            "order_id": order.id,
            "product_id": product.id,
            "qty": qty,
            "price_unit": product.list_price,
            "price_subtotal": product.list_price * abs(qty),
            "price_subtotal_incl": product.list_price * abs(qty),
            "full_product_name": product.display_name,
        })
        return order, line

    def test_managed_manufacture_line_creates_one_done_mo_and_is_idempotent(self):
        order, line = self._make_order(qty=2.0)

        component_before = self.component.with_context(location=self.warehouse.lot_stock_id.id).qty_available
        byproduct_before = self.byproduct.with_context(location=self.warehouse.lot_stock_id.id).qty_available
        finished_before = self.finished.with_context(location=self.warehouse.lot_stock_id.id).qty_available

        order._chargex_create_manufacturing_orders()
        production = self.env["mrp.production"].search([
            ("chargex_pos_order_line_id", "=", line.id),
        ])

        self.assertEqual(len(production), 1)
        self.assertEqual(production.state, "done")
        self.assertEqual(production.product_id, self.finished)
        self.assertEqual(production.bom_id, self.bom)
        self.assertEqual(production.product_qty, 2.0)
        self.assertTrue(production.move_raw_ids.filtered(lambda move: move.product_id == self.component and move.state == "done"))
        self.assertTrue(production.move_finished_ids.filtered(lambda move: move.product_id == self.finished and move.state == "done"))
        self.assertTrue(production.move_finished_ids.filtered(lambda move: move.product_id == self.byproduct and move.state == "done"))

        self.assertEqual(
            self.component.with_context(location=self.warehouse.lot_stock_id.id).qty_available,
            component_before - 6.0,
        )
        self.assertEqual(
            self.byproduct.with_context(location=self.warehouse.lot_stock_id.id).qty_available,
            byproduct_before + 1.0,
        )
        self.assertEqual(
            self.finished.with_context(location=self.warehouse.lot_stock_id.id).qty_available,
            finished_before + 2.0,
        )

        order._chargex_create_manufacturing_orders()
        self.assertEqual(self.env["mrp.production"].search_count([
            ("chargex_pos_order_line_id", "=", line.id),
        ]), 1)
        self.assertEqual(
            self.component.with_context(location=self.warehouse.lot_stock_id.id).qty_available,
            component_before - 6.0,
        )

    def test_negative_or_kit_lines_do_not_create_mo(self):
        kit_product = self.env["product.product"].create({
            "name": "ChargeX Kit",
            "default_code": "CHARGEX:kit_product",
            "sale_ok": True,
            "available_in_pos": True,
        })
        self.env["mrp.bom"].create({
            "code": "CHARGEX-BOM:kit_product",
            "product_tmpl_id": kit_product.product_tmpl_id.id,
            "product_qty": 1.0,
            "type": "phantom",
            "uom_id": kit_product.uom_id.id,
            "bom_line_ids": [(0, 0, {
                "product_id": self.component.id,
                "product_qty": 1.0,
            })],
        })

        kit_order, kit_line = self._make_order(product=kit_product, qty=1.0)
        negative_order, negative_line = self._make_order(qty=-1.0)

        kit_order._chargex_create_manufacturing_orders()
        negative_order._chargex_create_manufacturing_orders()

        self.assertFalse(self.env["mrp.production"].search([
            ("chargex_pos_order_line_id", "in", [kit_line.id, negative_line.id]),
        ]))
