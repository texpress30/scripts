"use client";

import { AppShell } from "@/components/AppShell";
import { ProtectedPage } from "@/components/ProtectedPage";
import {
  isPinterestIntegrationEnabled,
  isSnapchatIntegrationEnabled,
  isTikTokIntegrationEnabled,
} from "@/lib/featureFlags";

export default function AgencyIntegrationsPage() {
  const tiktokEnabled = isTikTokIntegrationEnabled();
  const pinterestEnabled = isPinterestIntegrationEnabled();
  const snapchatEnabled = isSnapchatIntegrationEnabled();

  return (
    <ProtectedPage>
      <AppShell title="Agency Integrations">
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
          <article className="wm-card p-4">
            <h2 className="text-base font-semibold text-slate-900">TikTok Ads (stabilized)</h2>
            <p className="mt-2 text-sm text-slate-600">
              {tiktokEnabled
                ? "Feature flag activ: sync-ul TikTok este disponibil pentru validare/UAT."
                : "Feature flag inactiv: integrarea TikTok rămâne ascunsă până la activare controlată."}
            </p>
          </article>

          <article className="wm-card p-4">
            <h2 className="text-base font-semibold text-slate-900">Pinterest Ads (slice 1)</h2>
            <p className="mt-2 text-sm text-slate-600">
              {pinterestEnabled
                ? "Feature flag activ: endpoint-urile Pinterest status/sync sunt disponibile în modul skeleton."
                : "Feature flag inactiv: integrarea Pinterest este pregătită, dar oprită implicit."}
            </p>
            <p className="mt-3 text-xs text-slate-500">Contract freeze only. Sync real/provider adapter urmează în slice-ul următor.</p>
          </article>

          <article className="wm-card p-4">
            <h2 className="text-base font-semibold text-slate-900">Snapchat Ads (slice 1)</h2>
            <p className="mt-2 text-sm text-slate-600">
              {snapchatEnabled
                ? "Feature flag activ: endpoint-urile Snapchat status/sync sunt disponibile în modul skeleton."
                : "Feature flag inactiv: integrarea Snapchat este pregătită, dar oprită implicit."}
            </p>
            <p className="mt-3 text-xs text-slate-500">Contract freeze only. Sync real/provider adapter urmează în slice-ul următor.</p>
          </article>
        </div>
      </AppShell>
    </ProtectedPage>
  );
}
