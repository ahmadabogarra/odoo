from __future__ import annotations

from odoo import Command
from odoo.exceptions import AccessError, UserError
from odoo.tests.common import TransactionCase


class TestTenantControlSecurity(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.params = cls.env["ir.config_parameter"].sudo()
        cls.params.set_str("chargex.subscription.status", "active")
        cls.params.set_str("chargex.subscription.message", "Subscription suspended")
        cls.tenant_user = cls.env["res.users"].create(
            {
                "name": "ChargeX Tenant Security Test",
                "login": "chargex-tenant-security-test@example.invalid",
                "email": "chargex-tenant-security-test@example.invalid",
                "group_ids": [
                    Command.set(
                        [
                            cls.env.ref("base.group_user").id,
                            cls.env.ref("base.group_partner_manager").id,
                        ]
                    )
                ],
            }
        )
        # Models the legacy provisioning bug where customer admins inherited
        # the service user's Settings group. This user must still not become a
        # ChargeX control-plane identity.
        cls.legacy_settings_user = cls.env["res.users"].create(
            {
                "name": "Legacy ChargeX Settings User",
                "login": "chargex-legacy-settings-test@example.invalid",
                "email": "chargex-legacy-settings-test@example.invalid",
                "group_ids": [Command.set([cls.env.ref("base.group_system").id])],
            }
        )

    def setUp(self):
        super().setUp()
        self.params.set_str("chargex.subscription.status", "active")

    def test_rpc_context_flag_cannot_bypass_suspension(self):
        self.params.set_str("chargex.subscription.status", "suspended")

        with self.assertRaises(UserError):
            self.env["res.partner"].with_user(self.tenant_user).with_context(
                chargex_tenant_control_bypass=True
            ).create({"name": "Blocked tenant write"})

    def test_legacy_settings_user_cannot_bypass_suspension(self):
        self.params.set_str("chargex.subscription.status", "suspended")

        with self.assertRaises(UserError):
            self.env["res.partner"].with_user(self.legacy_settings_user).with_context(
                chargex_tenant_control_bypass=True
            ).create({"name": "Blocked legacy settings write"})

    def test_service_admin_can_manage_suspended_database(self):
        self.params.set_str("chargex.subscription.status", "suspended")

        partner = self.env["res.partner"].with_user(
            self.env.ref("base.user_admin")
        ).create({"name": "Control plane write"})

        self.assertTrue(partner.exists())

    def test_tenant_cannot_modify_subscription_parameter_even_with_context_flag(self):
        self.params.set_str("chargex.subscription.status", "suspended")
        record = self.params.search(
            [("key", "=", "chargex.subscription.status")], limit=1
        )
        self.assertTrue(record)

        with self.assertRaises(AccessError):
            record.with_user(self.tenant_user).with_context(
                chargex_tenant_control_bypass=True
            ).write({"value": "active"})

        self.assertEqual(
            self.params.get_str("chargex.subscription.status"), "suspended"
        )

    def test_legacy_settings_user_cannot_modify_subscription_parameter(self):
        self.params.set_str("chargex.subscription.status", "suspended")
        record = self.params.search(
            [("key", "=", "chargex.subscription.status")], limit=1
        )

        with self.assertRaises(AccessError):
            record.with_user(self.legacy_settings_user).write({"value": "active"})

        self.assertEqual(
            self.params.get_str("chargex.subscription.status"), "suspended"
        )

    def test_tenant_cannot_create_or_rename_protected_parameter(self):
        tenant_params = self.env["ir.config_parameter"].with_user(self.tenant_user)

        with self.assertRaises(AccessError):
            tenant_params.create(
                {"key": "chargex.subscription.injected", "value": "active"}
            )

        ordinary = self.params.create(
            {"key": "chargex.security_test.ordinary", "value": "ok"}
        )
        with self.assertRaises(AccessError):
            ordinary.with_user(self.tenant_user).write(
                {"key": "chargex.subscription.renamed"}
            )
