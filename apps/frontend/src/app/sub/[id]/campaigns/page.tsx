"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import { AppShell } from "@/components/AppShell";
import { ProtectedPage } from "@/components/ProtectedPage";
import { apiRequest } from "@/lib/api";
import { getCurrentRole, isReadOnlyRole } from "@/lib/session";

type PlatformMetrics = {
  spend?: number;
  impressions?: number;
  clicks?: number;
  conversions?: number;
  revenue?: number;
  roas?: number;
};

type DashboardResponse = {
  totals?: PlatformMetrics;
  platforms?: {
    google_ads?: PlatformMetrics;
    meta_ads?: PlatformMetrics;
    tiktok_ads?: PlatformMetrics;
    pinterest_ads?: PlatformMetrics;
    snapchat_ads?: PlatformMetrics;
  };
};

type NormalizedMetrics = {
  spend: number;
  impressions: number;
  clicks: number;
  conversions: number;
  revenue: number;
  roas: number;
};

function safeNumber(value: unknown): number {
  return typeof value === "number" && Number.isFinite(value) ? value : 0;
}

function normalizeMetrics(value?: PlatformMetrics): NormalizedMetrics {
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

export default function SubCampaignsPage() {
  const params = useParams<{ id: string }>();
  const clientId = Number(params.id);
  const role = getCurrentRole();
  const readOnly = isReadOnlyRole(role);
  const [result, setResult] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState<boolean>(false);
  const [loadingMetrics, setLoadingMetrics] = useState(true);
  const [metricsData, setMetricsData] = useState<DashboardResponse | null>(null);

  async function loadMetrics() {
    setLoadingMetrics(true);
    try {
      const data = await apiRequest<DashboardResponse>(`/dashboard/${clientId}`);
      setMetricsData(data);
    } catch {
      setMetricsData(null);
    } finally {
      setLoadingMetrics(false);
    }
  }

  useEffect(() => {
    if (Number.isFinite(clientId)) void loadMetrics();
  }, [clientId]);

  async function action(name: "evaluate") {
    setError("");
    setResult("");
    setBusy(true);
    try {
      if (name === "evaluate") await apiRequest(`/rules/${clientId}/evaluate`, { method: "POST" });
      setResult(`Acțiunea ${name} a fost executată.`);
      await loadMetrics();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Acțiunea a eșuat");
    } finally {
      setBusy(false);
    }
  }

  const totals = normalizeMetrics(metricsData?.totals);
  const platformRows: Array<[string, NormalizedMetrics]> = [
    ["Google Ads", normalizeMetrics(metricsData?.platforms?.google_ads)],
    ["Meta Ads", normalizeMetrics(metricsData?.platforms?.meta_ads)],
    ["TikTok Ads", normalizeMetrics(metricsData?.platforms?.tiktok_ads)],
    ["Pinterest Ads", normalizeMetrics(metricsData?.platforms?.pinterest_ads)],
    ["Snapchat Ads", normalizeMetrics(metricsData?.platforms?.snapchat_ads)],
  ];

  return (
    <ProtectedPage>
      <AppShell title={`Sub Campaigns · #${clientId}`}>
        <div className="mb-4 flex items-center gap-3 text-sm">
          <Link href={`/sub/${clientId}/dashboard`} className="text-indigo-600 hover:underline">Dashboard</Link>
          <Link href={`/sub/${clientId}/rules`} className="text-indigo-600 hover:underline">Rules</Link>
        </div>

        {error ? <p className="mb-3 text-sm text-red-600">{error}</p> : null}
        {result ? <p className="mb-3 text-sm text-emerald-600">{result}</p> : null}

        <section className="wm-card mb-4 overflow-x-auto p-4">
          <h3 className="text-sm font-semibold text-slate-900">Normalized totals</h3>
          <table className="mt-2 min-w-full text-left text-sm">
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
                <td className="py-2 pr-4">{loadingMetrics ? "..." : `$${totals.spend.toLocaleString(undefined, { maximumFractionDigits: 2 })}`}</td>
                <td className="py-2 pr-4">{loadingMetrics ? "..." : totals.impressions.toLocaleString()}</td>
                <td className="py-2 pr-4">{loadingMetrics ? "..." : totals.clicks.toLocaleString()}</td>
                <td className="py-2 pr-4">{loadingMetrics ? "..." : totals.conversions.toLocaleString()}</td>
                <td className="py-2 pr-4">{loadingMetrics ? "..." : `$${totals.revenue.toLocaleString(undefined, { maximumFractionDigits: 2 })}`}</td>
                <td className="py-2 pr-4">{loadingMetrics ? "..." : totals.roas.toFixed(2)}</td>
              </tr>
            </tbody>
          </table>
        </section>

        <section className="wm-card mb-4 overflow-x-auto p-4">
          <h3 className="text-sm font-semibold text-slate-900">Platform metrics</h3>
          <table className="mt-2 min-w-full text-left text-sm">
            <thead className="text-slate-500">
              <tr>
                <th className="py-2 pr-4">Platform</th>
                <th className="py-2 pr-4">Spend</th>
                <th className="py-2 pr-4">Impressions</th>
                <th className="py-2 pr-4">Clicks</th>
                <th className="py-2 pr-4">Conversions</th>
                <th className="py-2 pr-4">Revenue</th>
                <th className="py-2 pr-4">ROAS</th>
              </tr>
            </thead>
            <tbody>
              {platformRows.map(([platform, m]) => (
                <tr key={platform} className="border-t border-slate-200 text-slate-900">
                  <td className="py-2 pr-4">{platform}</td>
                  <td className="py-2 pr-4">{loadingMetrics ? "..." : `$${m.spend.toLocaleString(undefined, { maximumFractionDigits: 2 })}`}</td>
                  <td className="py-2 pr-4">{loadingMetrics ? "..." : m.impressions.toLocaleString()}</td>
                  <td className="py-2 pr-4">{loadingMetrics ? "..." : m.clicks.toLocaleString()}</td>
                  <td className="py-2 pr-4">{loadingMetrics ? "..." : m.conversions.toLocaleString()}</td>
                  <td className="py-2 pr-4">{loadingMetrics ? "..." : `$${m.revenue.toLocaleString(undefined, { maximumFractionDigits: 2 })}`}</td>
                  <td className="py-2 pr-4">{loadingMetrics ? "..." : m.roas.toFixed(2)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>

        <section className="grid grid-cols-1 gap-4 md:grid-cols-1">
          <ActionCard
            title="Evaluate Rules"
            disabled={readOnly || busy}
            description="Evaluează regulile active pentru acest sub-account"
            onClick={() => action("evaluate")}
          />
        </section>
      </AppShell>
    </ProtectedPage>
  );
}

function ActionCard({
  title,
  description,
  onClick,
  disabled,
}: {
  title: string;
  description: string;
  onClick: () => void;
  disabled: boolean;
}) {
  return (
    <article className="wm-card p-4">
      <h3 className="text-sm font-semibold">{title}</h3>
      <p className="mt-2 text-sm text-slate-600">{description}</p>
      <button
        disabled={disabled}
        onClick={onClick}
        className="mt-4 wm-btn-primary disabled:opacity-50"
        title={disabled ? "Disponibil doar pentru roluri cu write" : undefined}
      >
        Execută
      </button>
    </article>
  );
}
