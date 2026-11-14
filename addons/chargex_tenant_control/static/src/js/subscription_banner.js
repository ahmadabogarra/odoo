/** @odoo-module **/

import { Component, onMounted, onWillUnmount, proxy, xml } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { rpc } from "@web/core/network/rpc";

// UI-only: suppress the Enterprise trial reminder on the app dashboard.
// This deliberately does not affect the expired-database blocker, Odoo license
// state, or ChargeX subscription/read-only enforcement.
function installEnterpriseTrialNoticeHider() {
    const expirationText = /\bthis database will expire in\b/i;
    let frame = null;

    function hideNotice() {
        frame = null;
        if (!document.body) {
            return;
        }
        const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
        let node;
        while ((node = walker.nextNode())) {
            if (!expirationText.test(node.textContent || "")) {
                continue;
            }
            const label = node.parentElement;
            if (!label || label.closest("[data-chargex-banner-hidden]")) {
                continue;
            }
            let panel = label.closest(
                ".o_enterprise_expiration_panel, .o_database_expiration_panel, .alert, [role='alert']"
            );
            if (!panel) {
                // Some Odoo versions render the dashboard reminder without an
                // alert class. Find its small, dismissible containing panel.
                let parent = label;
                for (let depth = 0; depth < 5 && parent; depth++, parent = parent.parentElement) {
                    const rect = parent.getBoundingClientRect();
                    if (rect.width >= 200 && rect.height >= 35 && rect.height <= 180
                            && parent.querySelector("button, [role='button']")) {
                        panel = parent;
                        break;
                    }
                }
            }
            if (panel) {
                const rect = panel.getBoundingClientRect();
                // Never hide the fullscreen expired-subscription blocker.
                if (rect.width >= 200 && rect.height >= 30 && rect.height <= 180) {
                    panel.dataset.chargexBannerHidden = "true";
                    panel.style.setProperty("display", "none", "important");
                }
            }
        }
    }

    function schedule() {
        if (frame === null) {
            frame = window.requestAnimationFrame(hideNotice);
        }
    }

    const observer = new MutationObserver(schedule);
    observer.observe(document.body, { childList: true, subtree: true, characterData: true });
    schedule();
    return () => {
        observer.disconnect();
        if (frame !== null) {
            window.cancelAnimationFrame(frame);
        }
    };
}

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
            this.stopTrialNoticeHider = installEnterpriseTrialNoticeHider();
            this.loadSubscriptionStatus();
        });
        onWillUnmount(() => this.stopTrialNoticeHider?.());
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
