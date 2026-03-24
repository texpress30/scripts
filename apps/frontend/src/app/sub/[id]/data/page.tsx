"use client";

import { format, parse, startOfMonth, endOfMonth, addMonths } from "date-fns";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import React, { useEffect, useMemo, useState } from "react";

import { AppShell } from "@/components/AppShell";
import { ProtectedPage } from "@/components/ProtectedPage";
import { apiRequest } from "@/lib/api";
import { SubReportingNav } from "@/app/sub/[id]/_components/SubReportingNav";

type ClientItem = { id: number; name: string };

type FixedFieldConfig = {
  key: string;
  label: string;
};

type DynamicCustomFieldConfig = {
  id: number;
  field_key: string;
  label: string;
  value_kind?: "count" | "amount";
  sort_order?: number;
  is_active?: boolean;
};

type DataConfigResponse = {
  currency_code?: string;
  display_currency?: string;
  fixed_fields?: FixedFieldConfig[];
  dynamic_custom_fields?: DynamicCustomFieldConfig[];
  custom_fields?: DynamicCustomFieldConfig[];
};

type SaleEntryRow = {
  id?: number;
  brand?: string | null;
  model?: string | null;
  sale_price_amount?: number | string | null;
  actual_price_amount?: number | string | null;
  gross_profit_amount?: number | string | null;
  notes?: string | null;
};

type DynamicCustomValueRow = {
  custom_field_id: number;
  label?: string;
  value_kind?: "count" | "amount";
  numeric_value: number | string;
};

type DataTableRow = {
  daily_input_id?: number;
  metric_date: string;
  source?: string;
  source_label?: string;
  leads?: number;
  phones?: number;
  custom_value_1_count?: number;
  custom_value_2_count?: number;
  custom_value_3_amount?: number | string;
  custom_value_5_amount?: number | string;
  notes?: string | null;
  sales_count?: number;
  revenue_amount?: number | string;
  cogs_amount?: number | string;
  custom_value_4_amount?: number | string;
  gross_profit_amount?: number | string;
  derived?: {
    sales_count?: number;
    revenue_amount?: number | string;
    cogs_amount?: number | string;
    custom_value_4_amount?: number | string;
    gross_profit_amount?: number | string;
  };
  sale_entries?: SaleEntryRow[];
  dynamic_custom_values?: DynamicCustomValueRow[];
  custom_values?: DynamicCustomValueRow[];
};

type DataTableResponse = {
  rows: DataTableRow[];
};

const FIXED_FIELD_FALLBACK_LABELS: Record<string, string> = {
  leads: "Lead-uri",
  phones: "Telefoane",
  custom_value_1_count: "Custom 1",
  custom_value_2_count: "Custom 2",
  custom_value_3_amount: "Custom 3",
  custom_value_4_amount: "Custom 4",
  custom_value_5_amount: "Custom 5",
};

function parseMonthParam(value: string | null): Date {
  if (!value) return startOfMonth(new Date());
  const parsed = parse(value, "yyyy-MM", new Date());
  if (Number.isNaN(parsed.getTime())) return startOfMonth(new Date());
  return startOfMonth(parsed);
}

function formatAmount(value: number | string | null | undefined, currencyCode: string): string {
  if (value == null || value === "") return "—";
  const parsed = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(parsed)) return "—";
  return new Intl.NumberFormat("ro-RO", { style: "currency", currency: currencyCode, maximumFractionDigits: 2 }).format(parsed);
}

function formatCount(value: number | string | null | undefined): string {
  if (value == null || value === "") return "—";
  const parsed = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(parsed)) return "—";
  return Math.trunc(parsed).toLocaleString("ro-RO");
}

function formatMonthLabel(value: Date): string {
  return new Intl.DateTimeFormat("ro-RO", { month: "long", year: "numeric" }).format(value);
}

function normalizeFixedLabels(config: DataConfigResponse | null): Record<string, string> {
  const mapped: Record<string, string> = { ...FIXED_FIELD_FALLBACK_LABELS };
  for (const field of config?.fixed_fields ?? []) {
    const key = String(field?.key || "").trim();
    const label = String(field?.label || "").trim();
    if (key && label) mapped[key] = label;
  }
  return mapped;
}

