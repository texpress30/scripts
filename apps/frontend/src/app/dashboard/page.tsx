"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

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
      <main className="mx-auto min-h-screen max-w-6xl p-6">
        <header className="mb-6 flex items-center justify-between">
          <h1 className="text-2xl font-semibold">Dashboard Principal</h1>
          <nav className="flex gap-3 text-sm">
            <Link className="text-brand-600" href="/clients">
              Clienți
            </Link>
            <Link className="text-slate-600" href="/login">
              Logout
            </Link>
          </nav>
        </header>

        <div className="mb-4 flex items-center gap-3">
          <label className="text-sm text-slate-600">Client ID</label>
          <input
            type="number"
            min={1}
            value={clientId}
            onChange={(e) => setClientId(Number(e.target.value || 1))}
            className="w-24 rounded border border-slate-300 px-3 py-2"
          />
        </div>

        {error ? <p className="mb-4 text-red-600">{error}</p> : null}

        <section className="mb-6 grid grid-cols-1 gap-4 md:grid-cols-3">
          <Card title="Spend" value={data ? `$${data.totals.spend}` : "-"} />
          <Card title="Conversions" value={data ? String(data.totals.conversions) : "-"} />
          <Card title="ROAS" value={data ? String(data.totals.roas) : "-"} />
        </section>

        <section className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
          <h2 className="mb-3 font-medium">Google vs Meta (Spend & Conversions)</h2>
          <div className="h-80 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="name" />
                <YAxis />
                <Tooltip />
                <Bar dataKey="spend" fill="#2563eb" />
                <Bar dataKey="conversions" fill="#16a34a" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </section>
      </main>
    </ProtectedPage>
  );
}

function Card({ title, value }: { title: string; value: string }) {
  return (
    <article className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <p className="text-sm text-slate-500">{title}</p>
      <p className="mt-1 text-xl font-semibold">{value}</p>
    </article>
  );
}
