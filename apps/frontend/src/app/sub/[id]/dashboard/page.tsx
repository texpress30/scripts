"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import { AppShell } from "@/components/AppShell";
import { ProtectedPage } from "@/components/ProtectedPage";
import { apiRequest } from "@/lib/api";
import { getCurrentRole, isReadOnlyRole } from "@/lib/session";

type DashboardResponse = {
  client_id: number;
  totals: { spend: number; conversions: number; roas: number };
  platforms: {
    google_ads: { spend: number; conversions: number; roas?: number };
    meta_ads: { spend: number; conversions: number; roas?: number };
  };
};

export default function SubDashboardPage() {
  const params = useParams<{ id: string }>();
  const clientId = Number(params.id);

  const [data, setData] = useState<DashboardResponse | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<"google" | "meta" | null>(null);
  const role = getCurrentRole();
  const readOnly = isReadOnlyRole(role);

  async function load() {
    setError("");
    setLoading(true);
    try {
      const result = await apiRequest<DashboardResponse>(`/dashboard/${clientId}`);
      setData(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Nu pot încărca dashboard-ul clientului");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (Number.isFinite(clientId)) void load();
  }, [clientId]);

  async function sync(channel: "google" | "meta") {
    setBusy(channel);
    try {
      const path = channel === "google" ? `/integrations/google-ads/${clientId}/sync` : `/integrations/meta-ads/${clientId}/sync`;
      await apiRequest(path, { method: "POST" });
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Sync eșuat");
    } finally {
      setBusy(null);
    }
  }

  const totals = data?.totals ?? { spend: 0, conversions: 0, roas: 0 };
  const google = data?.platforms.google_ads ?? { spend: 0, conversions: 0, roas: 0 };
  const meta = data?.platforms.meta_ads ?? { spend: 0, conversions: 0, roas: 0 };

  const subtitle = useMemo(() => `Sub-account #${clientId}`, [clientId]);

  return (
    <ProtectedPage>
      <AppShell title={`Sub Dashboard · ${subtitle}`}>
        <div className="mb-4 flex items-center gap-3 text-sm">
          <Link href={`/sub/${clientId}/campaigns`} className="text-indigo-600 hover:underline">Campaigns</Link>
          <Link href={`/sub/${clientId}/rules`} className="text-indigo-600 hover:underline">Rules</Link>
          <Link href={`/sub/${clientId}/creative`} className="text-indigo-600 hover:underline">Creative</Link>
          <Link href={`/sub/${clientId}/recommendations`} className="text-indigo-600 hover:underline">Recommendations</Link>
        </div>

        {error ? <p className="mb-4 text-sm text-red-600">{error}</p> : null}

        <section className="grid grid-cols-1 gap-4 md:grid-cols-3">
          <Card title="Spend" value={loading ? "..." : `$${totals.spend.toLocaleString()}`} />
          <Card title="Conversii" value={loading ? "..." : totals.conversions.toLocaleString()} />
          <Card title="ROAS" value={loading ? "..." : totals.roas.toFixed(2)} />
        </section>

        <section className="mt-6 grid grid-cols-1 gap-4 lg:grid-cols-2">
          <article className="wm-card p-4">
            <h3 className="text-sm font-semibold">Google Ads</h3>
            <p className="mt-2 text-sm text-slate-600">Spend: ${google.spend.toLocaleString()} · Conv: {google.conversions}</p>
            <button
              disabled={readOnly || busy !== null}
              onClick={() => sync("google")}
              className="mt-3 wm-btn-primary disabled:opacity-50"
              title={readOnly ? "Client viewer are acces read-only" : undefined}
            >
              {busy === "google" ? "Sync..." : "Sync Google"}
            </button>
          </article>

          <article className="wm-card p-4">
            <h3 className="text-sm font-semibold">Meta Ads</h3>
            <p className="mt-2 text-sm text-slate-600">Spend: ${meta.spend.toLocaleString()} · Conv: {meta.conversions}</p>
            <button
              disabled={readOnly || busy !== null}
              onClick={() => sync("meta")}
              className="mt-3 wm-btn-primary disabled:opacity-50"
              title={readOnly ? "Client viewer are acces read-only" : undefined}
            >
              {busy === "meta" ? "Sync..." : "Sync Meta"}
            </button>
          </article>
        </section>
      </AppShell>
    </ProtectedPage>
  );
}

function Card({ title, value }: { title: string; value: string }) {
  return (
    <article className="wm-card p-4">
      <p className="text-xs uppercase tracking-wide text-slate-500">{title}</p>
      <p className="mt-2 text-2xl font-semibold text-slate-900">{value}</p>
    </article>
  );
}
