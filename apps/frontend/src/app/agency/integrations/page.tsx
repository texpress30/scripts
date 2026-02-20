"use client";

import { AppShell } from "@/components/AppShell";
import { ProtectedPage } from "@/components/ProtectedPage";
import { isTikTokIntegrationEnabled } from "@/lib/featureFlags";

export default function AgencyIntegrationsPage() {
  const enabled = isTikTokIntegrationEnabled();

  return (
    <ProtectedPage>
      <AppShell title="Agency Integrations">
        <article className="wm-card p-4">
          <h2 className="text-base font-semibold text-slate-900">TikTok Ads (Slice 8.2.2)</h2>
          <p className="mt-2 text-sm text-slate-600">
            {enabled
              ? "Feature flag activ: sync-ul TikTok (mock) este disponibil și salvează snapshot-uri pentru dashboard."
              : "Feature flag inactiv: integrarea TikTok rămâne ascunsă până la validarea UAT."}
          </p>
          <p className="mt-3 text-xs text-slate-500">Sync minim E2E livrat. Adapterul provider real rămâne pentru hardening ulterior.</p>
        </article>
      </AppShell>
    </ProtectedPage>
  );
}
