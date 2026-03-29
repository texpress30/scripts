"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import React, { useEffect, useState } from "react";
import dynamic from "next/dynamic";

import { format, startOfMonth, subDays } from "date-fns";
import type { DateRange } from "react-day-picker";

import { AppShell } from "@/components/AppShell";
import { ProtectedPage } from "@/components/ProtectedPage";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { apiRequest, getSubaccountMyAccess } from "@/lib/api";
import { derivePlatformSyncStatus } from "@/lib/accountSyncStatus";
import { SubReportingNav } from "@/app/sub/[id]/_components/SubReportingNav";

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
  platform_sync_summary?: {
    meta_ads?: { accounts?: Array<Record<string, unknown>> };
    tiktok_ads?: { accounts?: Array<Record<string, unknown>> };
  };
  spend_by_day?: Array<{
    date?: string;
    spend?: number;
    platform_spend?: {
      google_ads?: number;
      meta_ads?: number;
      tiktok_ads?: number;
      pinterest_ads?: number;
      snapchat_ads?: number;
    };
  }>;
};

type PlatformMetrics = {
  spend?: number;
  impressions?: number;
  clicks?: number;
  conversions?: number;
  revenue?: number;
  roas?: number;
};

type NormalizedMetrics = {
  spend: number;
  impressions: number;
  clicks: number;
  conversions: number;
  revenue: number;
  roas: number;
};
type SpendByDayPoint = {
  date: string;
  spend: number;
  platform_spend: {
    google_ads: number;
    meta_ads: number;
    tiktok_ads: number;
    pinterest_ads: number;
    snapchat_ads: number;
  };
};

type DatePresetKey = "today" | "yesterday" | "last7" | "last14" | "last30" | "month" | "custom";

const PRESET_ITEMS: Array<{ key: DatePresetKey; label: string }> = [
  { key: "today", label: "Today" },
  { key: "yesterday", label: "Yesterday" },
  { key: "last7", label: "Last 7 days" },
  { key: "last14", label: "Last 14 days" },
  { key: "last30", label: "Last 30 days" },
  { key: "month", label: "This month" },
  { key: "custom", label: "Custom" },
];
const SUBACCOUNT_MODULE_ORDER = ["dashboard", "campaigns", "rules", "creative", "recommendations"] as const;

const DayRangePicker = dynamic(() => import("@/components/DayRangePicker").then((m) => m.DayRangePicker), { ssr: false });
const SubDashboardCharts = dynamic(
  () => import("@/app/sub/[id]/_components/SubDashboardCharts").then((m) => m.SubDashboardCharts),
  { ssr: false },
);

function toIso(value: Date): string {
  return format(value, "yyyy-MM-dd");
}

function rangeForPreset(preset: DatePresetKey): DateRange {
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  if (preset === "today") return { from: today, to: today };
  if (preset === "yesterday") {
    const y = subDays(today, 1);
    return { from: y, to: y };
  }
  if (preset === "last7") return { from: subDays(today, 6), to: today };
  if (preset === "last14") return { from: subDays(today, 13), to: today };
  if (preset === "last30") return { from: subDays(today, 29), to: today };
  if (preset === "month") return { from: startOfMonth(today), to: today };
  return { from: subDays(today, 29), to: today };
}

function formatRangeLabel(preset: DatePresetKey, range: DateRange): string {
  const from = range.from ?? new Date();
  const to = range.to ?? range.from ?? new Date();
  const presetLabel = PRESET_ITEMS.find((item) => item.key === preset)?.label ?? "Custom";
  return `${presetLabel}: ${format(from, "MMM d, yyyy")} - ${format(to, "MMM d, yyyy")}`;
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
  };
}

function normalizeSpendByDay(value: DashboardResponse["spend_by_day"]): SpendByDayPoint[] {
  return (value ?? [])
    .map((item) => ({
      date: typeof item?.date === "string" ? item.date : "",
      spend: safeNumber(item?.spend),
      platform_spend: {
        google_ads: safeNumber(item?.platform_spend?.google_ads),
        meta_ads: safeNumber(item?.platform_spend?.meta_ads),
        tiktok_ads: safeNumber(item?.platform_spend?.tiktok_ads),
        pinterest_ads: safeNumber(item?.platform_spend?.pinterest_ads),
        snapchat_ads: safeNumber(item?.platform_spend?.snapchat_ads),
      },
    }))
    .filter((item) => item.date !== "");
}

