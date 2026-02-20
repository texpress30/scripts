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
          <h2 className="text-base font-semibold text-slate-900">TikTok Ads (Slice 8.2.1)</h2>
          <p className="mt-2 text-sm text-slate-600">
            {enabled
              ? "Feature flag activ: endpoint-urile de status/sync sunt disponibile în modul skeleton."
              : "Feature flag inactiv: integrarea TikTok rămâne ascunsă până la validarea UAT."}
          </p>
          <p className="mt-3 text-xs text-slate-500">Contract freeze only. Adapterul provider și sincronizarea reală vin în Slice 8.2.2.</p>
        </article>
      </AppShell>
    </ProtectedPage>
  );
}
