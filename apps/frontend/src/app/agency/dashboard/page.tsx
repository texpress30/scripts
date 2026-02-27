"use client";

import { useEffect, useMemo, useState } from "react";

import { AppShell } from "@/components/AppShell";
import { ProtectedPage } from "@/components/ProtectedPage";
import { apiRequest } from "@/lib/api";

type IntegrationStatus = { platform: string; status: string };

type AgencySummaryResponse = {
  date_range: { start_date: string; end_date: string };
  active_clients: number;
  totals: {
    spend: number;
    impressions: number;
    clicks: number;
    conversions: number;
    revenue: number;
    roas: number;
  };
  top_clients: Array<{ client_id: number; name: string; spend: number }>;
};

type DatePresetKey = "today" | "last7" | "last30" | "month" | "custom";

function isoDate(value: Date): string {
  return value.toISOString().slice(0, 10);
}

function startOfMonth(now: Date): Date {
  return new Date(now.getFullYear(), now.getMonth(), 1);
}

function resolvePresetRange(preset: DatePresetKey): { startDate: string; endDate: string } {
  const now = new Date();
  const end = isoDate(now);
  if (preset === "today") return { startDate: end, endDate: end };
  if (preset === "last30") {
    const start = new Date(now);
    start.setDate(start.getDate() - 29);
    return { startDate: isoDate(start), endDate: end };
  }
  if (preset === "month") return { startDate: isoDate(startOfMonth(now)), endDate: end };

  const start = new Date(now);
  start.setDate(start.getDate() - 6);
  return { startDate: isoDate(start), endDate: end };
}

function statusTone(status: string): string {
  const normalized = status.toLowerCase();
  if (normalized === "connected") return "text-emerald-600";
  if (normalized === "disabled") return "text-slate-500";
  if (normalized === "error") return "text-red-600";
  return "text-red-600";
}