const STATUS_STYLES: Record<string, string> = {
  healthy: "bg-emerald-50 text-emerald-700 border-emerald-200",
  warning: "bg-amber-50 text-amber-700 border-amber-200",
  error: "bg-rose-50 text-rose-700 border-rose-200",
  unknown: "bg-slate-100 text-slate-600 border-slate-200",
};

export default function SubDashboardPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const clientId = Number(params.id);
  const [data, setData] = useState<DashboardResponse | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [accessGuardReady, setAccessGuardReady] = useState(false);

  const initialRange = rangeForPreset("last30");
  const [openPicker, setOpenPicker] = useState(false);
  const [appliedPreset, setAppliedPreset] = useState<DatePresetKey>("last30");
  const [appliedRange, setAppliedRange] = useState<DateRange>(initialRange);
  const [draftPreset, setDraftPreset] = useState<DatePresetKey>("last30");
  const [draftRange, setDraftRange] = useState<DateRange>(initialRange);
  const [detailsOpen, setDetailsOpen] = useState(false);

  const appliedFrom = appliedRange.from ?? subDays(new Date(), 29);
  const appliedTo = appliedRange.to ?? appliedFrom;

  useEffect(() => {
    if (!Number.isFinite(clientId)) {
      setAccessGuardReady(true);
      return;
    }

    let ignore = false;
    let redirected = false;
    setAccessGuardReady(false);
    async function validateDashboardAccess() {
      try {
        const access = await getSubaccountMyAccess(clientId);
        const allowedModules = new Set((access.module_keys ?? []).map((item) => String(item || "").trim().toLowerCase()));
        if (!allowedModules.has("dashboard")) {
          const firstAllowed = SUBACCOUNT_MODULE_ORDER.find((moduleKey) => allowedModules.has(moduleKey));
          const target = firstAllowed ? `/sub/${clientId}/${firstAllowed}` : "/agency/dashboard";
          redirected = true;
          router.replace(target);
          return;
        }
      } catch {
        // AppShell guard still handles API failures.
      } finally {
        if (!ignore && !redirected) setAccessGuardReady(true);
      }
    }
    void validateDashboardAccess();

    return () => {
      ignore = true;
    };
  }, [clientId, router]);

  async function load() {
    setLoading(true);
    setError("");
    try {
      const rangeNonce = `${toIso(appliedFrom)}_${toIso(appliedTo)}_${Date.now()}`;
      const result = await apiRequest<DashboardResponse>(
        `/dashboard/${clientId}?start_date=${toIso(appliedFrom)}&end_date=${toIso(appliedTo)}&_=${encodeURIComponent(rangeNonce)}`
      );
      setData(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Nu pot încărca dashboard-ul clientului");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (accessGuardReady && Number.isFinite(clientId)) void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [clientId, appliedFrom, appliedTo, accessGuardReady]);

  function handlePresetClick(nextPreset: DatePresetKey) {
    setDraftPreset(nextPreset);
    if (nextPreset === "custom") return;

    const nextRange = rangeForPreset(nextPreset);
    setDraftRange(nextRange);
    if (nextRange.from && nextRange.to) {
      setAppliedPreset(nextPreset);
      setAppliedRange(nextRange);
      setOpenPicker(false);
    }
  }

  function handleCancel() {
    setDraftPreset(appliedPreset);
    setDraftRange(appliedRange);
    setOpenPicker(false);
  }

  function handleUpdate() {
    if (!draftRange.from || !draftRange.to) return;
    setAppliedPreset(draftPreset);
    setAppliedRange({ from: draftRange.from, to: draftRange.to });
    setOpenPicker(false);
  }

  const label = formatRangeLabel(appliedPreset, appliedRange);

  const currencyCode = normalizeCurrencyCode(data?.currency);
  const totals = normalizeMetrics(data?.totals);
  const google = normalizeMetrics(data?.platforms.google_ads);
  const meta = normalizeMetrics(data?.platforms.meta_ads);
  const tiktok = normalizeMetrics(data?.platforms.tiktok_ads);
  const pinterest = normalizeMetrics(data?.platforms.pinterest_ads);
  const snapchat = normalizeMetrics(data?.platforms.snapchat_ads);

  const metaSync = derivePlatformSyncStatus("meta_ads", data?.platform_sync_summary?.meta_ads?.accounts ?? []);
  const tiktokSync = derivePlatformSyncStatus("tiktok_ads", data?.platform_sync_summary?.tiktok_ads?.accounts ?? []);
  const flaggedPlatforms = [metaSync, tiktokSync].filter((item) => item.uiStatus === "warning" || item.uiStatus === "error");
  const flaggedPlatformCount = flaggedPlatforms.length;
  const affectedAccountCount = flaggedPlatforms.reduce((sum, item) => sum + item.affectedAccountCount, 0);
  const spendByDay = normalizeSpendByDay(data?.spend_by_day);
  const hasSpendByDay = spendByDay.some((item) => item.spend > 0);
  const spendByPlatformTimeline = spendByDay.map((item) => ({
    date: item.date,
    google_ads: item.platform_spend.google_ads,
    meta_ads: item.platform_spend.meta_ads,
    tiktok_ads: item.platform_spend.tiktok_ads,
  }));
  const hasPlatformTimeline = spendByPlatformTimeline.some((item) => item.google_ads > 0 || item.meta_ads > 0 || item.tiktok_ads > 0);

  return (
    <ProtectedPage>
      <AppShell title={null}>
        <SubReportingNav clientId={clientId} />

        <section className="relative mb-4 flex justify-end">
          <button
            onClick={() => setOpenPicker((prev) => !prev)}
            className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 shadow-sm hover:bg-slate-50"
          >
            {label}
          </button>

          {openPicker ? (
            <div className="absolute right-0 top-12 z-50 flex w-[820px] gap-4 rounded-xl border border-slate-200 bg-white p-4 shadow-xl">
              <div className="w-48 border-r border-slate-200 pr-3">
                <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">Presets</p>
                <div className="space-y-1">
                  {PRESET_ITEMS.map((item) => (
                    <button
                      key={item.key}
                      onClick={() => handlePresetClick(item.key)}
                      className={`w-full rounded-md px-2 py-2 text-left text-sm ${
                        draftPreset === item.key ? "bg-indigo-50 font-medium text-indigo-700" : "text-slate-700 hover:bg-slate-100"
                      }`}
                    >
                      {item.label}
                    </button>
                  ))}
                </div>
              </div>

              <div className="flex-1">
                <DayRangePicker
                  selected={draftRange}
                  onSelect={(range) => {
                    setDraftPreset("custom");
                    setDraftRange(range ?? { from: undefined, to: undefined });
                  }}
                  defaultMonth={draftRange.from}
                />

                <div className="mt-3 flex justify-end gap-2 border-t border-slate-200 pt-3">
                  <button onClick={handleCancel} className="rounded-md border border-slate-200 px-3 py-1.5 text-sm text-slate-700 hover:bg-slate-50">
                    Cancel
                  </button>
                  <button
                    onClick={handleUpdate}
                    disabled={!draftRange.from || !draftRange.to}
                    className="rounded-md bg-indigo-600 px-3 py-1.5 text-sm font-medium text-white disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    Update
                  </button>
                </div>
              </div>
            </div>
          ) : null}
        </section>

        {error ? <p className="mb-4 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p> : null}

        <section className="grid grid-cols-1 gap-4 md:grid-cols-3 xl:grid-cols-6">
          <MetricCard title="Spend" value={loading ? "..." : formatCurrency(totals.spend, currencyCode)} />
          <MetricCard title="Impressions" value={loading ? "..." : totals.impressions.toLocaleString()} />
          <MetricCard title="Clicks" value={loading ? "..." : totals.clicks.toLocaleString()} />
          <MetricCard title="Conversions" value={loading ? "..." : totals.conversions.toLocaleString()} />
          <MetricCard title="Revenue" value={loading ? "..." : formatCurrency(totals.revenue, currencyCode)} />
          <MetricCard title="ROAS" value={loading ? "..." : totals.roas.toFixed(2)} />
        </section>

        <section className="mt-6 grid grid-cols-1 gap-4 xl:grid-cols-2">
          <Card>
            <CardHeader>
              <CardTitle>Spend total pe zile</CardTitle>
            </CardHeader>
            <CardContent>
              {loading ? (
                <p className="text-sm text-slate-500">Se încarcă datele pentru grafic…</p>
              ) : !hasSpendByDay ? (
                <p className="text-sm text-slate-500">Nu există spend în perioada selectată.</p>
              ) : (
                <SubDashboardCharts mode="total" spendByDay={spendByDay} spendByPlatformTimeline={[]} currencyCode={currencyCode} />
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Spend pe platforme</CardTitle>
            </CardHeader>
            <CardContent>
              {loading ? (
                <p className="text-sm text-slate-500">Se încarcă datele pentru grafic…</p>
              ) : !hasPlatformTimeline ? (
                <p className="text-sm text-slate-500">Nu există spend pe platforme în perioada selectată.</p>
              ) : (
                <SubDashboardCharts mode="platform" spendByDay={[]} spendByPlatformTimeline={spendByPlatformTimeline} currencyCode={currencyCode} />
              )}
            </CardContent>
          </Card>
        </section>

        {flaggedPlatformCount > 0 ? (
          <section className="mt-4 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900">
            <button type="button" className="flex w-full items-center justify-between gap-2 text-left" onClick={() => setDetailsOpen((current) => !current)}>
              <span>Some platform totals may be incomplete due to sync issues.</span>
              <span className="text-xs font-medium">{flaggedPlatformCount} platform {flaggedPlatformCount === 1 ? "warning" : "warnings"} • {affectedAccountCount} affected account{affectedAccountCount === 1 ? "" : "s"}</span>
            </button>
            {detailsOpen ? (
              <div className="mt-2 space-y-2 border-t border-amber-200 pt-2 text-xs">
                {[{ name: "Meta Ads", summary: metaSync }, { name: "TikTok Ads", summary: tiktokSync }]
                  .filter((item) => item.summary.uiStatus === "warning" || item.summary.uiStatus === "error")
                  .map((item) => (
                    <div key={item.name}>
                      <p className="font-semibold text-amber-900">{item.name}</p>
                      <ul className="mt-1 space-y-1">
                        {item.summary.accounts
                          .filter((account) => account.ui.uiStatus === "warning" || account.ui.uiStatus === "error")
                          .map((account) => (
                            <li key={`${item.name}:${account.id}`} className="rounded border border-amber-200 bg-amber-100/60 px-2 py-1">
                              <div className="flex items-center justify-between gap-2">
                                <span className="font-medium text-amber-900">{account.name} ({account.id})</span>
                                <span className={`inline-flex items-center rounded-full border px-2 py-0.5 font-medium ${STATUS_STYLES[account.ui.uiStatus]}`}>{account.ui.uiLabel}</span>
                              </div>
                              <p className="truncate text-amber-800">{account.ui.shortReason ?? account.ui.details.coverageStatus ?? "Sync issue"}</p>
                              <p className="truncate text-amber-700">
                                {account.ui.details.lastSyncAt ? `Last sync: ${account.ui.details.lastSyncAt}` : "Last sync: n/a"}
                                {account.ui.details.requestedStartDate && account.ui.details.requestedEndDate ? ` · Requested: ${account.ui.details.requestedStartDate} → ${account.ui.details.requestedEndDate}` : ""}
                                {account.ui.details.firstPersistedDate && account.ui.details.lastPersistedDate ? ` · Persisted: ${account.ui.details.firstPersistedDate} → ${account.ui.details.lastPersistedDate}` : ""}
                                {account.ui.details.failedChunkCount !== undefined ? ` · Failed chunks: ${account.ui.details.failedChunkCount}` : ""}
                                {account.ui.details.retryAttempted !== undefined ? ` · Retry: ${account.ui.details.retryAttempted ? "yes" : "no"}` : ""}
                              </p>
                            </li>
                          ))}
                      </ul>
                    </div>
                  ))}
              </div>
            ) : null}
          </section>
        ) : null}

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
                ["Google Ads", "google-ads", google],
                ["Meta Ads", "meta-ads", meta],
                ["TikTok Ads", "tiktok-ads", tiktok],
                ["Pinterest Ads", "pinterest-ads", pinterest],
                ["Snapchat Ads", "snapchat-ads", snapchat],
              ] as Array<[string, string, NormalizedMetrics]>).map(([name, slug, m]) => {
                const platformSummary = name === "Meta Ads" ? metaSync : name === "TikTok Ads" ? tiktokSync : null;
                return (
                  <tr key={name} className="border-t border-slate-200 text-slate-900">
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <Link href={`/sub/${clientId}/${slug}`} className="text-slate-900 transition-colors hover:text-indigo-700 hover:underline">
                          {name}
                        </Link>
                        {platformSummary ? (
                          <button type="button" onClick={() => setDetailsOpen((current) => !current)} className={`inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium ${STATUS_STYLES[platformSummary.uiStatus]}`}>
                            {platformSummary.uiLabel}{platformSummary.affectedAccountCount > 0 ? ` (${platformSummary.affectedAccountCount})` : ""}
                          </button>
                        ) : null}
                      </div>
                    </td>
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
