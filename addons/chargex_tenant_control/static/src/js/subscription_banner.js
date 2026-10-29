/** @odoo-module **/

import { Component, onMounted, proxy, xml } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { rpc } from "@web/core/network/rpc";

class ChargeXSubscriptionBanner extends Component {
    static template = xml`
        <div t-if="this.state.message" t-att-class="'o_chargex_subscription_banner ' + this.state.stage">
            <span class="o_chargex_subscription_banner__label">ChargeX Accounting</span>
            <span><t t-out="this.state.message"/></span>
        </div>
    `;

    setup() {
        this.state = proxy({ message: "", stage: "active" });
        onMounted(() => {
            this.loadSubscriptionStatus();
        });
    }

    async loadSubscriptionStatus() {
        try {
            const data = await rpc("/chargex/tenant/status", {});
            this.state.message = data?.message || "";
            this.state.stage = data?.stage || "active";
        } catch {
            // Subscription status must never block or break the Odoo web client.
        }
    }
}

registry.category("main_components").add("chargex_subscription_banner", {
    Component: ChargeXSubscriptionBanner,
});
