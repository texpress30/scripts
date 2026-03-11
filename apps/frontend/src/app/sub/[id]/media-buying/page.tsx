"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import React, { useEffect, useMemo, useState } from "react";

import { format, subDays } from "date-fns";

import { AppShell } from "@/components/AppShell";
import { ProtectedPage } from "@/components/ProtectedPage";
import { apiRequest } from "@/lib/api";

type ClientItem = { id: number; name: string };

type LeadTableRow = {
  date: string;
  cost_google: number;
  cost_meta: number;
  cost_tiktok: number;
  cost_total: number;
  percent_change: number | null;
  leads: number;
  phones: number;
  total_leads: number;
  custom_value_1_count: number;
  custom_value_2_count: number;
  custom_value_3_amount_ron: number;
  custom_value_4_amount_ron: number;
  custom_value_5_amount_ron: number;
  sales_count: number;
  custom_value_rate_1: number | null;
  custom_value_rate_2: number | null;
  cost_per_lead: number | null;
  cost_custom_value_1: number | null;
  cost_custom_value_2: number | null;
  cost_per_sale: number | null;
};

type LeadTableMonth = {
  month: string;
  date_from: string;
  date_to: string;
  totals: LeadTableRow;
  days: LeadTableRow[];
};

type LeadTableResponse = {
  meta: {
    client_id: number;
    template_type: string;
    display_currency: string;
    custom_label_1?: string;
    custom_label_2?: string;
    custom_label_3?: string;
    custom_label_4?: string;
    custom_label_5?: string;
    date_from: string;
    date_to: string;
    available_months?: string[];
  };
  days: LeadTableRow[];
  months: LeadTableMonth[];
};

function toIso(value: Date): string {
  return format(value, "yyyy-MM-dd");
}

function safeNumber(value: number | null | undefined): number {
  return typeof value === "number" && Number.isFinite(value) ? value : 0;
}

function formatMoney(value: number | null | undefined, currencyCode: string): string {
  if (typeof value !== "number" || !Number.isFinite(value)) return "—";
  return new Intl.NumberFormat(undefined, { style: "currency", currency: currencyCode, maximumFractionDigits: 2 }).format(value);
}

function formatCount(value: number | null | undefined): string {
  if (typeof value !== "number" || !Number.isFinite(value)) return "—";
  return Math.trunc(value).toLocaleString();
}

function formatRate(value: number | null | undefined): string {
  if (typeof value !== "number" || !Number.isFinite(value)) return "—";
  return `${(value * 100).toFixed(2)}%`;
}

function monthLabel(value: string): string {
  const [year, month] = value.split("-");
  const d = new Date(Number(year), Number(month) - 1, 1);
  return format(d, "MMMM yyyy");
}

function fallbackLabel(value: string | undefined, fallback: string): string {
  const normalized = String(value || "").trim();
  return normalized || fallback;
}

