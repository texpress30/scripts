"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import { AppShell } from "@/components/AppShell";
import { ProtectedPage } from "@/components/ProtectedPage";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { apiRequest } from "@/lib/api";
import { getCurrentRole, isReadOnlyRole } from "@/lib/session";

type DashboardResponse = {
  client_id: number;
  currency?: string;
  totals: {
    spend?: number;
    impressions?: number;
    clicks?: number;
    conversions?: number;
    revenue?: number;
    roas?: number;
  };
  platforms: {
    google_ads?: PlatformMetrics;
    meta_ads?: PlatformMetrics;
    tiktok_ads?: PlatformMetrics;
    pinterest_ads?: PlatformMetrics;
    snapchat_ads?: PlatformMetrics;
  };
};

type PlatformMetrics = {
  spend?: number;
  impressions?: number;
  clicks?: number;
  conversions?: number;
  revenue?: number;
  roas?: number;
  is_synced?: boolean;
};

type NormalizedMetrics = {
  spend: number;
  impressions: number;
  clicks: number;
  conversions: number;
  revenue: number;
  roas: number;
  isSynced: boolean;
};

function safeNumber(value: unknown): number {
  return typeof value === "number" && Number.isFinite(value) ? value : 0;
}


function normalizeCurrencyCode(value: string | undefined): string {
  const code = (value ?? "USD").toUpperCase();
  return code.length === 3 ? code : "USD";
}

function formatCurrency(value: number, currencyCode: string): string {
  return new Intl.NumberFormat(undefined, { style: "currency", currency: currencyCode, maximumFractionDigits: 2 }).format(value);
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
    isSynced: Boolean(value?.is_synced),
  };
}

