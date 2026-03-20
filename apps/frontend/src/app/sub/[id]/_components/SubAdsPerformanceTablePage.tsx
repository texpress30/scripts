"use client";

import Link from "next/link";
import React, { useEffect, useMemo, useState } from "react";
import { ArrowDownWideNarrow, ArrowDown, ArrowUp, Columns3, Download, Filter, RotateCcw } from "lucide-react";
import { format, startOfMonth, subDays } from "date-fns";
import { DayPicker, type DateRange } from "react-day-picker";
import "react-day-picker/dist/style.css";

import { AppShell } from "@/components/AppShell";
import { ProtectedPage } from "@/components/ProtectedPage";
import { apiRequest, type SubGoogleAdsTableItem, type SubGoogleAdsTableResponse } from "@/lib/api";

type ClientItem = { id: number; display_id?: number; name: string };
type MetricKey = "cost" | "rev_inf" | "roas_inf" | "mer_inf" | "truecac_inf" | "ecr_inf" | "ecpnv_inf" | "new_visits" | "visits";
type MetricRow = {
  accountId: string;
  accountName: string;
  healthy: boolean;
  values: Record<MetricKey, number | null>;
};

const METRIC_COLUMNS: Array<{ key: MetricKey; label: string; money?: boolean }> = [
  { key: "cost", label: "Cost", money: true },
  { key: "rev_inf", label: "Rev (∞d)", money: true },
  { key: "roas_inf", label: "ROAS (∞d)" },
  { key: "mer_inf", label: "MER (∞d)" },
  { key: "truecac_inf", label: "TrueCAC (∞d)", money: true },
  { key: "ecr_inf", label: "ECR (∞d)" },
  { key: "ecpnv_inf", label: "eCPNV (∞d)", money: true },
  { key: "new_visits", label: "New Visits" },
  { key: "visits", label: "Visits" },
];
const DEFAULT_COLUMNS = METRIC_COLUMNS.map((item) => item.key);

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

function formatMetric(value: number | null, key: MetricKey, money: boolean | undefined, currencyCode: string): string {
  if (value === null || !Number.isFinite(value)) return "—";
  if (money) return new Intl.NumberFormat(undefined, { style: "currency", currency: currencyCode, maximumFractionDigits: 2 }).format(value);
  if (key === "roas_inf" || key === "mer_inf" || key === "ecr_inf") return value.toFixed(2);
  return Math.round(value).toLocaleString();
}

