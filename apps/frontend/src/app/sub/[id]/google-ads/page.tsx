"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import React, { useEffect, useMemo, useState } from "react";
import { ArrowDownWideNarrow, Columns3, Download, Filter, RotateCcw } from "lucide-react";
import { format, startOfMonth, subDays } from "date-fns";
import { DayPicker, type DateRange } from "react-day-picker";
import "react-day-picker/dist/style.css";

import { SubAdsPerformanceTablePage } from "../_components/SubAdsPerformanceTablePage";
import { getSubGoogleAdsTable } from "@/lib/api";

export default function SubGoogleAdsPage() {
  const params = useParams<{ id: string }>();
  const clientId = Number(params.id);
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
    const stored = window.localStorage.getItem(STORAGE_KEY);
    if (!stored) return;
    try {
      const parsed = JSON.parse(stored) as unknown;
      if (!Array.isArray(parsed)) return;
      const valid = parsed.filter((item): item is MetricKey => DEFAULT_COLUMNS.includes(item as MetricKey));
      if (valid.length > 0) setVisibleColumns(valid);
    } catch {
      // ignore invalid localStorage payload
    }
  }, []);

  useEffect(() => {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(visibleColumns));
  }, [visibleColumns]);

  useEffect(() => {
    let ignore = false;

    async function loadGoogleAccounts() {
      setLoading(true);
      setError("");
      try {
        const clients = await apiRequest<{ items: ClientItem[] }>("/clients");
        const currentClient = clients.items.find((item) => item.id === clientId);
        const from = appliedRange.from ?? subDays(new Date(), 29);
        const to = appliedRange.to ?? from;
        const payload = await getSubGoogleAdsTable(clientId, { start_date: toIso(from), end_date: toIso(to) });
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
          setError(err instanceof Error ? err.message : "Nu am putut încărca datele Google Ads.");
        }
      } finally {
        if (!ignore) setLoading(false);
      }
    }

    if (Number.isFinite(clientId)) void loadGoogleAccounts();
    return () => {
      ignore = true;
    };
  }, [clientId, appliedRange.from, appliedRange.to]);

  const title = useMemo(() => `Google Ads - ${clientName}`, [clientName]);
  const allSelected = rows.length > 0 && selectedAccounts.length === rows.length;
  const activeColumns = METRIC_COLUMNS.filter((item) => visibleColumns.includes(item.key));
  const rangeLabel = formatRangeLabel(appliedPreset, appliedRange);

  function toggleAccount(accountId: string) {
    setSelectedAccounts((prev) => (prev.includes(accountId) ? prev.filter((item) => item !== accountId) : [...prev, accountId]));
  }

  function toggleColumn(metric: MetricKey) {
    setVisibleColumns((prev) => (prev.includes(metric) ? prev.filter((item) => item !== metric) : [...prev, metric]));
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
              <p className="text-xs text-slate-500">Performance multi-account • Google Ads</p>
            </div>
            <div className="flex items-center gap-2">
              <button type="button" className="wm-btn-secondary inline-flex items-center gap-2"><Filter className="h-4 w-4" />Filter</button>
              <div className="relative">
                <button type="button" onClick={() => setColumnMenuOpen((current) => !current)} className="wm-btn-secondary inline-flex items-center gap-2"><Columns3 className="h-4 w-4" />Columns</button>
                {columnMenuOpen ? (
                  <div className="absolute right-0 z-20 mt-2 w-64 rounded-lg border border-slate-200 bg-white p-3 shadow-lg">
                    <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">Visible metrics</p>
                    <div className="max-h-56 space-y-1 overflow-auto">
                      {METRIC_COLUMNS.map((column) => (
                        <label key={column.key} className="flex items-center gap-2 text-sm text-slate-700">
                          <input type="checkbox" checked={visibleColumns.includes(column.key)} onChange={() => toggleColumn(column.key)} />
                          {column.label}
                        </label>
                      ))}
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
          {loading ? <p className="text-sm text-slate-500">Se încarcă performanța conturilor Google Ads...</p> : null}

  return (
    <SubAdsPerformanceTablePage
      clientId={clientId}
      platformTitle="Google Ads"
      platformDescription="Performance multi-account • Google Ads"
      storageKey="sub-google-ads-visible-columns-v1"
      fetchTable={getSubGoogleAdsTable}
    />
  );
}
