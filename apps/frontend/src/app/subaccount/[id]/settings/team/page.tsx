"use client";

import { useParams } from "next/navigation";

import { AppShell } from "@/components/AppShell";
import { ProtectedPage } from "@/components/ProtectedPage";

export default function SubAccountSettingsPage() {
  const params = useParams<{ id: string }>();
  return (
    <ProtectedPage>
      <AppShell title={`Sub-account #${params.id} — Echipa Mea`}>
        <main className="p-6">
          <section className="wm-card p-4">
            <h2 className="text-lg font-semibold text-slate-900">Echipa Mea</h2>
            <p className="mt-2 text-sm text-slate-600">Setările sub-account pentru Echipa Mea vor fi disponibile aici.</p>
          </section>
        </main>
      </AppShell>
    </ProtectedPage>
  );
}