function normalizeActiveDynamicFields(config: DataConfigResponse | null): DynamicCustomFieldConfig[] {
  const fields = (config?.dynamic_custom_fields ?? config?.custom_fields ?? []).slice();
  return fields
    .filter((field) => Boolean(field?.is_active ?? true))
    .sort((a, b) => (Number(a.sort_order ?? 0) - Number(b.sort_order ?? 0)) || (Number(a.id ?? 0) - Number(b.id ?? 0)));
}

function normalizeRowCustomValues(row: DataTableRow): DynamicCustomValueRow[] {
  return (row.dynamic_custom_values ?? row.custom_values ?? []).slice();
}

export default function SubDataPage() {
  const params = useParams<{ id: string }>();
  const clientId = Number(params.id);
  const router = useRouter();
  const searchParams = useSearchParams();

  const monthDate = useMemo(() => parseMonthParam(searchParams.get("month")), [searchParams]);
  const monthKey = useMemo(() => format(monthDate, "yyyy-MM"), [monthDate]);
  const dateFrom = useMemo(() => format(startOfMonth(monthDate), "yyyy-MM-dd"), [monthDate]);
  const dateTo = useMemo(() => format(endOfMonth(monthDate), "yyyy-MM-dd"), [monthDate]);

  const [clientName, setClientName] = useState("");
  const [config, setConfig] = useState<DataConfigResponse | null>(null);
  const [rows, setRows] = useState<DataTableRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const currencyCode = String(config?.currency_code || config?.display_currency || "USD").toUpperCase();
  const fixedLabels = useMemo(() => normalizeFixedLabels(config), [config]);
  const activeDynamicFields = useMemo(() => normalizeActiveDynamicFields(config), [config]);

  useEffect(() => {
    let ignore = false;

    async function loadClientName() {
      try {
        const result = await apiRequest<{ items: ClientItem[] }>("/clients");
        const match = result.items.find((item) => item.id === clientId);
        if (!ignore) setClientName(match?.name || "");
      } catch {
        if (!ignore) setClientName("");
      }
    }

    if (Number.isFinite(clientId)) void loadClientName();
    return () => {
      ignore = true;
    };
  }, [clientId]);

  useEffect(() => {
    let ignore = false;

    async function loadData() {
      if (!Number.isFinite(clientId)) return;
      setLoading(true);
      setError("");
      try {
        const [configPayload, tablePayload] = await Promise.all([
          apiRequest<DataConfigResponse>(`/clients/${clientId}/data/config`),
          apiRequest<DataTableResponse>(`/clients/${clientId}/data/table?date_from=${dateFrom}&date_to=${dateTo}`),
        ]);

        if (!ignore) {
          setConfig(configPayload ?? null);
          setRows(Array.isArray(tablePayload?.rows) ? tablePayload.rows : []);
        }
      } catch (err) {
        if (!ignore) {
          setConfig(null);
          setRows([]);
          setError(err instanceof Error ? err.message : "Nu am putut încărca datele.");
        }
      } finally {
        if (!ignore) setLoading(false);
      }
    }

    void loadData();

    return () => {
      ignore = true;
    };
  }, [clientId, dateFrom, dateTo]);

  function updateMonth(next: Date) {
    const paramsCopy = new URLSearchParams(searchParams.toString());
    paramsCopy.set("month", format(startOfMonth(next), "yyyy-MM"));
    router.replace(`/sub/${clientId}/data?${paramsCopy.toString()}`);
  }

  const title = clientName ? `Data - ${clientName}` : "Data";

  return (
    <ProtectedPage>
      <AppShell title={null}>
        <SubReportingNav clientId={clientId} />

        <section className="wm-card p-6">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h1 className="text-xl font-semibold text-slate-900">{title}</h1>
              <p className="mt-1 text-sm text-slate-600">{dateFrom} - {dateTo} · Currency: {currencyCode}</p>
            </div>
            <div className="flex items-center gap-2">
              <button
                type="button"
                className="rounded-md border border-slate-300 px-3 py-1.5 text-sm text-slate-700"
                onClick={() => updateMonth(addMonths(monthDate, -1))}
              >
                Previous
              </button>
              <span className="min-w-44 text-center text-sm font-medium text-slate-800">{formatMonthLabel(monthDate)}</span>
              <button
                type="button"
                className="rounded-md border border-slate-300 px-3 py-1.5 text-sm text-slate-700"
                onClick={() => updateMonth(addMonths(monthDate, 1))}
              >
                Next
              </button>
            </div>
          </div>

          {loading ? <p className="mt-4 text-sm text-slate-600">Loading data table...</p> : null}
          {!loading && error ? <p className="mt-4 rounded-md border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</p> : null}
          {!loading && !error && rows.length === 0 ? (
            <p className="mt-4 rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-600">Nu există date pentru perioada selectată.</p>
          ) : null}

          {!loading && !error && rows.length > 0 ? (
            <div className="mt-4 overflow-x-auto">
              <table className="min-w-full border-collapse text-sm">
                <thead>
                  <tr className="bg-slate-50 text-left text-slate-700">
                    <th className="border border-slate-200 px-3 py-2">Data</th>
                    <th className="border border-slate-200 px-3 py-2">Sursa</th>
                    <th className="border border-slate-200 px-3 py-2">{fixedLabels.leads}</th>
                    <th className="border border-slate-200 px-3 py-2">{fixedLabels.phones}</th>
                    <th className="border border-slate-200 px-3 py-2">{fixedLabels.custom_value_1_count}</th>
                    <th className="border border-slate-200 px-3 py-2">{fixedLabels.custom_value_2_count}</th>
                    <th className="border border-slate-200 px-3 py-2">{fixedLabels.custom_value_3_amount}</th>
                    <th className="border border-slate-200 px-3 py-2">{fixedLabels.custom_value_4_amount}</th>
                    <th className="border border-slate-200 px-3 py-2">{fixedLabels.custom_value_5_amount}</th>
                    {activeDynamicFields.map((field) => (
                      <th key={field.id} className="border border-slate-200 px-3 py-2">{field.label}</th>
                    ))}
                    <th className="border border-slate-200 px-3 py-2">Vânzări</th>
                    <th className="border border-slate-200 px-3 py-2">Venit</th>
                    <th className="border border-slate-200 px-3 py-2">COGS</th>
                    <th className="border border-slate-200 px-3 py-2">Profit Brut</th>
                    <th className="border border-slate-200 px-3 py-2">Mențiuni</th>
                    <th className="border border-slate-200 px-3 py-2">Detalii</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row) => {
                    const derived = row.derived ?? {};
                    const saleEntries = row.sale_entries ?? [];
                    const rowCustomValues = normalizeRowCustomValues(row);
                    const customValueByFieldId = new Map(rowCustomValues.map((item) => [Number(item.custom_field_id), item]));
                    const salesCount = derived.sales_count ?? row.sales_count;
                    const revenueAmount = derived.revenue_amount ?? row.revenue_amount;
                    const cogsAmount = derived.cogs_amount ?? row.cogs_amount;
                    const customValue4Amount = derived.custom_value_4_amount ?? row.custom_value_4_amount;
                    const grossProfitAmount = derived.gross_profit_amount ?? row.gross_profit_amount;

                    return (
                      <tr key={`${row.metric_date}:${row.source ?? "unknown"}:${row.daily_input_id ?? ""}`} className="align-top">
                        <td className="border border-slate-200 px-3 py-2">{row.metric_date}</td>
                        <td className="border border-slate-200 px-3 py-2">{row.source_label || "—"}</td>
                        <td className="border border-slate-200 px-3 py-2">{formatCount(row.leads)}</td>
                        <td className="border border-slate-200 px-3 py-2">{formatCount(row.phones)}</td>
                        <td className="border border-slate-200 px-3 py-2">{formatCount(row.custom_value_1_count)}</td>
                        <td className="border border-slate-200 px-3 py-2">{formatCount(row.custom_value_2_count)}</td>
                        <td className="border border-slate-200 px-3 py-2">{formatAmount(row.custom_value_3_amount, currencyCode)}</td>
                        <td className="border border-slate-200 px-3 py-2">{formatAmount(customValue4Amount, currencyCode)}</td>
                        <td className="border border-slate-200 px-3 py-2">{formatAmount(row.custom_value_5_amount, currencyCode)}</td>
                        {activeDynamicFields.map((field) => {
                          const custom = customValueByFieldId.get(field.id);
                          if (!custom) return <td key={field.id} className="border border-slate-200 px-3 py-2">—</td>;
                          return (
                            <td key={field.id} className="border border-slate-200 px-3 py-2">
                              {custom.value_kind === "amount" ? formatAmount(custom.numeric_value, currencyCode) : formatCount(custom.numeric_value)}
                            </td>
                          );
                        })}
                        <td className="border border-slate-200 px-3 py-2">{formatCount(salesCount)}</td>
                        <td className="border border-slate-200 px-3 py-2">{formatAmount(revenueAmount, currencyCode)}</td>
                        <td className="border border-slate-200 px-3 py-2">{formatAmount(cogsAmount, currencyCode)}</td>
                        <td className="border border-slate-200 px-3 py-2">{formatAmount(grossProfitAmount, currencyCode)}</td>
                        <td className="border border-slate-200 px-3 py-2">{String(row.notes || "").trim() || "—"}</td>
                        <td className="border border-slate-200 px-3 py-2">
                          <details>
                            <summary className="cursor-pointer text-indigo-700">View</summary>
                            <div className="mt-2 space-y-3">
                              <div>
                                <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-500">Sale entries</p>
                                {saleEntries.length === 0 ? (
                                  <p className="text-xs text-slate-500">—</p>
                                ) : (
                                  <table className="min-w-full border-collapse text-xs">
                                    <thead>
                                      <tr className="bg-slate-50 text-left">
                                        <th className="border border-slate-200 px-2 py-1">Brand</th>
                                        <th className="border border-slate-200 px-2 py-1">Model</th>
                                        <th className="border border-slate-200 px-2 py-1">Preț Vânzare</th>
                                        <th className="border border-slate-200 px-2 py-1">Preț Actual</th>
                                        <th className="border border-slate-200 px-2 py-1">Profit Brut</th>
                                        <th className="border border-slate-200 px-2 py-1">Mențiuni</th>
                                      </tr>
                                    </thead>
                                    <tbody>
                                      {saleEntries.map((entry, idx) => (
                                        <tr key={`${row.metric_date}:sale:${idx}`}>
                                          <td className="border border-slate-200 px-2 py-1">{String(entry.brand || "").trim() || "—"}</td>
                                          <td className="border border-slate-200 px-2 py-1">{String(entry.model || "").trim() || "—"}</td>
                                          <td className="border border-slate-200 px-2 py-1">{formatAmount(entry.sale_price_amount, currencyCode)}</td>
                                          <td className="border border-slate-200 px-2 py-1">{formatAmount(entry.actual_price_amount, currencyCode)}</td>
                                          <td className="border border-slate-200 px-2 py-1">{formatAmount(entry.gross_profit_amount, currencyCode)}</td>
                                          <td className="border border-slate-200 px-2 py-1">{String(entry.notes || "").trim() || "—"}</td>
                                        </tr>
                                      ))}
                                    </tbody>
                                  </table>
                                )}
                              </div>

                              <div>
                                <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-500">Dynamic custom values (historical)</p>
                                {rowCustomValues.length === 0 ? (
                                  <p className="text-xs text-slate-500">—</p>
                                ) : (
                                  <ul className="space-y-1 text-xs text-slate-700">
                                    {rowCustomValues.map((item, idx) => (
                                      <li key={`${row.metric_date}:custom:${item.custom_field_id}:${idx}`}>
                                        {String(item.label || `Field #${item.custom_field_id}`)}: {item.value_kind === "amount" ? formatAmount(item.numeric_value, currencyCode) : formatCount(item.numeric_value)}
                                      </li>
                                    ))}
                                  </ul>
                                )}
                              </div>
                            </div>
                          </details>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          ) : null}
        </section>
      </AppShell>
    </ProtectedPage>
  );
}
