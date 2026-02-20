"use client";

import { useEffect, useState } from "react";
import { AppShell } from "@/components/AppShell";
import { ProtectedPage } from "@/components/ProtectedPage";
import { ClientCommandPalette } from "@/components/ClientCommandPalette";
import { apiRequest } from "@/lib/api";

type ClientItem = { id: number; name: string; owner_email: string };
type ClientsResponse = { items: ClientItem[] };

type Recommendation = {
  id: number;
  client_id: number;
  status: "new" | "approved" | "rejected" | "applied" | "expired";
  payload: {
    problema: string;
    cauza: string;
    actiune: string;
    impact_estimat: string;
    incredere: number;
    risc: string;
  };
  updated_at: string;
};

type ImpactWindow = {
  window_days: number;
  delta_cpa: number;
  delta_roas: number;
  delta_cvr: number;
};

export default function RecommendationsPage() {
  const [clientId, setClientId] = useState(1);
  const [clients, setClients] = useState<ClientItem[]>([]);
  const [items, setItems] = useState<Recommendation[]>([]);
  const [impact, setImpact] = useState<ImpactWindow[]>([]);
  const [error, setError] = useState("");

  async function loadAll(selectedClientId: number) {
    try {
      setError("");
      const [recList, impactReport] = await Promise.all([
        apiRequest<{ items: Recommendation[] }>(`/ai/recommendations/${selectedClientId}/list`),
        apiRequest<{ windows: ImpactWindow[] }>(`/ai/recommendations/${selectedClientId}/impact-report`),
      ]);
      setItems(recList.items);
      setImpact(impactReport.windows);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Nu pot incarca recomandarile");
    }
  }

  useEffect(() => {
    let ignore = false;
    async function loadClients() {
      try {
        const result = await apiRequest<ClientsResponse>("/clients");
        if (!ignore) {
          setClients(result.items);
          if (result.items.length > 0) {
            const firstId = result.items[0].id;
            setClientId(firstId);
            await loadAll(firstId);
          }
        }
      } catch {
        /* noop */
      }
    }
    void loadClients();
    return () => {
      ignore = true;
    };
  }, []);

  useEffect(() => {
    void loadAll(clientId);
  }, [clientId]);

  async function generateRecommendation() {
    await apiRequest(`/ai/recommendations/${clientId}`);
    await loadAll(clientId);
  }

  async function reviewRecommendation(recommendationId: number, action: "approve" | "dismiss" | "snooze") {
    await apiRequest(`/ai/recommendations/${clientId}/${recommendationId}/review`, {
      method: "POST",
      body: JSON.stringify({ action, snooze_days: 3 }),
    });
    await loadAll(clientId);
  }

  return (
    <ProtectedPage>
      <AppShell title="AI Recommendations">
        <div className="mb-5 flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
          <ClientCommandPalette clients={clients} selectedClientId={clientId} onSelect={setClientId} />
          <button
            onClick={generateRecommendation}
            className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-500"
          >
            Generate recommendation
          </button>
        </div>

        {error && <p className="mb-4 text-sm text-rose-500">{error}</p>}

        <div className="grid gap-4 lg:grid-cols-2">
          <div className="space-y-3">
            {items.map((item) => (
              <div key={item.id} className="mcc-card p-4">
                <div className="mb-2 flex items-center justify-between">
                  <span className="text-xs uppercase text-slate-500">#{item.id} · {item.status}</span>
                  <span className="text-xs text-slate-400">{new Date(item.updated_at).toLocaleString()}</span>
                </div>
                <p className="text-sm font-semibold">Problema: {item.payload.problema}</p>
                <p className="text-sm">Cauza: {item.payload.cauza}</p>
                <p className="text-sm">Actiune: {item.payload.actiune}</p>
                <p className="text-sm">Impact: {item.payload.impact_estimat}</p>
                <p className="text-xs text-slate-500">Incredere: {(item.payload.incredere * 100).toFixed(0)}% · Risc: {item.payload.risc}</p>

                <div className="mt-3 flex gap-2">
                  <button onClick={() => reviewRecommendation(item.id, "approve")} className="rounded bg-emerald-600 px-3 py-1.5 text-xs text-white">Approve</button>
                  <button onClick={() => reviewRecommendation(item.id, "dismiss")} className="rounded bg-rose-600 px-3 py-1.5 text-xs text-white">Dismiss</button>
                  <button onClick={() => reviewRecommendation(item.id, "snooze")} className="rounded bg-amber-500 px-3 py-1.5 text-xs text-white">Snooze</button>
                </div>
              </div>
            ))}
            {items.length === 0 && <div className="mcc-card p-6 text-sm text-slate-500">Nu exista recomandari. Apasa Generate recommendation.</div>}
          </div>

          <div className="mcc-card p-4">
            <h3 className="mb-3 text-sm font-semibold">Impact report (delta CPA / ROAS / CVR)</h3>
            <div className="space-y-2 text-sm">
              {impact.map((window) => (
                <div key={window.window_days} className="rounded border border-slate-200 p-3 dark:border-slate-700">
                  <p className="font-medium">{window.window_days} zile</p>
                  <p>Δ CPA: {window.delta_cpa}</p>
                  <p>Δ ROAS: +{window.delta_roas}</p>
                  <p>Δ CVR: +{window.delta_cvr}%</p>
                </div>
              ))}
            </div>
          </div>
        </div>
      </AppShell>
    </ProtectedPage>
  );
}
