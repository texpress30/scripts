"use client";

import { useEffect, useMemo, useState } from "react";

import { AppShell } from "@/components/AppShell";
import { ProtectedPage } from "@/components/ProtectedPage";
import { apiRequest } from "@/lib/api";

type ClientItem = {
  id: number;
  name: string;
  owner_email: string;
};

type ClientsResponse = { items: ClientItem[] };
type IntegrationStatus = { platform: string; status: string };

type DashboardResponse = {
  totals: {
    spend?: number;
    impressions?: number;
    clicks?: number;
    conversions?: number;
    revenue?: number;
    roas?: number;
  };
};

type NormalizedTotals = {
  spend: number;
  impressions: number;
  clicks: number;
  conversions: number;
  revenue: number;
  roas: number;
};

const ZERO_TOTALS: NormalizedTotals = { spend: 0, impressions: 0, clicks: 0, conversions: 0, revenue: 0, roas: 0 };

function safeNumber(value: unknown): number {
  return typeof value === "number" && Number.isFinite(value) ? value : 0;
}

function normalizeTotals(value?: DashboardResponse["totals"]): NormalizedTotals {
  const spend = safeNumber(value?.spend);
  const revenue = safeNumber(value?.revenue);
  return {
    spend,
    impressions: Math.max(0, Math.trunc(safeNumber(value?.impressions))),
    clicks: Math.max(0, Math.trunc(safeNumber(value?.clicks))),
    conversions: Math.max(0, Math.trunc(safeNumber(value?.conversions))),
    revenue,
    roas: spend > 0 ? revenue / spend : 0,
  };
}

