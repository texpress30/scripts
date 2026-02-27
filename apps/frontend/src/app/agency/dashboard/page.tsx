"use client";

import { useEffect, useMemo, useState } from "react";

import { format, startOfMonth, subDays } from "date-fns";
import { DayPicker, type DateRange } from "react-day-picker";
import "react-day-picker/dist/style.css";

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

type DatePresetKey = "today" | "yesterday" | "last7" | "last30" | "month" | "custom";

const PRESET_ITEMS: Array<{ key: DatePresetKey; label: string }> = [
  { key: "today", label: "Today" },
  { key: "yesterday", label: "Yesterday" },
  { key: "last7", label: "Last 7 days" },
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

function statusTone(status: string): string {
  const normalized = status.toLowerCase();
  if (normalized === "connected") return "text-emerald-600";
  if (normalized === "disabled" || normalized === "inactive") return "text-slate-500";
  if (normalized === "error") return "text-red-600";
  return "text-slate-500";
}

export default function AgencyDashboardPage() {
  const [openPicker, setOpenPicker] = useState(false);

  const initialRange = rangeForPreset("last30");
  const [appliedPreset, setAppliedPreset] = useState<DatePresetKey>("last30");
  const [appliedRange, setAppliedRange] = useState<DateRange>(initialRange);

  const [draftPreset, setDraftPreset] = useState<DatePresetKey>("last30");
  const [draftRange, setDraftRange] = useState<DateRange>(initialRange);

  const [googleStatus, setGoogleStatus] = useState<IntegrationStatus | null>(null);
  const [summary, setSummary] = useState<AgencySummaryResponse | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  const appliedFrom = appliedRange.from ?? subDays(new Date(), 29);
  const appliedTo = appliedRange.to ?? appliedFrom;

  useEffect(() => {
    async function loadDashboard() {
      setLoading(true);
      setError("");
      try {
        const [google, agencySummary] = await Promise.all([
          apiRequest<IntegrationStatus>("/integrations/google-ads/status"),
          apiRequest<AgencySummaryResponse>(
            `/dashboard/agency/summary?start_date=${toIso(appliedFrom)}&end_date=${toIso(appliedTo)}`
          ),
        ]);

        setGoogleStatus(google);
        setSummary(agencySummary);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Nu am putut încărca dashboard-ul agency");
      } finally {
        setLoading(false);
      }
    }

    void loadDashboard();
  }, [appliedFrom, appliedTo]);

  const integrationSummary = useMemo(
    () => [
      { label: "Google Ads", status: googleStatus?.status ?? "error" },
      { label: "Meta Ads", status: "disabled" },
      { label: "TikTok Ads", status: "disabled" },
      { label: "Pinterest Ads", status: "disabled" },
      { label: "Snapchat Ads", status: "disabled" },
    ],
    [googleStatus?.status]
  );

  function handlePresetClick(nextPreset: DatePresetKey) {
    setDraftPreset(nextPreset);
    if (nextPreset === "custom") return;
    setDraftRange(rangeForPreset(nextPreset));
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

  return (
    <ProtectedPage>
      <AppShell title="Agency Dashboard">
        {error ? <p className="mb-4 text-sm text-red-600">{error}</p> : null}

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
      {loading ? <p className="mt-2 text-sm font-medium text-slate-500">Se încarcă datele...</p> : <p className="mt-2 text-2xl font-semibold text-slate-900">{value}</p>}
    </article>
  );
}