export default function AgencyDashboardPage() {
  const defaultRange = resolvePresetRange("last7");
  const [preset, setPreset] = useState<DatePresetKey>("last7");
  const [startDate, setStartDate] = useState(defaultRange.startDate);
  const [endDate, setEndDate] = useState(defaultRange.endDate);

  const [googleStatus, setGoogleStatus] = useState<IntegrationStatus | null>(null);
  const [metaStatus, setMetaStatus] = useState<IntegrationStatus | null>(null);
  const [tiktokStatus, setTiktokStatus] = useState<IntegrationStatus | null>(null);
  const [pinterestStatus, setPinterestStatus] = useState<IntegrationStatus | null>(null);
  const [snapchatStatus, setSnapchatStatus] = useState<IntegrationStatus | null>(null);

  const [summary, setSummary] = useState<AgencySummaryResponse | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  async function loadDashboard(range: { startDate: string; endDate: string }) {
    setLoading(true);
    setError("");

    try {
      const [google, meta, tiktok, pinterest, snapchat, agencySummary] = await Promise.all([
        apiRequest<IntegrationStatus>("/integrations/google-ads/status"),
        apiRequest<IntegrationStatus>("/integrations/meta-ads/status"),
        apiRequest<IntegrationStatus>("/integrations/tiktok-ads/status"),
        apiRequest<IntegrationStatus>("/integrations/pinterest-ads/status"),
        apiRequest<IntegrationStatus>("/integrations/snapchat-ads/status"),
        apiRequest<AgencySummaryResponse>(`/dashboard/agency/summary?start_date=${range.startDate}&end_date=${range.endDate}`),
      ]);

      setGoogleStatus(google);
      setMetaStatus(meta);
      setTiktokStatus(tiktok);
      setPinterestStatus(pinterest);
      setSnapchatStatus(snapchat);
      setSummary(agencySummary);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Nu am putut încărca dashboard-ul agency");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadDashboard({ startDate, endDate });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const integrationSummary = useMemo(
    () => [
      { label: "Google Ads", status: googleStatus?.status ?? "error" },
      { label: "Meta Ads", status: metaStatus?.status ?? "error" },
      { label: "TikTok Ads", status: tiktokStatus?.status ?? "error" },
      { label: "Pinterest Ads", status: pinterestStatus?.status ?? "error" },
      { label: "Snapchat Ads", status: snapchatStatus?.status ?? "error" },
    ],
    [googleStatus?.status, metaStatus?.status, tiktokStatus?.status, pinterestStatus?.status, snapchatStatus?.status]
  );

  function onPresetChange(nextPreset: DatePresetKey) {
    setPreset(nextPreset);
    if (nextPreset === "custom") return;
    const range = resolvePresetRange(nextPreset);
    setStartDate(range.startDate);
    setEndDate(range.endDate);
  }

  return (
    <ProtectedPage>
      <AppShell title="Agency Dashboard">
        {error ? <p className="mb-4 text-sm text-red-600">{error}</p> : null}

        <section className="mb-4 flex flex-col items-start gap-2 rounded-xl border border-slate-200 bg-white p-3 md:ml-auto md:w-fit md:items-end">
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Date range</p>
          <div className="flex flex-wrap items-center gap-2">
            <select
              className="wm-input h-9 w-[200px]"
              value={preset}
              onChange={(e) => onPresetChange(e.target.value as DatePresetKey)}
            >
              <option value="today">Astăzi</option>
              <option value="last7">Ultimele 7 zile</option>
              <option value="last30">Ultimele 30 zile</option>
              <option value="month">Luna aceasta</option>
              <option value="custom">Custom range</option>
            </select>

            <input type="date" className="wm-input h-9" value={startDate} onChange={(e) => setStartDate(e.target.value)} />
            <input type="date" className="wm-input h-9" value={endDate} onChange={(e) => setEndDate(e.target.value)} />

            <button
              onClick={() => void loadDashboard({ startDate, endDate })}
              className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700"
            >
              Update
            </button>
          </div>
        </section>

        <section className="grid grid-cols-1 gap-4 md:grid-cols-4 xl:grid-cols-7">
          <Card title="Clienți activi" value={summary?.active_clients.toLocaleString() ?? "0"} loading={loading} />
          <Card title="Spend total" value={`$${(summary?.totals.spend ?? 0).toLocaleString(undefined, { maximumFractionDigits: 2 })}`} loading={loading} />
          <Card title="Impressions" value={(summary?.totals.impressions ?? 0).toLocaleString()} loading={loading} />
          <Card title="Clicks" value={(summary?.totals.clicks ?? 0).toLocaleString()} loading={loading} />
          <Card title="Conversii total" value={(summary?.totals.conversions ?? 0).toLocaleString()} loading={loading} />
          <Card title="Revenue total" value={`$${(summary?.totals.revenue ?? 0).toLocaleString(undefined, { maximumFractionDigits: 2 })}`} loading={loading} />
          <Card title="ROAS agregat" value={(summary?.totals.roas ?? 0).toFixed(2)} loading={loading} />
        </section>

        <section className="mt-6 grid grid-cols-1 gap-4 lg:grid-cols-2">
          <article className="wm-card p-4">
            <h3 className="text-sm font-semibold text-slate-900">Integration health</h3>
            <ul className="mt-3 space-y-2 text-sm text-slate-600">
              {integrationSummary.map((item) => (
                <li key={item.label} className="flex items-center justify-between">
                  <span>{item.label}</span>
                  <span className={`font-medium ${statusTone(item.status)}`}>{item.status}</span>
                </li>
              ))}
            </ul>
          </article>

          <article className="wm-card p-4">
            <h3 className="text-sm font-semibold text-slate-900">Top clienți (după spend)</h3>
            <ul className="mt-3 space-y-2 text-sm text-slate-600">
              {(summary?.top_clients ?? []).map((client) => (
                <li key={client.client_id} className="flex items-center justify-between">
                  <span>{client.name}</span>
                  <span className="text-slate-900">${client.spend.toLocaleString(undefined, { maximumFractionDigits: 2 })}</span>
                </li>
              ))}
              {!loading && (summary?.top_clients.length ?? 0) === 0 ? <li>Nu există clienți.</li> : null}
            </ul>
          </article>
        </section>
      </AppShell>
    </ProtectedPage>
  );
}

function Card({ title, value, loading }: { title: string; value: string; loading: boolean }) {
  return (
    <article className="wm-card p-4">
      <p className="text-xs uppercase tracking-wide text-slate-500">{title}</p>
      {loading ? <div className="mt-2 h-8 w-3/4 animate-pulse rounded bg-slate-200" /> : <p className="mt-2 text-2xl font-semibold text-slate-900">{value}</p>}
    </article>
  );
}
