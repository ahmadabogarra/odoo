# ChargeX Accounting products on the official Odoo MCP

This independent Odoo addon provides five constrained tools as `ir.actions.server`
records with `use_in_mcp=True`:

- `chargex_list_product_categories` (read-only)
- `chargex_get_product` (read-only)
- `chargex_create_product`
- `chargex_update_product`
- `chargex_set_product_active` (archive/restore)

## Architecture

The addon **depends on Odoo's `ai_mcp` module**; it does not duplicate the
official MCP transport, OAuth, API-key authentication, or the action dispatcher.
Odoo authenticates each request using the associated Odoo user. Every business
operation runs under the invoking user's ACLs and active company. No `sudo()`
is used for business record reads/writes (only to read the global policy flag).

The module is independently written; it does **not** include or distribute
Odoo Enterprise AI or MCP source. The official `ai` and `ai_mcp`
dependencies must be made available separately under an appropriate license
before installation. The current ChargeX Community-only Dockerfile does not
ship these dependencies, so this addon is **not ready to install in production**.

## Safe installation

1. Make the compatible Odoo 20 `ai` and `ai_mcp` modules available in a
   licensed, isolated testing deployment.
2. Install `chargex_accounting_mcp` on a **non-production** test database.
3. Authenticate via Odoo's official MCP endpoint, and verify `tools/list`
   under an ordinary Odoo user rather than a shared administrator token.
4. Give a dedicated product editor both normal Odoo product-create permissions
   and group `ChargeX MCP Product Writer`.
5. When intentionally testing writes, set Odoo system parameter
   `chargex_accounting_mcp.product_writes_enabled` to `True`.
   This parameter is **False by default**; never enable it automatically
   during module installation.
6. Run Odoo addon integration tests and a real test-database product
   create → read → update → archive → restore sequence.
7. Keep the existing external `odoo-mcp` service available in read-only mode
   until the native tools have passed staging validation.

## Security contract

- All operations are scoped to `env.company` and Odoo's record permissions.
- Shared company-less products may be read but cannot be changed.
- Create/update reject duplicate names in the same category and duplicate
  non-empty SKUs across active and archived records.
- Only single-variant templates are mutable; no arbitrary model or field
  operations are exposed.
- Updating and archiving require the exact `revision` returned by
  `chargex_get_product`; a database row lock serializes concurrent writes.
- The official MCP dispatcher currently supplies `tool_request_confirmed=True`
  when running server actions. **This addon does not implement human approval.**
  Do not enable write policy for high-risk operations without a separate
  trusted approval workflow outside the AI arguments.
- Authorization is controlled at both the Odoo group and global write switch.
  This is not an approval workflow or a substitute for live security testing.

## Transition

These are five **new native tools**, not a migration or deletion of the
70 tools in the old external MCP server. Further migration should occur
by feature area after matching functional tests and Odoo tenant isolation.
