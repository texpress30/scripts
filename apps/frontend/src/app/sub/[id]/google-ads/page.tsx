"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import React, { useEffect, useMemo, useState } from "react";
import { ArrowDownWideNarrow, Columns3, Download, Filter, RotateCcw } from "lucide-react";

import { AppShell } from "@/components/AppShell";
import { ProtectedPage } from "@/components/ProtectedPage";
import { apiRequest } from "@/lib/api";

type ClientItem = { id: number; display_id?: number; name: string };
type ClientDetails = {
  client: { id: number; display_id?: number; name: string };
  platforms: Array<{ platform: string; enabled: boolean; accounts: Array<{ id: string; name: string }> }>;
};
type MetricKey = "cost" | "rev_inf" | "roas_inf" | "mer_inf" | "truecac_inf" | "ecr_inf" | "ecpnv_inf" | "new_visits" | "visits";
type MetricRow = {
  accountId: string;
  accountName: string;
  healthy: boolean;
  values: Record<MetricKey, number>;
  deltaPct: Partial<Record<MetricKey, number>>;
};

const STORAGE_KEY = "sub-google-ads-visible-columns-v1";
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

function hashNumber(input: string): number {
  let hash = 0;
  for (let index = 0; index < input.length; index += 1) hash = (hash * 31 + input.charCodeAt(index)) >>> 0;
  return hash;
}

function formatMetric(value: number, key: MetricKey, money?: boolean): string {
  if (money) return new Intl.NumberFormat(undefined, { style: "currency", currency: "USD", maximumFractionDigits: 2 }).format(value);
  if (key === "roas_inf" || key === "mer_inf" || key === "ecr_inf") return value.toFixed(2);
  return Math.round(value).toLocaleString();
}

export default function SubGoogleAdsPage() {
  const params = useParams<{ id: string }>();
  const clientId = Number(params.id);
  const [clientName, setClientName] = useState<string>(`Sub-account #${clientId}`);
  const [rows, setRows] = useState<MetricRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [columnMenuOpen, setColumnMenuOpen] = useState(false);
  const [visibleColumns, setVisibleColumns] = useState<MetricKey[]>(DEFAULT_COLUMNS);
  const [selectedAccounts, setSelectedAccounts] = useState<string[]>([]);

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
        const displayId = currentClient?.display_id;
        if (!displayId) throw new Error("Nu am găsit sub-account-ul curent.");
        const details = await apiRequest<ClientDetails>(`/clients/display/${displayId}`);
        const googlePlatform = details.platforms.find((item) => item.platform === "google_ads");
        const accountRows: MetricRow[] = (googlePlatform?.accounts ?? []).map((account) => {
          const seed = hashNumber(account.id);
          const spend = 1800 + (seed % 5000);
          const revenue = spend * (1.5 + ((seed % 25) / 20));
          const visits = 4500 + (seed % 18000);
          const newVisits = Math.max(120, Math.round(visits * (0.18 + ((seed % 7) / 100))));
          const roas = revenue / spend;
          const mer = revenue > 0 ? spend / revenue : 0;
          const trueCac = spend / Math.max(1, newVisits * 0.12);
          const ecr = (newVisits / Math.max(1, visits)) * 100;
          const ecpnv = spend / Math.max(1, newVisits);
          const deltaFactor = ((seed % 21) - 10) / 10;
          return {
            accountId: account.id,
            accountName: account.name || account.id,
            healthy: seed % 4 !== 0,
            values: {
              cost: spend,
              rev_inf: revenue,
              roas_inf: roas,
              mer_inf: mer,
              truecac_inf: trueCac,
              ecr_inf: ecr,
              ecpnv_inf: ecpnv,
              new_visits: newVisits,
              visits: visits,
            },
            deltaPct: {
              cost: deltaFactor,
              rev_inf: -deltaFactor / 2,
              roas_inf: deltaFactor / 4,
              visits: -deltaFactor / 5,
            },
          };
        });

        if (!ignore) {
          setClientName(details.client.name || `Sub-account #${clientId}`);
          setRows(accountRows.sort((a, b) => b.values.cost - a.values.cost));
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
  }, [clientId]);

  const title = useMemo(() => `Google Ads - ${clientName}`, [clientName]);
  const allSelected = rows.length > 0 && selectedAccounts.length === rows.length;
  const activeColumns = METRIC_COLUMNS.filter((item) => visibleColumns.includes(item.key));

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
            </div>
          </header>

          {error ? <p className="mb-3 rounded-md border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</p> : null}
          {loading ? <p className="text-sm text-slate-500">Se încarcă performanța conturilor Google Ads...</p> : null}

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
                        const delta = row.deltaPct[column.key];
                        const alignClass = column.key === "cost" ? "text-right" : "text-center";
                        return (
                          <td key={`${row.accountId}:${column.key}`} className={`px-3 py-3 ${alignClass}`}>
                            <div className="inline-flex flex-col">
                              <span className={`${column.money ? "underline decoration-dotted underline-offset-2" : ""} font-medium text-slate-800`}>
                                {formatMetric(metricValue, column.key, column.money)}
                              </span>
                              {typeof delta === "number" ? (
                                <span className={`text-[11px] ${delta >= 0 ? "text-emerald-600" : "text-rose-600"}`}>
                                  {delta >= 0 ? "+" : ""}{(delta * 100).toFixed(1)}%
                                </span>
                              ) : null}
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
