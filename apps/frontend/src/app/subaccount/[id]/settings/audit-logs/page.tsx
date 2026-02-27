"use client";

import { useParams } from "next/navigation";

import { AppShell } from "@/components/AppShell";
import { ProtectedPage } from "@/components/ProtectedPage";

export default function SubAccountSettingsPage() {
  const params = useParams<{ id: string }>();
  return (
    <ProtectedPage>
      <AppShell title={`Sub-account #${params.id} — Audit Logs`}>
        <main className="p-6">
          <section className="wm-card p-4">
            <h2 className="text-lg font-semibold text-slate-900">Audit Logs</h2>
            <p className="mt-2 text-sm text-slate-600">Setările sub-account pentru Audit Logs vor fi disponibile aici.</p>
          </section>
        </main>
      </AppShell>
    </ProtectedPage>
  );
}
