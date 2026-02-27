"use client";

import { AppShell } from "@/components/AppShell";
import { ProtectedPage } from "@/components/ProtectedPage";

export default function SettingsAiAgentsPage() {
  return (
    <ProtectedPage>
      <AppShell title="Settings — Ai Agents">
        <main className="p-6">
          <section className="wm-card p-4">
            <h2 className="text-lg font-semibold text-slate-900">Ai Agents</h2>
            <p className="mt-2 text-sm text-slate-600">Configurațiile pentru Ai Agents vor fi disponibile aici.</p>
          </section>
        </main>
      </AppShell>
    </ProtectedPage>
  );
}
