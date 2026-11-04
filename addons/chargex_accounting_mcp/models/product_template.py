"""Constrained ChargeX product operations exposed through Odoo's official MCP."""

import math

from odoo import api, models
from odoo.exceptions import AccessError, UserError, ValidationError


class ProductTemplate(models.Model):
    _inherit = "product.template"

    @api.model
    def _cx_mcp_write_guard(self):
        if not self.env.user.has_group("chargex_accounting_mcp.group_product_mcp_writer"):
            raise AccessError("ChargeX MCP product writer permission is required.")
        flag = self.env["ir.config_parameter"].sudo().get_param(
            "chargex_accounting_mcp.product_writes_enabled", default="False"
        )
        if str(flag).lower() not in ("true", "1", "yes", "on"):
            raise AccessError("ChargeX MCP product writes are disabled by policy.")

    @api.model
    def _cx_mcp_revision(self, template):
        value = template.write_date
        return value.isoformat(timespec="microseconds") + "Z" if value else None

    @api.model
    def _cx_mcp_product(self, template_id, write=False):
        if type(template_id) is not int or template_id <= 0:
            raise ValidationError("A positive template ID is required.")
        product = self.with_context(active_test=False).browse(template_id).exists()
        if not product:
            raise UserError("Product not found.")
        product.check_access("write" if write else "read")
        if product.company_id and product.company_id != self.env.company:
            raise AccessError("The product belongs to a different company.")
        if write and not product.company_id:
            raise AccessError("Shared products cannot be modified by ChargeX MCP.")
        return product

    @api.model
    def _cx_mcp_snapshot(self, product):
        product.check_access("read")
        variants = product.with_context(active_test=False).product_variant_ids
        return {
            "template_id": product.id,
            "variant_id": variants.id if len(variants) == 1 else None,
            "name": product.name,
            "category_id": product.categ_id.id,
            "company_id": product.company_id.id or None,
            "default_code": variants.default_code if len(variants) == 1 else None,
            "list_price": product.list_price,
            "active": product.active,
            "variant_count": len(variants),
            "write_date": self._cx_mcp_revision(product),
        }

    @api.model
    def _cx_mcp_validate_name(self, name):
        if not isinstance(name, str) or not 1 <= len(name.strip()) <= 255:
            raise ValidationError("Name must be a non-empty string up to 255 characters.")
        return name.strip()

    @api.model
    def _cx_mcp_validate_sku(self, code):
        if not isinstance(code, str) or len(code.strip()) > 64:
            raise ValidationError("SKU must be a string of at most 64 characters.")
        return code.strip()

    @api.model
    def _cx_mcp_validate_price(self, price):
        if isinstance(price, bool) or not isinstance(price, (float, int)):
            raise ValidationError("Price must be numeric.")
        if not math.isfinite(price) or price < 0:
            raise ValidationError("Price must be finite and nonnegative.")
        return float(price)

    @api.model
    def _cx_mcp_category(self, category_id):
        if type(category_id) is not int or category_id <= 0:
            raise ValidationError("A positive category ID is required.")
        category = self.env["product.category"].browse(category_id).exists()
        if not category:
            raise UserError("Category not found.")
        category.check_access("read")
        if category.company_id and category.company_id != self.env.company:
            raise AccessError("Category belongs to a different company.")
        return category

    @api.model
    def _cx_mcp_no_duplicates(self, name=None, category_id=None, code=None, exclude=None):
        if name is not None and category_id is not None:
            domain = [
                ("name", "=", name), ("categ_id", "=", category_id),
                ("company_id", "in", [False, self.env.company.id]),
            ]
            if exclude:
                domain.append(("id", "!=", exclude))
            if self.with_context(active_test=False).search(domain, limit=1):
                raise ValidationError("A product with this name and category exists.")
        if code:
            domain = [
                ("default_code", "=", code),
                ("product_tmpl_id.company_id", "in", [False, self.env.company.id]),
            ]
            if exclude:
                domain.append(("product_tmpl_id", "!=", exclude))
            if self.env["product.product"].with_context(active_test=False).search(
                domain, limit=1
            ):
                raise ValidationError("SKU already belongs to another product.")

    @api.model
    def _cx_mcp_lock_and_check(self, product, expected_write_date):
        if not isinstance(expected_write_date, str) or not expected_write_date:
            raise ValidationError("Expected write_date is required.")
        # Acquire database row lock before revision checking. No data is returned.
        self.env.cr.execute(
            "SELECT id FROM product_template WHERE id = %s FOR UPDATE",
            [product.id],
        )
        product.invalidate_recordset(["write_date"])
        if self._cx_mcp_revision(product) != expected_write_date:
            raise ValidationError("Product has changed. Read it again first.")

    @api.model
    def chargex_mcp_list_categories(self):
        categories = self.env["product.category"].search(
            [("company_id", "in", [False, self.env.company.id])],
            order="name",
            limit=500,
        )
        return {
            "company_id": self.env.company.id,
            "categories": [{"id": c.id, "name": c.complete_name} for c in categories],
            "truncated": len(categories) == 500,
        }

    @api.model
    def chargex_mcp_get_product(self, template_id):
        return self._cx_mcp_snapshot(self._cx_mcp_product(template_id))

    @api.model
    def chargex_mcp_create_product(self, name, category_id, list_price, default_code):
        self._cx_mcp_write_guard()
        name = self._cx_mcp_validate_name(name)
        category = self._cx_mcp_category(category_id)
        price = self._cx_mcp_validate_price(list_price)
        code = self._cx_mcp_validate_sku(default_code)
        self._cx_mcp_no_duplicates(name=name, category_id=category.id, code=code)
        product = self.create({
            "name": name,
            "categ_id": category.id,
            "list_price": price,
            "company_id": self.env.company.id,
            "sale_ok": True,
            "purchase_ok": True,
        })
        variants = product.with_context(active_test=False).product_variant_ids
        if len(variants) != 1:
            raise UserError("Only a single-variant product can be created.")
        if code:
            variants.write({"default_code": code})
        return self._cx_mcp_snapshot(product)

    @api.model
    def chargex_mcp_update_product(self, template_id, expected_write_date, changes):
        self._cx_mcp_write_guard()
        product = self._cx_mcp_product(template_id, write=True)
        variants = product.with_context(active_test=False).product_variant_ids
        if len(variants) != 1:
            raise UserError("Multi-variant products are not supported.")
        if not isinstance(changes, dict):
            raise ValidationError("Changes must be an object.")
        # Optional ai_mcp schema values are injected as None when omitted.
        changes = {key: val for key, val in changes.items() if val is not None}
        if not changes or set(changes) - {"name", "list_price", "default_code"}:
            raise ValidationError("Allowed changes: name, list_price, default_code.")
        updates = {}
        if "name" in changes:
            updates["name"] = self._cx_mcp_validate_name(changes["name"])
        if "list_price" in changes:
            updates["list_price"] = self._cx_mcp_validate_price(changes["list_price"])
        code = self._cx_mcp_validate_sku(changes["default_code"]) if "default_code" in changes else None
        self._cx_mcp_lock_and_check(product, expected_write_date)
        if "name" in updates:
            self._cx_mcp_no_duplicates(
                name=updates["name"], category_id=product.categ_id.id, exclude=product.id
            )
        if code:
            self._cx_mcp_no_duplicates(code=code, exclude=product.id)
        if updates:
            product.write(updates)
        if code is not None:
            variants.write({"default_code": code or False})
        product.invalidate_recordset()
        return self._cx_mcp_snapshot(product)

    @api.model
    def chargex_mcp_set_product_active(self, template_id, expected_write_date, active):
        self._cx_mcp_write_guard()
        if type(active) is not bool:
            raise ValidationError("Active must be a boolean.")
        product = self._cx_mcp_product(template_id, write=True)
        if len(product.with_context(active_test=False).product_variant_ids) != 1:
            raise UserError("Multi-variant products are not supported.")
        self._cx_mcp_lock_and_check(product, expected_write_date)
        if product.active != active:
            product.write({"active": active})
        product.invalidate_recordset()
        return self._cx_mcp_snapshot(product)
