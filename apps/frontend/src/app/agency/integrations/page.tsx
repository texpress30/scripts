"use client";

import { AppShell } from "@/components/AppShell";
import { ProtectedPage } from "@/components/ProtectedPage";

export default function AgencyIntegrationsPage() {
  return (
    <ProtectedPage>
      <AppShell title="Agency Integrations">
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
          <article className="wm-card p-4">
            <h2 className="text-base font-semibold text-slate-900">TikTok Ads (stabilized)</h2>
            <p className="mt-2 text-sm text-slate-600">
              Integrarea TikTok este activă pentru sync și vizibilitate în dashboard.
            </p>
          </article>

          <article className="wm-card p-4">
            <h2 className="text-base font-semibold text-slate-900">Pinterest Ads</h2>
            <p className="mt-2 text-sm text-slate-600">
              Integrarea Pinterest este activă pentru sync și monitorizare în Agency View.
            </p>
            <p className="mt-3 text-xs text-slate-500">Status și sync disponibile. Datele apar în dashboard după prima sincronizare.</p>
          </article>

          <article className="wm-card p-4">
            <h2 className="text-base font-semibold text-slate-900">Snapchat Ads</h2>
            <p className="mt-2 text-sm text-slate-600">
              Integrarea Snapchat este activă pentru sync și monitorizare în Agency View.
            </p>
            <p className="mt-3 text-xs text-slate-500">Status și sync disponibile. Datele apar în dashboard după prima sincronizare.</p>
          </article>
        </div>
      </AppShell>
    </ProtectedPage>
  );
}
