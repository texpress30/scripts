"use client";

import { useEffect, useMemo, useState } from "react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { ProtectedPage } from "@/components/ProtectedPage";
import { AppShell } from "@/components/AppShell";
import { ClientCommandPalette } from "@/components/ClientCommandPalette";
import { apiRequest } from "@/lib/api";

type DashboardResponse = {
  client_id: number;
  totals: {
    spend: number;
    conversions: number;
    roas: number;
  };
  platforms: {
    google_ads: { spend: number; conversions: number; roas?: number };
    meta_ads: { spend: number; conversions: number; roas?: number };
  };
};

type ClientItem = {
  id: number;
  name: string;
  owner_email: string;
};

type ClientsResponse = { items: ClientItem[] };

export default function DashboardPage() {
  const [clientId, setClientId] = useState(1);
  const [clients, setClients] = useState<ClientItem[]>([]);
  const [data, setData] = useState<DashboardResponse | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let ignore = false;

    async function loadClients() {
      try {
        const result = await apiRequest<ClientsResponse>("/clients");
        if (!ignore) {
          setClients(result.items);
          if (result.items.length > 0 && !result.items.some((item) => item.id === clientId)) {
            setClientId(result.items[0].id);
          }
        }
      } catch {
        // dashboard continues to work with manual/default client id fallback
      }
    }

    void loadClients();
    return () => {
      ignore = true;
    };
  }, [clientId]);

  useEffect(() => {
    let ignore = false;
    async function loadDashboard() {
      setError("");
      try {
        const result = await apiRequest<DashboardResponse>(`/dashboard/${clientId}`);
        if (!ignore) setData(result);
      } catch (err) {
        if (!ignore) setError(err instanceof Error ? err.message : "Nu pot încărca dashboard");
      }
    }

    void loadDashboard();
    return () => {
      ignore = true;
    };
  }, [clientId]);

  const chartData = useMemo(() => {
    if (!data) return [];
    return [
      {
        name: "Google",
        spend: data.platforms.google_ads.spend,
        conversions: data.platforms.google_ads.conversions,
        roas: data.platforms.google_ads.roas ?? 0
      },
      {
        name: "Meta",
        spend: data.platforms.meta_ads.spend,
        conversions: data.platforms.meta_ads.conversions,
        roas: data.platforms.meta_ads.roas ?? 0
      }
    ];
  }, [data]);

  return (
    <ProtectedPage>
      <AppShell title="Dashboard Premium">
        <main>
          <div className="mb-6 flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
            <div>
              <p className="text-sm text-slate-500">Analiză multi-platform pentru clientul selectat.</p>
            </div>
            <ClientCommandPalette clients={clients} selectedClientId={clientId} onSelect={setClientId} />
          </div>

          {error ? <p className="mb-4 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-600">{error}</p> : null}

          <section className="mb-6 grid grid-cols-1 gap-4 md:grid-cols-3">
            <MetricCard title="Spend" value={data ? `$${data.totals.spend.toLocaleString()}` : "-"} />
            <MetricCard title="Conversions" value={data ? data.totals.conversions.toLocaleString() : "-"} />
            <MetricCard title="ROAS" value={data ? data.totals.roas.toFixed(2) : "-"} />
          </section>

          <section className="wm-card p-4">
            <h2 className="mb-3 font-medium">Google vs Meta (Spend, Conversions, ROAS)</h2>
            <div className="h-80 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="name" />
                  <YAxis />
                  <Tooltip />
                  <Bar dataKey="spend" fill="#7c3aed" />
                  <Bar dataKey="conversions" fill="#0ea5e9" />
                  <Bar dataKey="roas" fill="#10b981" />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </section>
        </main>
      </AppShell>
    </ProtectedPage>
  );
}

function MetricCard({ title, value }: { title: string; value: string }) {
  return (
    <article className="wm-card p-4">
      <p className="text-sm text-slate-500">{title}</p>
      <p className="mt-1 text-xl font-semibold text-slate-900">{value}</p>
    </article>
  );
}