export default function SubMediaBuyingPage() {
  const params = useParams<{ id: string }>();
  const clientId = Number(params.id);

  const [clientName, setClientName] = useState<string>(`Sub-account #${clientId}`);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [tableData, setTableData] = useState<LeadTableResponse | null>(null);
  const [expandedMonths, setExpandedMonths] = useState<Record<string, boolean>>({});

  const dateTo = useMemo(() => new Date(), []);
  const dateFrom = useMemo(() => subDays(dateTo, 89), [dateTo]);

  useEffect(() => {
    let ignore = false;

    async function loadClientName() {
      try {
        const result = await apiRequest<{ items: ClientItem[] }>("/clients");
        const match = result.items.find((item) => item.id === clientId);
        if (!ignore && match?.name) setClientName(match.name);
      } catch {
        if (!ignore) setClientName(`Sub-account #${clientId}`);
      }
    }

    if (Number.isFinite(clientId)) void loadClientName();
    return () => {
      ignore = true;
    };
  }, [clientId]);

  useEffect(() => {
    let ignore = false;

    async function loadTable() {
      if (!Number.isFinite(clientId)) return;
      setLoading(true);
      setError("");
      try {
        const payload = await apiRequest<LeadTableResponse>(
          `/clients/${clientId}/media-buying/lead/table?date_from=${toIso(dateFrom)}&date_to=${toIso(dateTo)}`
        );
        if (ignore) return;
        setTableData(payload);

        const latestMonth = payload.months[payload.months.length - 1]?.month;
        setExpandedMonths(latestMonth ? { [latestMonth]: true } : {});
      } catch (err) {
        if (ignore) return;
        setTableData(null);
        setError(err instanceof Error ? err.message : "Nu am putut încărca tabelul Media Buying");
      } finally {
        if (!ignore) setLoading(false);
      }
    }

    void loadTable();
    return () => {
      ignore = true;
    };
  }, [clientId, dateFrom, dateTo]);

  const title = `Media Buying - ${clientName}`;

  const displayCurrency = tableData?.meta.display_currency || "RON";
  const label1 = fallbackLabel(tableData?.meta.custom_label_1, "Custom Value 1");
  const label2 = fallbackLabel(tableData?.meta.custom_label_2, "Custom Value 2");
  const label3 = fallbackLabel(tableData?.meta.custom_label_3, "Custom Value 3");
  const label4 = fallbackLabel(tableData?.meta.custom_label_4, "Custom Value 4");
  const label5 = fallbackLabel(tableData?.meta.custom_label_5, "Custom Value 5");

  const isLeadTemplate = (tableData?.meta.template_type || "lead") === "lead";

  return (
    <ProtectedPage>
      <AppShell title={null}>
        <div className="mb-4 flex items-center gap-4 text-sm">
          <Link href={`/sub/${clientId}/media-buying`} className="text-indigo-600 transition-colors hover:text-indigo-700 hover:underline">Media Buying</Link>
          <Link href={`/sub/${clientId}/media-tracker`} className="text-indigo-600 transition-colors hover:text-indigo-700 hover:underline">Media Tracker</Link>
        </div>

        <section className="wm-card p-6">
          <h1 className="text-xl font-semibold text-slate-900">{title}</h1>
          <p className="mt-2 text-sm text-slate-600">Range: {toIso(dateFrom)} - {toIso(dateTo)}</p>

          {loading ? <p className="mt-4 text-sm text-slate-600">Loading Media Buying table...</p> : null}
          {!loading && error ? <p className="mt-4 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p> : null}

          {!loading && !error && tableData && !isLeadTemplate ? (
            <div className="mt-4 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
              Template not implemented yet for this sub-account.
            </div>
          ) : null}

          {!loading && !error && tableData && isLeadTemplate && tableData.months.length === 0 ? (
            <div className="mt-4 rounded-lg border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-600">
              No data available for selected range.
            </div>
          ) : null}

          {!loading && !error && tableData && isLeadTemplate && tableData.months.length > 0 ? (
            <div className="mt-4 overflow-x-auto">
              <table className="min-w-[1800px] wm-card text-left text-sm">
                <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-600">
                  <tr>
                    <th className="px-3 py-2">Data</th>
                    <th className="px-3 py-2">Cost Google</th>
                    <th className="px-3 py-2">Cost Meta</th>
                    <th className="px-3 py-2">Cost TikTok</th>
                    <th className="px-3 py-2">Cost Total</th>
                    <th className="px-3 py-2">%^</th>
                    <th className="px-3 py-2">Lead-uri</th>
                    <th className="px-3 py-2">Telefoane</th>
                    <th className="px-3 py-2">Total Lead-uri</th>
                    <th className="px-3 py-2">{label1}</th>
                    <th className="px-3 py-2">{label2}</th>
                    <th className="px-3 py-2">{label3}</th>
                    <th className="px-3 py-2">{label4}</th>
                    <th className="px-3 py-2">{label5}</th>
                    <th className="px-3 py-2">Vânzări</th>
                    <th className="px-3 py-2">Custom Value Rate 1</th>
                    <th className="px-3 py-2">Custom Value Rate 2</th>
                    <th className="px-3 py-2">Cost per Lead</th>
                    <th className="px-3 py-2">Cost Custom Value 1</th>
                    <th className="px-3 py-2">Cost Custom Value 2</th>
                    <th className="px-3 py-2">Cost per Sale</th>
                  </tr>
                </thead>
                <tbody>
                  {tableData.months.map((month) => {
                    const open = Boolean(expandedMonths[month.month]);
                    const monthTotals = month.totals;
                    return (
                      <React.Fragment key={month.month}>
                        <tr className="border-t border-slate-300 bg-slate-100 font-semibold text-slate-900">
                          <td className="px-3 py-2">
                            <button
                              type="button"
                              onClick={() => setExpandedMonths((prev) => ({ ...prev, [month.month]: !open }))}
                              className="text-left"
                            >
                              {open ? "▾" : "▸"} {monthLabel(month.month)}
                            </button>
                          </td>
                          <td className="px-3 py-2">{formatMoney(monthTotals.cost_google, displayCurrency)}</td>
                          <td className="px-3 py-2">{formatMoney(monthTotals.cost_meta, displayCurrency)}</td>
                          <td className="px-3 py-2">{formatMoney(monthTotals.cost_tiktok, displayCurrency)}</td>
                          <td className="px-3 py-2">{formatMoney(monthTotals.cost_total, displayCurrency)}</td>
                          <td className="px-3 py-2">—</td>
                          <td className="px-3 py-2">{formatCount(monthTotals.leads)}</td>
                          <td className="px-3 py-2">{formatCount(monthTotals.phones)}</td>
                          <td className="px-3 py-2">{formatCount(monthTotals.total_leads)}</td>
                          <td className="px-3 py-2">{formatCount(monthTotals.custom_value_1_count)}</td>
                          <td className="px-3 py-2">{formatCount(monthTotals.custom_value_2_count)}</td>
                          <td className="px-3 py-2">{formatMoney(monthTotals.custom_value_3_amount_ron, displayCurrency)}</td>
                          <td className="px-3 py-2">{formatMoney(monthTotals.custom_value_4_amount_ron, displayCurrency)}</td>
                          <td className="px-3 py-2">{formatMoney(monthTotals.custom_value_5_amount_ron, displayCurrency)}</td>
                          <td className="px-3 py-2">{formatCount(monthTotals.sales_count)}</td>
                          <td className="px-3 py-2">{formatRate(monthTotals.custom_value_rate_1)}</td>
                          <td className="px-3 py-2">{formatRate(monthTotals.custom_value_rate_2)}</td>
                          <td className="px-3 py-2">{formatMoney(monthTotals.cost_per_lead, displayCurrency)}</td>
                          <td className="px-3 py-2">{formatMoney(monthTotals.cost_custom_value_1, displayCurrency)}</td>
                          <td className="px-3 py-2">{formatMoney(monthTotals.cost_custom_value_2, displayCurrency)}</td>
                          <td className="px-3 py-2">{formatMoney(monthTotals.cost_per_sale, displayCurrency)}</td>
                        </tr>

                        {open
                          ? month.days.map((day) => (
                              <tr key={day.date} className="border-t border-slate-200 bg-white text-slate-800">
                                <td className="px-3 py-2 pl-8">{day.date}</td>
                                <td className="px-3 py-2">{formatMoney(day.cost_google, displayCurrency)}</td>
                                <td className="px-3 py-2">{formatMoney(day.cost_meta, displayCurrency)}</td>
                                <td className="px-3 py-2">{formatMoney(day.cost_tiktok, displayCurrency)}</td>
                                <td className="px-3 py-2">{formatMoney(day.cost_total, displayCurrency)}</td>
                                <td className="px-3 py-2">—</td>
                                <td className="px-3 py-2">{formatCount(day.leads)}</td>
                                <td className="px-3 py-2">{formatCount(day.phones)}</td>
                                <td className="px-3 py-2">{formatCount(day.total_leads)}</td>
                                <td className="px-3 py-2">{formatCount(day.custom_value_1_count)}</td>
                                <td className="px-3 py-2">{formatCount(day.custom_value_2_count)}</td>
                                <td className="px-3 py-2">{formatMoney(day.custom_value_3_amount_ron, displayCurrency)}</td>
                                <td className="px-3 py-2">{formatMoney(day.custom_value_4_amount_ron, displayCurrency)}</td>
                                <td className="px-3 py-2">{formatMoney(day.custom_value_5_amount_ron, displayCurrency)}</td>
                                <td className="px-3 py-2">{formatCount(day.sales_count)}</td>
                                <td className="px-3 py-2">{formatRate(day.custom_value_rate_1)}</td>
                                <td className="px-3 py-2">{formatRate(day.custom_value_rate_2)}</td>
                                <td className="px-3 py-2">{formatMoney(day.cost_per_lead, displayCurrency)}</td>
                                <td className="px-3 py-2">{formatMoney(day.cost_custom_value_1, displayCurrency)}</td>
                                <td className="px-3 py-2">{formatMoney(day.cost_custom_value_2, displayCurrency)}</td>
                                <td className="px-3 py-2">{formatMoney(day.cost_per_sale, displayCurrency)}</td>
                              </tr>
                            ))
                          : null}
                      </React.Fragment>
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
