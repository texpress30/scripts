"use client";

import { useParams } from "next/navigation";

import { AppShell } from "@/components/AppShell";
import { ProtectedPage } from "@/components/ProtectedPage";

export default function SubAccountSettingsPage() {
  const params = useParams<{ id: string }>();
  return (
    <ProtectedPage>
      <AppShell title={`Sub-account #${params.id} — Integrări`}>
        <main className="p-6">
          <section className="wm-card p-4">
            <h2 className="text-lg font-semibold text-slate-900">Integrări</h2>
            <p className="mt-2 text-sm text-slate-600">Sincronizarea datelor se face doar din Agency Accounts / Agency Integrations. Din sub-account această secțiune este doar informativă.</p>
          </section>
        </main>
      </AppShell>
    </ProtectedPage>
  );
}
