/** @odoo-module **/

import { Component, onWillStart, useState, xml } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { rpc } from "@web/core/network/rpc";

class ChargeXSubscriptionBanner extends Component {
    static template = xml`
        <div t-if="state.message" t-att-class="'o_chargex_subscription_banner ' + state.stage">
            <span class="o_chargex_subscription_banner__label">ChargeX Accounting</span>
            <span t-esc="state.message"/>
        </div>
    `;

    setup() {
        this.state = useState({ message: "", stage: "active" });
        onWillStart(async () => {
            try {
                const data = await rpc("/chargex/tenant/status", {});
                this.state.message = data.message || "";
                this.state.stage = data.stage || "active";
            } catch {
                // Never prevent the Odoo web client from loading because of the banner.
            }
        });
    }
}

registry.category("main_components").add("chargex_subscription_banner", {
    Component: ChargeXSubscriptionBanner,
});
