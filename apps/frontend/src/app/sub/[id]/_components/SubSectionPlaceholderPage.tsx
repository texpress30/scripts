"use client";

import React from "react";
import { useEffect, useMemo, useState } from "react";

import { AppShell } from "@/components/AppShell";
import { ProtectedPage } from "@/components/ProtectedPage";
import { apiRequest } from "@/lib/api";
import { SubReportingNav } from "@/app/sub/[id]/_components/SubReportingNav";

type ClientItem = {
  id: number;
  name: string;
};

export function SubSectionPlaceholderPage({ clientId, sectionTitle }: { clientId: number; sectionTitle: string }) {
  const [clientName, setClientName] = useState<string>(`Sub-account #${clientId}`);

  useEffect(() => {
    let ignore = false;

    async function loadClientName() {
      try {
        const result = await apiRequest<{ items: ClientItem[] }>("/clients");
        const match = result.items.find((item) => item.id === clientId);
        if (!ignore && match?.name) setClientName(match.name);
      } catch {
        if (!ignore) setClientName(`Sub-account #${clientId}`);
      }
    }

    if (Number.isFinite(clientId)) void loadClientName();

    return () => {
      ignore = true;
    };
  }, [clientId]);

  const composedTitle = useMemo(() => `${sectionTitle} - ${clientName}`, [sectionTitle, clientName]);

  return (
    <ProtectedPage>
      <AppShell title={null}>
        <SubReportingNav clientId={clientId} />

        <section className="wm-card p-6">
          <h1 className="text-xl font-semibold text-slate-900">{composedTitle}</h1>
          <div className="mt-4 rounded-lg border border-dashed border-slate-300 bg-slate-50 p-6 text-sm text-slate-600">Coming Soon</div>
        </section>
      </AppShell>
    </ProtectedPage>
  );
}