export default function SubDashboardPage() {
  const params = useParams<{ id: string }>();
  const clientId = Number(params.id);
  const role = getCurrentRole();
  const readOnly = isReadOnlyRole(role);
  const [data, setData] = useState<DashboardResponse | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<"google" | "meta" | "tiktok" | "pinterest" | "snapchat" | null>(null);

  async function load() {
    setLoading(true);
    setError("");
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

  async function sync(channel: "google" | "meta" | "tiktok" | "pinterest" | "snapchat") {
    setBusy(channel);
    setError("");
    try {
      const path =
        channel === "google"
          ? `/integrations/google-ads/${clientId}/sync`
          : channel === "meta"
            ? `/integrations/meta-ads/${clientId}/sync`
            : channel === "tiktok"
              ? `/integrations/tiktok-ads/${clientId}/sync`
              : channel === "pinterest"
                ? `/integrations/pinterest-ads/${clientId}/sync`
                : `/integrations/snapchat-ads/${clientId}/sync`;
      await apiRequest(path, { method: "POST" });
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Sync eșuat");
    } finally {
      setBusy(null);
    }
  }

  const currencyCode = normalizeCurrencyCode(data?.currency);
  const totals = normalizeMetrics(data?.totals);
  const google = normalizeMetrics(data?.platforms.google_ads);
  const meta = normalizeMetrics(data?.platforms.meta_ads);
  const tiktok = normalizeMetrics(data?.platforms.tiktok_ads);
  const pinterest = normalizeMetrics(data?.platforms.pinterest_ads);
  const snapchat = normalizeMetrics(data?.platforms.snapchat_ads);

  return (
    <ProtectedPage>
      <AppShell title={`Sub-account Dashboard #${clientId}`}>
        <div className="mb-4 flex items-center gap-4 text-sm">
          <Link href={`/sub/${clientId}/campaigns`} className="text-indigo-600 hover:underline">Campaigns</Link>
          <Link href={`/sub/${clientId}/rules`} className="text-indigo-600 hover:underline">Rules</Link>
          <Link href={`/sub/${clientId}/creative`} className="text-indigo-600 hover:underline">Creative</Link>
          <Link href={`/sub/${clientId}/recommendations`} className="text-indigo-600 hover:underline">Recommendations</Link>
        </div>

        {error ? <p className="mb-4 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p> : null}

        <section className="grid grid-cols-1 gap-4 md:grid-cols-3 xl:grid-cols-6">
          <MetricCard title="Spend" value={loading ? "..." : formatCurrency(totals.spend, currencyCode)} />
          <MetricCard title="Impressions" value={loading ? "..." : totals.impressions.toLocaleString()} />
          <MetricCard title="Clicks" value={loading ? "..." : totals.clicks.toLocaleString()} />
          <MetricCard title="Conversions" value={loading ? "..." : totals.conversions.toLocaleString()} />
          <MetricCard title="Revenue" value={loading ? "..." : formatCurrency(totals.revenue, currencyCode)} />
          <MetricCard title="ROAS" value={loading ? "..." : totals.roas.toFixed(2)} />
        </section>

        <section className="mt-6 overflow-x-auto">
          <table className="min-w-full wm-card text-left text-sm">
            <thead className="text-slate-500">
              <tr>
                <th className="px-4 py-3">Platform</th>
                <th className="px-4 py-3">Spend</th>
                <th className="px-4 py-3">Impressions</th>
                <th className="px-4 py-3">Clicks</th>
                <th className="px-4 py-3">Conversions</th>
                <th className="px-4 py-3">Revenue</th>
                <th className="px-4 py-3">ROAS</th>
              </tr>
            </thead>
            <tbody>
              {([
                ["Google Ads", google],
                ["Meta Ads", meta],
                ["TikTok Ads", tiktok],
                ["Pinterest Ads", pinterest],
                ["Snapchat Ads", snapchat],
              ] as Array<[string, NormalizedMetrics]>).map(([name, m]) => {
                return (
                  <tr key={name} className="border-t border-slate-200 text-slate-900">
                    <td className="px-4 py-3">{name}</td>
                    <td className="px-4 py-3">{loading ? "..." : formatCurrency(m.spend, currencyCode)}</td>
                    <td className="px-4 py-3">{loading ? "..." : m.impressions.toLocaleString()}</td>
                    <td className="px-4 py-3">{loading ? "..." : m.clicks.toLocaleString()}</td>
                    <td className="px-4 py-3">{loading ? "..." : m.conversions.toLocaleString()}</td>
                    <td className="px-4 py-3">{loading ? "..." : formatCurrency(m.revenue, currencyCode)}</td>
                    <td className="px-4 py-3">{loading ? "..." : m.roas.toFixed(2)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </section>

        <section className="mt-6 grid grid-cols-1 gap-4 lg:grid-cols-5">
          <IntegrationCard
            title="Google Ads"
            spend={google.spend}
            impressions={google.impressions}
            clicks={google.clicks}
            conversions={google.conversions}
            revenue={google.revenue}
            roas={google.roas}
            currencyCode={currencyCode}
            loading={loading}
            synced={google.isSynced}
            buttonLabel={busy === "google" ? "Sync..." : "Sync Google"}
            disabled={readOnly || busy !== null}
            onSync={() => sync("google")}
          />
          <IntegrationCard
            title="Meta Ads"
            spend={meta.spend}
            impressions={meta.impressions}
            clicks={meta.clicks}
            conversions={meta.conversions}
            revenue={meta.revenue}
            roas={meta.roas}
            currencyCode={currencyCode}
            loading={loading}
            synced={meta.isSynced}
            buttonLabel={busy === "meta" ? "Sync..." : "Sync Meta"}
            disabled={readOnly || busy !== null}
            onSync={() => sync("meta")}
          />
          <IntegrationCard
            title="TikTok Ads"
            spend={tiktok.spend}
            impressions={tiktok.impressions}
            clicks={tiktok.clicks}
            conversions={tiktok.conversions}
            revenue={tiktok.revenue}
            roas={tiktok.roas}
            currencyCode={currencyCode}
            loading={loading}
            synced={tiktok.isSynced}
            buttonLabel={busy === "tiktok" ? "Sync..." : "Sync TikTok"}
            disabled={readOnly || busy !== null}
            onSync={() => sync("tiktok")}
          />
          <IntegrationCard
            title="Pinterest Ads"
            spend={pinterest.spend}
            impressions={pinterest.impressions}
            clicks={pinterest.clicks}
            conversions={pinterest.conversions}
            revenue={pinterest.revenue}
            roas={pinterest.roas}
            currencyCode={currencyCode}
            loading={loading}
            synced={pinterest.isSynced}
            buttonLabel={busy === "pinterest" ? "Sync..." : "Sync Pinterest"}
            disabled={readOnly || busy !== null}
            onSync={() => sync("pinterest")}
          />
          <IntegrationCard
            title="Snapchat Ads"
            spend={snapchat.spend}
            impressions={snapchat.impressions}
            clicks={snapchat.clicks}
            conversions={snapchat.conversions}
            revenue={snapchat.revenue}
            roas={snapchat.roas}
            currencyCode={currencyCode}
            loading={loading}
            synced={snapchat.isSynced}
            buttonLabel={busy === "snapchat" ? "Sync..." : "Sync Snapchat"}
            disabled={readOnly || busy !== null}
            onSync={() => sync("snapchat")}
          />
        </section>
      </AppShell>
    </ProtectedPage>
  );
}

function MetricCard({ title, value }: { title: string; value: string }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
      </CardHeader>
      <CardContent>
        <p className="text-2xl font-bold text-slate-900">{value}</p>
      </CardContent>
    </Card>
  );
}

function IntegrationCard({
  title,
  spend,
  impressions,
  clicks,
  conversions,
  revenue,
  roas,
  buttonLabel,
  currencyCode,
  disabled,
  onSync,
  loading,
  synced,
}: {
  title: string;
  spend: number;
  impressions: number;
  clicks: number;
  conversions: number;
  revenue: number;
  roas: number;
  buttonLabel: string;
  currencyCode: string;
  disabled: boolean;
  onSync: () => void;
  loading: boolean;
  synced: boolean;
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
      </CardHeader>
      <CardContent>
        <p className="text-sm text-slate-600">Status: {loading ? "Loading..." : synced ? "Synced" : "No data"}</p>
        <p className="text-sm text-slate-600">Spend: {loading ? "..." : formatCurrency(spend, currencyCode)}</p>
        <p className="text-sm text-slate-600">Impressions: {loading ? "..." : impressions.toLocaleString()}</p>
        <p className="text-sm text-slate-600">Clicks: {loading ? "..." : clicks.toLocaleString()}</p>
        <p className="text-sm text-slate-600">Conversions: {loading ? "..." : conversions.toLocaleString()}</p>
        <p className="text-sm text-slate-600">Revenue: {loading ? "..." : formatCurrency(revenue, currencyCode)}</p>
        <p className="text-sm text-slate-600">ROAS: {loading ? "..." : roas.toFixed(2)}</p>
        <button
          disabled={disabled}
          onClick={onSync}
          className="mt-4 h-9 rounded-md bg-indigo-600 px-4 text-sm font-medium text-white hover:bg-indigo-500 disabled:opacity-50"
          title={disabled ? "Read-only sau acțiune în progres" : undefined}
        >
          {buttonLabel}
        </button>
      </CardContent>
    </Card>
  );
}
