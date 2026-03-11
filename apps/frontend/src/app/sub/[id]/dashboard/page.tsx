"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import React, { useEffect, useState } from "react";

import { format, startOfMonth, subDays } from "date-fns";
import { DayPicker, type DateRange } from "react-day-picker";
import "react-day-picker/dist/style.css";

import { AppShell } from "@/components/AppShell";
import { ProtectedPage } from "@/components/ProtectedPage";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { apiRequest } from "@/lib/api";

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
};

type NormalizedMetrics = {
  spend: number;
  impressions: number;
  clicks: number;
  conversions: number;
  revenue: number;
  roas: number;
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
  };
}

export default function SubDashboardPage() {
  const params = useParams<{ id: string }>();
  const clientId = Number(params.id);
  const [data, setData] = useState<DashboardResponse | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  const initialRange = rangeForPreset("last30");
  const [openPicker, setOpenPicker] = useState(false);
  const [appliedPreset, setAppliedPreset] = useState<DatePresetKey>("last30");
  const [appliedRange, setAppliedRange] = useState<DateRange>(initialRange);
  const [draftPreset, setDraftPreset] = useState<DatePresetKey>("last30");
  const [draftRange, setDraftRange] = useState<DateRange>(initialRange);

  const appliedFrom = appliedRange.from ?? subDays(new Date(), 29);
  const appliedTo = appliedRange.to ?? appliedFrom;

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
    if (Number.isFinite(clientId)) void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [clientId, appliedFrom, appliedTo]);

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

  return (
    <ProtectedPage>
      <AppShell title={null}>
        <div className="mb-4 flex items-center gap-4 text-sm">
          <Link href={`/sub/${clientId}/media-buying`} className="text-indigo-600 transition-colors hover:text-indigo-700 hover:underline">Media Buying</Link>
          <Link href={`/sub/${clientId}/media-tracker`} className="text-indigo-600 transition-colors hover:text-indigo-700 hover:underline">Media Tracker</Link>
        </div>

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
                <DayPicker
                  mode="range"
                  numberOfMonths={2}
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
                return (
                  <tr key={name} className="border-t border-slate-200 text-slate-900">
                    <td className="px-4 py-3">
                      <Link href={`/sub/${clientId}/${slug}`} className="text-slate-900 transition-colors hover:text-indigo-700 hover:underline">
                        {name}
                      </Link>
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
