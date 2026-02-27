"use client";

import { AppShell } from "@/components/AppShell";
import { ProtectedPage } from "@/components/ProtectedPage";

export default function SettingsStoragePage() {
  return (
    <ProtectedPage>
      <AppShell title="Settings — Media Storage Usage">
        <main className="p-6">
          <section className="wm-card p-4">
            <h2 className="text-lg font-semibold text-slate-900">Media Storage Usage</h2>
            <p className="mt-2 text-sm text-slate-600">Configurațiile pentru Media Storage Usage vor fi disponibile aici.</p>
          </section>
        </main>
      </AppShell>
    </ProtectedPage>
  );
}
