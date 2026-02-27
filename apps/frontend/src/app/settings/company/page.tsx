"use client";

import { AppShell } from "@/components/AppShell";
import { ProtectedPage } from "@/components/ProtectedPage";

export default function SettingsCompanyPage() {
  return (
    <ProtectedPage>
      <AppShell title="Settings — Company">
        <main className="p-6">
          <section className="wm-card p-4">
            <h2 className="text-lg font-semibold text-slate-900">Company</h2>
            <p className="mt-2 text-sm text-slate-600">Configurațiile pentru Company vor fi disponibile aici.</p>
          </section>
        </main>
      </AppShell>
    </ProtectedPage>
  );
}
