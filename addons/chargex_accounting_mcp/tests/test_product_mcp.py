"""Install-time integration tests for ChargeX tools on Odoo's MCP dispatcher."""

import json

from odoo.exceptions import AccessError, ValidationError
from odoo.tests import TransactionCase, new_test_user, tagged


@tagged("post_install", "-at_install")
class TestChargexProductMcp(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.category = cls.env["product.category"].create({
            "name": "MCP test products",
            "company_id": cls.env.company.id,
        })
        cls.writer = new_test_user(
            cls.env,
            "chargex_mcp_product_writer",
            groups="base.group_user,product.group_product_manager,chargex_accounting_mcp.group_product_mcp_writer",
            company_id=cls.env.company.id,
        )
        cls.reader = new_test_user(
            cls.env,
            "chargex_mcp_product_reader",
            groups="base.group_user,product.group_product_manager",
            company_id=cls.env.company.id,
        )

    def _call_tool(self, user, name, arguments):
        result = self.env["ai.mcp.request.dispatcher"].with_user(user)._mcp_dispatch({
            "id": 1,
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
        })
        self.assertFalse(result["isError"])
        return json.loads(result["content"][0]["text"])

    def _create(self, name="MCP Dummy Product", sku="MCP-NEW-01"):
        return self._call_tool(self.writer, "chargex_create_product", {
            "name": name,
            "category_id": self.category.id,
            "list_price": 23.75,
            "default_code": sku,
        })

    def test_tools_follow_odoo_group_permissions(self):
        for user, should_write in [(self.writer, True), (self.reader, False)]:
            response = self.env["ai.mcp.request.dispatcher"].with_user(user)._mcp_dispatch({
                "id": 1, "method": "tools/list", "params": {},
            })
            names = {tool["name"] for tool in response["tools"]}
            self.assertIn("chargex_get_product", names)
            self.assertIn("chargex_list_product_categories", names)
            self.assertEqual("chargex_create_product" in names, should_write)
            self.assertEqual("chargex_update_product" in names, should_write)
            self.assertEqual("chargex_set_product_active" in names, should_write)

    def test_write_policy_is_off_by_default(self):
        self.env["ir.config_parameter"].sudo().set_param(
            "chargex_accounting_mcp.product_writes_enabled", "False"
        )
        with self.assertRaises(AccessError):
            self._create()

    def test_writer_group_is_required_even_if_server_policy_enabled(self):
        self.env["ir.config_parameter"].sudo().set_param(
            "chargex_accounting_mcp.product_writes_enabled", "True"
        )
        with self.assertRaises(AccessError):
            self.env["product.template"].with_user(self.reader).chargex_mcp_create_product(
                "Forbidden", self.category.id, 10.0, "FORBIDDEN"
            )

    def test_full_create_update_archive_restore_roundtrip(self):
        self.env["ir.config_parameter"].sudo().set_param(
            "chargex_accounting_mcp.product_writes_enabled", "True"
        )
        created = self._create()
        self.assertEqual(created["name"], "MCP Dummy Product")
        self.assertEqual(created["company_id"], self.env.company.id)
        self.assertEqual(created["default_code"], "MCP-NEW-01")

        updated = self._call_tool(self.writer, "chargex_update_product", {
            "template_id": created["template_id"],
            "expected_revision": created["revision"],
            "changes": {"list_price": 27.00},
        })
        self.assertEqual(updated["list_price"], 27.0)

        archived = self._call_tool(self.writer, "chargex_set_product_active", {
            "template_id": updated["template_id"],
            "expected_revision": updated["revision"],
            "active": False,
        })
        self.assertFalse(archived["active"])
        restored = self._call_tool(self.writer, "chargex_set_product_active", {
            "template_id": archived["template_id"],
            "expected_revision": archived["revision"],
            "active": True,
        })
        self.assertTrue(restored["active"])

    def test_duplicate_sku_is_blocked_even_if_product_archived(self):
        self.env["ir.config_parameter"].sudo().set_param(
            "chargex_accounting_mcp.product_writes_enabled", "True"
        )
        product = self._create()
        self._call_tool(self.writer, "chargex_set_product_active", {
            "template_id": product["template_id"],
            "expected_revision": product["revision"],
            "active": False,
        })
        with self.assertRaises(ValidationError):
            self._create(name="Other MCP product", sku="MCP-NEW-01")

    def test_stale_revision_rejected(self):
        self.env["ir.config_parameter"].sudo().set_param(
            "chargex_accounting_mcp.product_writes_enabled", "True"
        )
        original = self._create()
        new_version = self._call_tool(self.writer, "chargex_update_product", {
            "template_id": original["template_id"],
            "expected_revision": original["revision"],
            "changes": {"list_price": 37.00},
        })
        self.assertEqual(new_version["list_price"], 37.0)
        with self.assertRaises(ValidationError):
            self._call_tool(self.writer, "chargex_update_product", {
                "template_id": original["template_id"],
                "expected_revision": original["revision"],
                "changes": {"name": "Stale write"},
            })

    def test_shared_product_cannot_be_changed(self):
        self.env["ir.config_parameter"].sudo().set_param(
            "chargex_accounting_mcp.product_writes_enabled", "True"
        )
        shared = self.env["product.template"].create({
            "name": "Shared MCP product",
            "company_id": False,
            "categ_id": self.category.id,
        })
        with self.assertRaises(AccessError):
            self.env["product.template"].with_user(self.writer).chargex_mcp_set_product_active(
                shared.id,
                self.env["product.template"]._cx_mcp_revision(shared),
                False,
            )