export default function AgencyDashboardPage() {
  const [clients, setClients] = useState<ClientItem[]>([]);
  const [googleStatus, setGoogleStatus] = useState<IntegrationStatus | null>(null);
  const [metaStatus, setMetaStatus] = useState<IntegrationStatus | null>(null);
  const [tiktokStatus, setTiktokStatus] = useState<IntegrationStatus | null>(null);
  const [pinterestStatus, setPinterestStatus] = useState<IntegrationStatus | null>(null);
  const [snapchatStatus, setSnapchatStatus] = useState<IntegrationStatus | null>(null);
  const [totals, setTotals] = useState<NormalizedTotals>(ZERO_TOTALS);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let ignore = false;

    async function loadAgencyDashboard() {
      setLoading(true);
      setError("");

      try {
        const clientsResponse = await apiRequest<ClientsResponse>("/clients");
        if (ignore) return;

        setClients(clientsResponse.items);

        const [google, meta, tiktok, pinterest, snapchat] = await Promise.all([
          apiRequest<IntegrationStatus>("/integrations/google-ads/status"),
          apiRequest<IntegrationStatus>("/integrations/meta-ads/status"),
          apiRequest<IntegrationStatus>("/integrations/tiktok-ads/status"),
          apiRequest<IntegrationStatus>("/integrations/pinterest-ads/status"),
          apiRequest<IntegrationStatus>("/integrations/snapchat-ads/status"),
        ]);

        if (ignore) return;
        setGoogleStatus(google);
        setMetaStatus(meta);
        setTiktokStatus(tiktok);
        setPinterestStatus(pinterest);
        setSnapchatStatus(snapchat);

        const dashboardItems = await Promise.all(
          clientsResponse.items.map((client) => apiRequest<DashboardResponse>(`/dashboard/${client.id}`))
        );

        if (ignore) return;

        const aggregated = dashboardItems.reduce(
          (acc, item) => {
            const normalized = normalizeTotals(item.totals);
            acc.spend += normalized.spend;
            acc.impressions += normalized.impressions;
            acc.clicks += normalized.clicks;
            acc.conversions += normalized.conversions;
            acc.revenue += normalized.revenue;
            return acc;
          },
          { ...ZERO_TOTALS }
        );

        setTotals({
          spend: Number(aggregated.spend.toFixed(2)),
          impressions: aggregated.impressions,
          clicks: aggregated.clicks,
          conversions: aggregated.conversions,
          revenue: Number(aggregated.revenue.toFixed(2)),
          roas: aggregated.spend > 0 ? Number((aggregated.revenue / aggregated.spend).toFixed(2)) : 0,
        });
      } catch (err) {
        if (!ignore) {
          setError(err instanceof Error ? err.message : "Nu am putut încărca dashboard-ul agency");
        }
      } finally {
        if (!ignore) setLoading(false);
      }
    }

    void loadAgencyDashboard();
    return () => {
      ignore = true;
    };
  }, []);

  const integrationSummary = useMemo(
    () => [
      { label: "Google Ads", status: googleStatus?.status ?? "unknown" },
      { label: "Meta Ads", status: metaStatus?.status ?? "unknown" },
      { label: "TikTok Ads", status: tiktokStatus?.status ?? "unknown" },
      { label: "Pinterest Ads", status: pinterestStatus?.status ?? "unknown" },
      { label: "Snapchat Ads", status: snapchatStatus?.status ?? "unknown" },
    ],
    [
      googleStatus?.status,
      metaStatus?.status,
      tiktokStatus?.status,
      pinterestStatus?.status,
      snapchatStatus?.status,
    ]
  );

  return (
    <ProtectedPage>
      <AppShell title="Agency Dashboard">
        {error ? <p className="mb-4 text-sm text-red-600">{error}</p> : null}

        <section className="grid grid-cols-1 gap-4 md:grid-cols-4 xl:grid-cols-7">
          <Card title="Clienți activi" value={loading ? "..." : String(clients.length)} />
          <Card title="Spend total" value={loading ? "..." : `$${totals.spend.toLocaleString(undefined, { maximumFractionDigits: 2 })}`} />
          <Card title="Impressions" value={loading ? "..." : totals.impressions.toLocaleString()} />
          <Card title="Clicks" value={loading ? "..." : totals.clicks.toLocaleString()} />
          <Card title="Conversii total" value={loading ? "..." : totals.conversions.toLocaleString()} />
          <Card title="Revenue total" value={loading ? "..." : `$${totals.revenue.toLocaleString(undefined, { maximumFractionDigits: 2 })}`} />
          <Card title="ROAS agregat" value={loading ? "..." : totals.roas.toFixed(2)} />
        </section>

        <section className="mt-6 overflow-x-auto wm-card p-4">
          <h3 className="text-sm font-semibold text-slate-900">Normalized totals</h3>
          <table className="mt-3 min-w-full text-left text-sm">
            <thead className="text-slate-500">
              <tr>
                <th className="py-2 pr-4">Spend</th>
                <th className="py-2 pr-4">Impressions</th>
                <th className="py-2 pr-4">Clicks</th>
                <th className="py-2 pr-4">Conversions</th>
                <th className="py-2 pr-4">Revenue</th>
                <th className="py-2 pr-4">ROAS</th>
              </tr>
            </thead>
            <tbody>
              <tr className="text-slate-900">
                <td className="py-2 pr-4">{loading ? "..." : `$${totals.spend.toLocaleString(undefined, { maximumFractionDigits: 2 })}`}</td>
                <td className="py-2 pr-4">{loading ? "..." : totals.impressions.toLocaleString()}</td>
                <td className="py-2 pr-4">{loading ? "..." : totals.clicks.toLocaleString()}</td>
                <td className="py-2 pr-4">{loading ? "..." : totals.conversions.toLocaleString()}</td>
                <td className="py-2 pr-4">{loading ? "..." : `$${totals.revenue.toLocaleString(undefined, { maximumFractionDigits: 2 })}`}</td>
                <td className="py-2 pr-4">{loading ? "..." : totals.roas.toFixed(2)}</td>
              </tr>
            </tbody>
          </table>
        </section>

        <section className="mt-6 grid grid-cols-1 gap-4 lg:grid-cols-2">
          <article className="wm-card p-4">
            <h3 className="text-sm font-semibold text-slate-900">Integration health</h3>
            <ul className="mt-3 space-y-2 text-sm text-slate-600">
              {integrationSummary.map((item) => (
                <li key={item.label} className="flex items-center justify-between">
                  <span>{item.label}</span>
                  <span className="font-medium text-slate-900">{item.status}</span>
                </li>
              ))}
            </ul>
          </article>

          <article className="wm-card p-4">
            <h3 className="text-sm font-semibold text-slate-900">Top clienți (după spend)</h3>
            <ul className="mt-3 space-y-2 text-sm text-slate-600">
              {clients.slice(0, 5).map((client) => (
                <li key={client.id} className="flex items-center justify-between">
                  <span>{client.name}</span>
                  <span className="text-slate-500">#{client.id}</span>
                </li>
              ))}
              {!loading && clients.length === 0 ? <li>Nu există clienți.</li> : null}
            </ul>
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
