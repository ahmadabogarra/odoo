CHARGEX_BOM_PREFIX = "CHARGEX-BOM:"


def post_init_hook(env):
    """Repair existing ChargeX manufacture products when the bridge is installed."""
    boms = env["mrp.bom"].search([
        ("code", "like", f"{CHARGEX_BOM_PREFIX}%"),
        ("type", "=", "normal"),
        ("active", "=", True),
    ])
    boms.mapped("product_tmpl_id").write({"is_storable": True})
