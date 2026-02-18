"use client";

import { useEffect, useMemo, useState } from "react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { AppShell } from "@/components/AppShell";
import { ProtectedPage } from "@/components/ProtectedPage";
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

export default function DashboardPage() {
  const [clientId, setClientId] = useState(1);
  const [data, setData] = useState<DashboardResponse | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let ignore = false;
    async function load() {
      setError("");
      try {
        const result = await apiRequest<DashboardResponse>(`/dashboard/${clientId}`);
        if (!ignore) setData(result);
      } catch (err) {
        if (!ignore) setError(err instanceof Error ? err.message : "Nu pot încărca dashboard");
      }
    }
    void load();
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
        conversions: data.platforms.google_ads.conversions
      },
      {
        name: "Meta",
        spend: data.platforms.meta_ads.spend,
        conversions: data.platforms.meta_ads.conversions
      }
    ];
  }, [data]);

  return (
    <ProtectedPage>
      <AppShell title="Dashboard Principal">
        <main>
          <div className="mb-4 flex items-center gap-3">
            <label className="text-sm text-slate-600">Client ID</label>
            <input
              type="number"
              min={1}
              value={clientId}
              onChange={(e) => setClientId(Number(e.target.value || 1))}
              className="wm-input w-24"
            />
          </div>

          {error ? <p className="mb-4 text-red-600">{error}</p> : null}

          <section className="mb-6 grid grid-cols-1 gap-4 md:grid-cols-3">
            <Card title="Spend" value={data ? `$${data.totals.spend}` : "-"} />
            <Card title="Conversions" value={data ? String(data.totals.conversions) : "-"} />
            <Card title="ROAS" value={data ? String(data.totals.roas) : "-"} />
          </section>

          <section className="wm-card p-4">
            <h2 className="mb-3 font-medium">Google vs Meta (Spend & Conversions)</h2>
            <div className="h-80 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="name" />
                  <YAxis />
                  <Tooltip />
                  <Bar dataKey="spend" fill="#7c3aed" />
                  <Bar dataKey="conversions" fill="#0ea5e9" />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </section>
        </main>
      </AppShell>
    </ProtectedPage>
  );
}

function Card({ title, value }: { title: string; value: string }) {
  return (
    <article className="wm-card p-4">
      <p className="text-sm text-slate-500">{title}</p>
      <p className="mt-1 text-xl font-semibold">{value}</p>
    </article>
  );
}