export function SubAdsPerformanceTablePage({
  clientId,
  platformTitle,
  platformDescription,
  storageKey,
  fetchTable,
}: {
  clientId: number;
  platformTitle: string;
  platformDescription: string;
  storageKey: string;
  fetchTable: (subaccountId: number, params: { start_date: string; end_date: string }) => Promise<SubGoogleAdsTableResponse>;
}) {
  const [clientName, setClientName] = useState<string>(`Sub-account #${clientId}`);
  const [rows, setRows] = useState<MetricRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [currencyCode, setCurrencyCode] = useState("USD");
  const [columnMenuOpen, setColumnMenuOpen] = useState(false);
  const [visibleColumns, setVisibleColumns] = useState<MetricKey[]>(DEFAULT_COLUMNS);
  const [selectedAccounts, setSelectedAccounts] = useState<string[]>([]);
  const initialRange = rangeForPreset("last30");
  const [openPicker, setOpenPicker] = useState(false);
  const [appliedPreset, setAppliedPreset] = useState<DatePresetKey>("last30");
  const [appliedRange, setAppliedRange] = useState<DateRange>(initialRange);
  const [draftPreset, setDraftPreset] = useState<DatePresetKey>("last30");
  const [draftRange, setDraftRange] = useState<DateRange>(initialRange);

  useEffect(() => {
    const stored = window.localStorage.getItem(storageKey);
    if (!stored) return;
    try {
      const parsed = JSON.parse(stored) as unknown;
      if (!Array.isArray(parsed)) return;
      const valid = parsed.filter((item): item is MetricKey => DEFAULT_COLUMNS.includes(item as MetricKey));
      if (valid.length > 0) setVisibleColumns(valid);
    } catch {
      // ignore invalid localStorage payload
    }
  }, [storageKey]);

  useEffect(() => {
    window.localStorage.setItem(storageKey, JSON.stringify(visibleColumns));
  }, [storageKey, visibleColumns]);

  useEffect(() => {
    let ignore = false;

    async function loadAccounts() {
      setLoading(true);
      setError("");
      try {
        const clients = await apiRequest<{ items: ClientItem[] }>("/clients");
        const currentClient = clients.items.find((item) => item.id === clientId);
        const from = appliedRange.from ?? subDays(new Date(), 29);
        const to = appliedRange.to ?? from;
        const payload = await fetchTable(clientId, { start_date: toIso(from), end_date: toIso(to) });
        const accountRows: MetricRow[] = payload.items.map((item: SubGoogleAdsTableItem) => {
          const status = String(item.status || "").trim().toLowerCase();
          const healthy = status === "active" || status === "connected" || status === "ok";
          return {
            accountId: item.account_id,
            accountName: item.account_name || item.account_id,
            healthy,
            values: {
              cost: item.cost ?? null,
              rev_inf: item.rev_inf ?? null,
              roas_inf: item.roas_inf ?? null,
              mer_inf: item.mer_inf ?? null,
              truecac_inf: item.truecac_inf ?? null,
              ecr_inf: item.ecr_inf ?? null,
              ecpnv_inf: item.ecpnv_inf ?? null,
              new_visits: item.new_visits ?? null,
              visits: item.visits ?? null,
            },
          };
        });

        if (!ignore) {
          setClientName(currentClient?.name || `Sub-account #${clientId}`);
          setCurrencyCode(String(payload.currency || "USD").toUpperCase());
          setRows(accountRows.sort((a, b) => (b.values.cost ?? 0) - (a.values.cost ?? 0)));
          setSelectedAccounts(accountRows.map((item) => item.accountId));
        }
      } catch (err) {
        if (!ignore) {
          setError(err instanceof Error ? err.message : `Nu am putut încărca datele ${platformTitle}.`);
        }
      } finally {
        if (!ignore) setLoading(false);
      }
    }

    if (Number.isFinite(clientId)) void loadAccounts();
    return () => {
      ignore = true;
    };
  }, [clientId, appliedRange.from, appliedRange.to, fetchTable, platformTitle]);

  const title = useMemo(() => `${platformTitle} - ${clientName}`, [platformTitle, clientName]);
  const allSelected = rows.length > 0 && selectedAccounts.length === rows.length;
  const activeColumns = visibleColumns
    .map((key) => METRIC_COLUMNS.find((column) => column.key === key))
    .filter((item): item is (typeof METRIC_COLUMNS)[number] => Boolean(item));
  const rangeLabel = formatRangeLabel(appliedPreset, appliedRange);

  function toggleAccount(accountId: string) {
    setSelectedAccounts((prev) => (prev.includes(accountId) ? prev.filter((item) => item !== accountId) : [...prev, accountId]));
  }

  function toggleColumn(metric: MetricKey) {
    setVisibleColumns((prev) => {
      if (prev.includes(metric)) return prev.filter((item) => item !== metric);
      return [...prev, metric];
    });
  }

  function moveColumn(metric: MetricKey, direction: -1 | 1) {
    setVisibleColumns((prev) => {
      const idx = prev.indexOf(metric);
      if (idx < 0) return prev;
      const nextIdx = idx + direction;
      if (nextIdx < 0 || nextIdx >= prev.length) return prev;
      const next = [...prev];
      const [item] = next.splice(idx, 1);
      next.splice(nextIdx, 0, item);
      return next;
    });
  }

  function setAllColumns() {
    setVisibleColumns(DEFAULT_COLUMNS);
  }

  function resetColumns() {
    setVisibleColumns(DEFAULT_COLUMNS);
  }

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

  function handleCancelRange() {
    setDraftPreset(appliedPreset);
    setDraftRange(appliedRange);
    setOpenPicker(false);
  }

  function handleApplyRange() {
    if (!draftRange.from || !draftRange.to) return;
    setAppliedPreset(draftPreset);
    setAppliedRange({ from: draftRange.from, to: draftRange.to });
    setOpenPicker(false);
  }

  return (
    <ProtectedPage>
      <AppShell title={null}>
        <div className="mb-4 flex items-center gap-4 text-sm">
          <Link href={`/sub/${clientId}/media-buying`} className="text-indigo-600 transition-colors hover:text-indigo-700 hover:underline">Media Buying</Link>
          <Link href={`/sub/${clientId}/media-tracker`} className="text-indigo-600 transition-colors hover:text-indigo-700 hover:underline">Media Tracker</Link>
        </div>

        <section className="wm-card p-4">
          <header className="mb-4 flex flex-wrap items-center justify-between gap-3">
            <div>
              <h1 className="text-xl font-semibold text-slate-900">{title}</h1>
              <p className="text-xs text-slate-500">{platformDescription}</p>
            </div>
            <div className="flex items-center gap-2">
              <button type="button" className="wm-btn-secondary inline-flex items-center gap-2"><Filter className="h-4 w-4" />Filter</button>
              <div className="relative">
                <button type="button" onClick={() => setColumnMenuOpen((current) => !current)} className="wm-btn-secondary inline-flex items-center gap-2"><Columns3 className="h-4 w-4" />Columns</button>
                {columnMenuOpen ? (
                  <div className="absolute right-0 z-20 mt-2 w-80 rounded-lg border border-slate-200 bg-white p-3 shadow-lg">
                    <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">Visible metrics</p>
                    <div className="mb-2 flex items-center justify-between text-[11px] text-slate-500">
                      <span>Change column order</span>
                    </div>
                    <div className="max-h-64 space-y-1 overflow-auto">
                      {METRIC_COLUMNS.map((column) => {
                        const idx = visibleColumns.indexOf(column.key);
                        const isVisible = idx >= 0;
                        return (
                          <div key={column.key} className="flex items-center justify-between gap-2 rounded px-1 py-1 hover:bg-slate-50">
                            <label className="flex items-center gap-2 text-sm text-slate-700">
                              <input type="checkbox" checked={isVisible} onChange={() => toggleColumn(column.key)} />
                              {column.label}
                            </label>
                            <div className="flex items-center gap-1">
                              <button
                                type="button"
                                aria-label={`Move ${column.label} up`}
                                onClick={() => moveColumn(column.key, -1)}
                                disabled={!isVisible || idx <= 0}
                                className="rounded border border-slate-200 p-1 text-slate-500 disabled:opacity-40"
                              >
                                <ArrowUp className="h-3 w-3" />
                              </button>
                              <button
                                type="button"
                                aria-label={`Move ${column.label} down`}
                                onClick={() => moveColumn(column.key, 1)}
                                disabled={!isVisible || idx < 0 || idx >= visibleColumns.length - 1}
                                className="rounded border border-slate-200 p-1 text-slate-500 disabled:opacity-40"
                              >
                                <ArrowDown className="h-3 w-3" />
                              </button>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                    <div className="mt-3 flex items-center justify-between border-t border-slate-100 pt-2">
                      <button type="button" onClick={setAllColumns} className="text-xs font-medium text-indigo-600 hover:text-indigo-700">Select All</button>
                      <button type="button" onClick={resetColumns} className="inline-flex items-center gap-1 text-xs font-medium text-slate-600 hover:text-slate-700"><RotateCcw className="h-3.5 w-3.5" />Reset to Default</button>
                    </div>
                  </div>
                ) : null}
              </div>
              <button type="button" className="wm-btn-secondary inline-flex items-center gap-2"><Download className="h-4 w-4" />Export</button>
              <div className="relative">
                <button type="button" onClick={() => setOpenPicker((current) => !current)} className="wm-btn-secondary whitespace-nowrap">
                  {rangeLabel}
                </button>
                {openPicker ? (
                  <div className="absolute right-0 z-30 mt-2 flex w-[760px] gap-4 rounded-xl border border-slate-200 bg-white p-4 shadow-xl">
                    <div className="w-48 border-r border-slate-200 pr-3">
                      <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">Presets</p>
                      <div className="space-y-1">
                        {PRESET_ITEMS.map((item) => (
                          <button
                            key={item.key}
                            type="button"
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
                        <button type="button" onClick={handleCancelRange} className="wm-btn-secondary">Cancel</button>
                        <button type="button" onClick={handleApplyRange} disabled={!draftRange.from || !draftRange.to} className="wm-btn-primary disabled:cursor-not-allowed disabled:opacity-60">Update</button>
                      </div>
                    </div>
                  </div>
                ) : null}
              </div>
            </div>
          </header>

          {error ? <p className="mb-3 rounded-md border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</p> : null}
          {loading ? <p className="text-sm text-slate-500">Se încarcă performanța conturilor {platformTitle}...</p> : null}

          {!loading ? (
            <div className="overflow-x-auto">
              <table className="min-w-full text-sm">
                <thead className="border-b border-slate-200 text-xs uppercase tracking-wide text-slate-500">
                  <tr>
                    <th className="px-3 py-2 text-left">
                      <label className="inline-flex items-center gap-2">
                        <input type="checkbox" checked={allSelected} onChange={() => setSelectedAccounts(allSelected ? [] : rows.map((item) => item.accountId))} />
                        Account
                      </label>
                    </th>
                    {activeColumns.map((column) => (
                      <th key={column.key} className={`px-3 py-2 ${column.key === "cost" ? "text-right font-semibold text-slate-700" : "text-center"}`}>
                        <span className="inline-flex items-center gap-1">
                          {column.label}
                          {column.key === "cost" ? <ArrowDownWideNarrow className="h-3.5 w-3.5 text-indigo-600" /> : null}
                        </span>
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row) => (
                    <tr key={row.accountId} className="border-b border-slate-100 hover:bg-slate-50/70">
                      <td className="px-3 py-3 text-left">
                        <div className="flex items-center gap-2">
                          <input type="checkbox" checked={selectedAccounts.includes(row.accountId)} onChange={() => toggleAccount(row.accountId)} />
                          <span className={`inline-flex h-2.5 w-2.5 rounded-full ${row.healthy ? "bg-emerald-500" : "bg-rose-500"}`} aria-hidden />
                          {!row.healthy ? <span className="rounded border border-rose-200 bg-rose-50 px-1 py-0.5 text-[10px] font-semibold text-rose-700">X</span> : null}
                          <span className="font-medium text-slate-900">{row.accountName}</span>
                        </div>
                      </td>
                      {activeColumns.map((column) => {
                        const metricValue = row.values[column.key];
                        const alignClass = column.key === "cost" ? "text-right" : "text-center";
                        return (
                          <td key={`${row.accountId}:${column.key}`} className={`px-3 py-3 ${alignClass}`}>
                            <div className="inline-flex flex-col">
                              <span className={`${column.money ? "underline decoration-dotted underline-offset-2" : ""} font-medium text-slate-800`}>
                                {formatMetric(metricValue, column.key, column.money, currencyCode)}
                              </span>
                            </div>
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : null}
        </section>
      </AppShell>
    </ProtectedPage>
  );
}
