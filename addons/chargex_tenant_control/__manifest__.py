{
    "name": "ChargeX Tenant Control",
    "summary": "Subscription enforcement and ChargeX Accounting tenant controls",
    "version": "20.0.1.0.0",
    "category": "Technical",
    "license": "LGPL-3",
    "depends": ["base", "web"],
    "data": [],
    "assets": {
        "web.assets_backend": [
            "chargex_tenant_control/static/src/js/subscription_banner.js",
            "chargex_tenant_control/static/src/scss/subscription_banner.scss",
        ],
    },
    "installable": True,
    "application": False,
    "auto_install": False,
}
