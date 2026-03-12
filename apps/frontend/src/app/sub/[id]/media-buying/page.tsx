"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import React, { useCallback, useEffect, useMemo, useState } from "react";

import { format } from "date-fns";

import { AppShell } from "@/components/AppShell";
import { ProtectedPage } from "@/components/ProtectedPage";
import { apiRequest } from "@/lib/api";

type ClientItem = { id: number; name: string; client_type?: string };

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

type LeadTableMeta = {
  client_id: number;
  template_type: string;
  display_currency: string;
  custom_label_1?: string;
  custom_label_2?: string;
  custom_label_3?: string;
  custom_label_4?: string;
  custom_label_5?: string;
  custom_rate_label_1?: string;
  custom_rate_label_2?: string;
  custom_cost_label_1?: string;
  custom_cost_label_2?: string;
  visible_columns?: string[];
  date_from: string | null;
  date_to: string | null;
  effective_date_from?: string | null;
  effective_date_to?: string | null;
  earliest_data_date?: string | null;
  latest_data_date?: string | null;
  available_months?: string[];
};

type LeadTableResponse = {
  meta: LeadTableMeta;
  days: LeadTableRow[];
  months: LeadTableMonth[];
};

type EditableDraft = {
  leads: string;
  phones: string;
  custom_value_1_count: string;
  custom_value_2_count: string;
  custom_value_3_amount_ron: string;
  custom_value_4_amount_ron: string;
  custom_value_5_amount_ron: string;
  sales_count: string;
};

type LabelFieldKey =
  | "custom_label_1"
  | "custom_label_2"
  | "custom_label_3"
  | "custom_label_4"
  | "custom_label_5"
  | "custom_rate_label_1"
  | "custom_rate_label_2"
  | "custom_cost_label_1"
  | "custom_cost_label_2";

const INTEGER_FIELDS: Array<keyof EditableDraft> = [
  "leads",
  "phones",
  "custom_value_1_count",
  "custom_value_2_count",
  "sales_count",
];

const NON_NEGATIVE_AMOUNT_FIELDS: Array<keyof EditableDraft> = ["custom_value_3_amount_ron", "custom_value_4_amount_ron"];

const RO_MONTH_SHORT = ["Ian", "Feb", "Mar", "Apr", "Mai", "Iun", "Iul", "Aug", "Sep", "Oct", "Noi", "Dec"] as const;
const DEFAULT_VISIBLE_COLUMNS: ColumnSemanticKey[] = [
  "date",
  "cost_google",
  "cost_meta",
  "cost_tiktok",
  "cost_total",
  "percent_change",
  "leads",
  "phones",
  "total_leads",
  "custom_value_1_count",
  "custom_value_2_count",
  "custom_value_3_amount_ron",
  "custom_value_4_amount_ron",
  "custom_value_5_amount_ron",
  "sales_count",
  "custom_value_rate_1",
  "custom_value_rate_2",
  "cost_per_lead",
  "cost_custom_value_1",
  "cost_custom_value_2",
  "cost_per_sale",
];
const MANDATORY_COLUMNS: Set<ColumnSemanticKey> = new Set(["date"]);

type ColumnSemanticKey =
  | "date"
  | "cost_google"
  | "cost_meta"
  | "cost_tiktok"
  | "cost_total"
  | "percent_change"
  | "leads"
  | "phones"
  | "total_leads"
  | "custom_value_1_count"
  | "custom_value_2_count"
  | "custom_value_3_amount_ron"
  | "custom_value_4_amount_ron"
  | "custom_value_5_amount_ron"
  | "sales_count"
  | "custom_value_rate_1"
  | "custom_value_rate_2"
  | "cost_per_lead"
  | "cost_custom_value_1"
  | "cost_custom_value_2"
  | "cost_per_sale";

const GREY_COLUMNS: Set<ColumnSemanticKey> = new Set([
  "cost_google",
  "cost_meta",
  "cost_tiktok",
  "leads",
  "phones",
]);

const DASHED_COLUMNS: Set<ColumnSemanticKey> = new Set([
  "cost_total",
  "total_leads",
  "custom_value_rate_1",
  "custom_value_rate_2",
]);

const VIOLET_COLUMNS: Set<ColumnSemanticKey> = new Set([]);

function toIso(value: Date): string {
  return format(value, "yyyy-MM-dd");
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

function formatUnrealizedMoney(value: number | null | undefined, currencyCode: string): string {
  if (typeof value !== "number" || !Number.isFinite(value)) return "—";
  if (value > 0) return `(${formatMoney(value, currencyCode)})`;
  return formatMoney(0, currencyCode);
}

function columnClass(key: ColumnSemanticKey): string {
  const classes = ["px-3", "py-2"];
  if (GREY_COLUMNS.has(key)) classes.push("text-[#bfbfbf]");
  if (DASHED_COLUMNS.has(key)) classes.push("border-l", "border-r", "border-dashed", "border-slate-300");
  if (VIOLET_COLUMNS.has(key)) classes.push("text-violet-600");
  return classes.join(" ");
}

function stickyHeaderClass(column: ColumnSemanticKey): string {
  if (column === "date") return "sticky left-0 top-0 z-50 bg-slate-50 shadow-[6px_0_8px_-8px_rgba(15,23,42,0.35)]";
  return "sticky top-0 z-30 bg-slate-50";
}

function stickyDateCellClass(tone: "month" | "day"): string {
  const base = "sticky left-0 z-20 border-r border-slate-200 bg-white shadow-[6px_0_8px_-8px_rgba(15,23,42,0.35)]";
  if (tone === "month") return `${base} bg-slate-100`;
  return base;
}

function monthLabel(value: string): string {
  const [year, month] = value.split("-");
  const monthIndex = Number(month) - 1;
  return `${RO_MONTH_SHORT[Math.max(0, Math.min(11, monthIndex))]} ${year}`;
}

function shortDayLabel(value: string): string {
  const [, month, day] = value.split("-");
  const monthIndex = Number(month) - 1;
  return `${Number(day)} ${RO_MONTH_SHORT[Math.max(0, Math.min(11, monthIndex))]}`;
}

function fallbackLabel(value: string | undefined, fallback: string): string {
  const normalized = String(value || "").trim();
  return normalized || fallback;
}

function normalizedClientType(value: string | null): string {
  const raw = String(value || "lead").trim().toLowerCase();
  if (raw === "e-commerce") return "ecommerce";
  if (raw === "ecommerce") return "ecommerce";
  if (raw === "programmatic") return "programmatic";
  return "lead";
}

function makeDraft(row: LeadTableRow): EditableDraft {
  return {
    leads: String(row.leads),
    phones: String(row.phones),
    custom_value_1_count: String(row.custom_value_1_count),
    custom_value_2_count: String(row.custom_value_2_count),
    custom_value_3_amount_ron: String(row.custom_value_3_amount_ron),
    custom_value_4_amount_ron: String(row.custom_value_4_amount_ron),
    custom_value_5_amount_ron: String(row.custom_value_5_amount_ron),
    sales_count: String(row.sales_count),
  };
}

function validateDraft(draft: EditableDraft): Record<string, string> {
  const errors: Record<string, string> = {};

  for (const field of INTEGER_FIELDS) {
    const raw = draft[field].trim();
    if (!/^\d+$/.test(raw)) {
      errors[field] = "Must be integer >= 0";
      continue;
    }
    const parsed = Number(raw);
    if (!Number.isInteger(parsed) || parsed < 0) errors[field] = "Must be integer >= 0";
  }

  for (const field of NON_NEGATIVE_AMOUNT_FIELDS) {
    const raw = draft[field].trim();
    const parsed = Number(raw);
    if (!Number.isFinite(parsed) || parsed < 0) errors[field] = "Must be >= 0";
  }

  const custom5 = Number(draft.custom_value_5_amount_ron.trim());
  if (!Number.isFinite(custom5)) errors.custom_value_5_amount_ron = "Must be a number";

  return errors;
}

function hasChanges(draft: EditableDraft, row: LeadTableRow): boolean {
  return (
    draft.leads !== String(row.leads)
    || draft.phones !== String(row.phones)
    || draft.custom_value_1_count !== String(row.custom_value_1_count)
    || draft.custom_value_2_count !== String(row.custom_value_2_count)
    || draft.custom_value_3_amount_ron !== String(row.custom_value_3_amount_ron)
    || draft.custom_value_4_amount_ron !== String(row.custom_value_4_amount_ron)
    || draft.custom_value_5_amount_ron !== String(row.custom_value_5_amount_ron)
    || draft.sales_count !== String(row.sales_count)
  );
}

export default function SubMediaBuyingPage() {
  const params = useParams<{ id: string }>();
  const clientId = Number(params.id);

  const [clientName, setClientName] = useState<string>(`Sub-account #${clientId}`);
  const [clientType, setClientType] = useState<string>("lead");
  const [clientContextLoaded, setClientContextLoaded] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [tableData, setTableData] = useState<LeadTableResponse | null>(null);
  const [expandedMonths, setExpandedMonths] = useState<Record<string, boolean>>({});
  const [editingByDate, setEditingByDate] = useState<Record<string, EditableDraft>>({});
  const [savingByDate, setSavingByDate] = useState<Record<string, boolean>>({});
  const [rowFeedback, setRowFeedback] = useState<Record<string, { kind: "success" | "error"; message: string }>>({});

  const [editingLabelKey, setEditingLabelKey] = useState<LabelFieldKey | null>(null);
  const [labelDraft, setLabelDraft] = useState("");
  const [labelSaving, setLabelSaving] = useState(false);
  const [labelFeedback, setLabelFeedback] = useState<{ kind: "success" | "error"; message: string } | null>(null);

  const [visibleColumns, setVisibleColumns] = useState<ColumnSemanticKey[]>(DEFAULT_VISIBLE_COLUMNS);
  const [columnsPanelOpen, setColumnsPanelOpen] = useState(false);

  const loadTable = useCallback(async (preserveExpanded: boolean) => {
    if (!Number.isFinite(clientId)) return;
    setLoading(true);
    setError("");
    try {
      const payload = await apiRequest<LeadTableResponse>(
        `/clients/${clientId}/media-buying/lead/table`
      );
      setTableData(payload);
      setEditingByDate({});
      if (!preserveExpanded) {
        const latestMonth = [...payload.months].sort((a, b) => b.month.localeCompare(a.month))[0]?.month;
        setExpandedMonths(latestMonth ? { [latestMonth]: true } : {});
      }
    } catch (err) {
      setTableData(null);
      setError(err instanceof Error ? err.message : "Nu am putut încărca tabelul Media Buying");
    } finally {
      setLoading(false);
    }
  }, [clientId]);

  useEffect(() => {
    let ignore = false;

    async function loadClientContext() {
      try {
        const result = await apiRequest<{ items: ClientItem[] }>("/clients");
        const match = result.items.find((item) => item.id === clientId);
        if (!ignore) {
          if (match?.name) setClientName(match.name);
          if (match?.client_type) setClientType(normalizedClientType(match.client_type));
          setClientContextLoaded(true);
        }
      } catch {
        if (!ignore) {
          setClientName(`Sub-account #${clientId}`);
          setClientType("lead");
          setClientContextLoaded(true);
        }
      }
    }

    if (Number.isFinite(clientId)) void loadClientContext();
    return () => {
      ignore = true;
    };
  }, [clientId]);

  useEffect(() => {
    if (!clientContextLoaded) return;
    if (clientType !== "lead") {
      setLoading(false);
      setTableData(null);
      return;
    }
    void loadTable(false);
  }, [loadTable, clientType, clientContextLoaded]);

  const title = `Media Buying - ${clientName}`;

  const displayCurrency = tableData?.meta.display_currency || "RON";
  const labelMap: Record<LabelFieldKey, string> = {
    custom_label_1: fallbackLabel(tableData?.meta.custom_label_1, "Custom Value 1"),
    custom_label_2: fallbackLabel(tableData?.meta.custom_label_2, "Custom Value 2"),
    custom_label_3: fallbackLabel(tableData?.meta.custom_label_3, "Custom Value 3"),
    custom_label_4: fallbackLabel(tableData?.meta.custom_label_4, "Custom Value 4"),
    custom_label_5: fallbackLabel(tableData?.meta.custom_label_5, "Custom Value 5"),
    custom_rate_label_1: fallbackLabel(tableData?.meta.custom_rate_label_1, "Custom Value Rate 1"),
    custom_rate_label_2: fallbackLabel(tableData?.meta.custom_rate_label_2, "Custom Value Rate 2"),
    custom_cost_label_1: fallbackLabel(tableData?.meta.custom_cost_label_1, "Cost Custom Value 1"),
    custom_cost_label_2: fallbackLabel(tableData?.meta.custom_cost_label_2, "Cost Custom Value 2"),
  };

  const columnsMenu: Array<{ key: ColumnSemanticKey; label: string }> = [
    { key: "date", label: "Data" },
    { key: "cost_google", label: "Cost Google" },
    { key: "cost_meta", label: "Cost Meta" },
    { key: "cost_tiktok", label: "Cost TikTok" },
    { key: "cost_total", label: "Cost Total" },
    { key: "percent_change", label: "%^" },
    { key: "leads", label: "Lead-uri" },
    { key: "phones", label: "Telefoane" },
    { key: "total_leads", label: "Total Lead-uri" },
    { key: "custom_value_1_count", label: labelMap.custom_label_1 },
    { key: "custom_value_2_count", label: labelMap.custom_label_2 },
    { key: "custom_value_3_amount_ron", label: labelMap.custom_label_3 },
    { key: "custom_value_4_amount_ron", label: labelMap.custom_label_4 },
    { key: "custom_value_5_amount_ron", label: labelMap.custom_label_5 },
    { key: "sales_count", label: "Vânzări" },
    { key: "custom_value_rate_1", label: labelMap.custom_rate_label_1 },
    { key: "custom_value_rate_2", label: labelMap.custom_rate_label_2 },
    { key: "cost_per_lead", label: "Cost per Lead" },
    { key: "cost_custom_value_1", label: labelMap.custom_cost_label_1 },
    { key: "cost_custom_value_2", label: labelMap.custom_cost_label_2 },
    { key: "cost_per_sale", label: "Cost per Sale" },
  ];

  const isLeadTemplate = clientType === "lead";
  const sortedMonths = useMemo(
    () => (tableData ? [...tableData.months].sort((a, b) => b.month.localeCompare(a.month)) : []),
    [tableData]
  );

  useEffect(() => {
    const raw = tableData?.meta.visible_columns;
    const allowed = new Set(DEFAULT_VISIBLE_COLUMNS);
    const normalized = Array.isArray(raw)
      ? raw.filter((item): item is ColumnSemanticKey => allowed.has(item as ColumnSemanticKey))
      : [];
    setVisibleColumns(normalized.length > 0 ? normalized : DEFAULT_VISIBLE_COLUMNS);
  }, [tableData?.meta.visible_columns]);

  const visibleSet = useMemo(() => new Set(visibleColumns), [visibleColumns]);
  const isVisible = useCallback((column: ColumnSemanticKey) => MANDATORY_COLUMNS.has(column) || visibleSet.has(column), [visibleSet]);
  const classFor = useCallback((column: ColumnSemanticKey) => `${columnClass(column)} ${isVisible(column) ? "" : "hidden"}`.trim(), [isVisible]);
  const visibilityProps = useCallback((column: ColumnSemanticKey) => (isVisible(column) ? {} : { hidden: true, "aria-hidden": true }), [isVisible]);

  async function saveRow(day: LeadTableRow) {
    const draft = editingByDate[day.date];
    if (!draft) return;
    const validationErrors = validateDraft(draft);
    if (Object.keys(validationErrors).length > 0) return;

    setSavingByDate((prev) => ({ ...prev, [day.date]: true }));
    setRowFeedback((prev) => ({ ...prev, [day.date]: { kind: "success", message: "" } }));

    try {
      await apiRequest(`/clients/${clientId}/media-buying/lead/daily-values`, {
        method: "PUT",
        body: JSON.stringify({
          date: day.date,
          leads: Number(draft.leads),
          phones: Number(draft.phones),
          custom_value_1_count: Number(draft.custom_value_1_count),
          custom_value_2_count: Number(draft.custom_value_2_count),
          custom_value_3_amount_ron: Number(draft.custom_value_3_amount_ron),
          custom_value_4_amount_ron: Number(draft.custom_value_4_amount_ron),
          custom_value_5_amount_ron: Number(draft.custom_value_5_amount_ron),
          sales_count: Number(draft.sales_count),
        }),
      });

      await loadTable(true);
      setRowFeedback((prev) => ({ ...prev, [day.date]: { kind: "success", message: "Saved" } }));
    } catch (err) {
      setRowFeedback((prev) => ({
        ...prev,
        [day.date]: { kind: "error", message: err instanceof Error ? err.message : "Save failed" },
      }));
    } finally {
      setSavingByDate((prev) => ({ ...prev, [day.date]: false }));
    }
  }

  async function saveLabel(labelKey: LabelFieldKey) {
    const nextValue = labelDraft.trim();
    if (!tableData) return;

    setLabelSaving(true);
    setLabelFeedback(null);
    try {
      const updated = await apiRequest<LeadTableMeta>(`/clients/${clientId}/media-buying/config`, {
        method: "PUT",
        body: JSON.stringify({ [labelKey]: nextValue }),
      });

      setTableData((prev) => {
        if (!prev) return prev;
        return {
          ...prev,
          meta: {
            ...prev.meta,
            ...updated,
            template_type: prev.meta.template_type,
          },
        };
      });
      setEditingLabelKey(null);
      setLabelDraft("");
      setLabelFeedback({ kind: "success", message: "Label saved" });
    } catch (err) {
      setLabelFeedback({ kind: "error", message: err instanceof Error ? err.message : "Could not save label" });
    } finally {
      setLabelSaving(false);
    }
  }

  async function persistVisibleColumns(next: ColumnSemanticKey[]) {
    const unique = DEFAULT_VISIBLE_COLUMNS.filter((item) => next.includes(item) || MANDATORY_COLUMNS.has(item));
    setVisibleColumns(unique);
    setLabelFeedback(null);
    try {
      const updated = await apiRequest<LeadTableMeta>(`/clients/${clientId}/media-buying/config`, {
        method: "PUT",
        body: JSON.stringify({ visible_columns: unique }),
      });
      setTableData((prev) => {
        if (!prev) return prev;
        return { ...prev, meta: { ...prev.meta, ...updated } };
      });
      setLabelFeedback({ kind: "success", message: "View saved" });
    } catch (err) {
      setLabelFeedback({ kind: "error", message: err instanceof Error ? err.message : "Could not save view" });
    }
  }

  function toggleColumn(column: ColumnSemanticKey) {
    if (MANDATORY_COLUMNS.has(column)) return;
    const next = visibleSet.has(column)
      ? visibleColumns.filter((item) => item !== column)
      : [...visibleColumns, column];
    void persistVisibleColumns(next);
  }

  function renderEditableHeader(labelKey: LabelFieldKey) {

    const labelValue = labelMap[labelKey];
    const editing = editingLabelKey === labelKey;
    return (
      <div className="flex items-center gap-1">
        {editing ? (
          <input
            aria-label={`Edit ${labelKey}`}
            autoFocus
            className="w-36 rounded border border-slate-300 px-1 py-0.5 text-xs normal-case"
            value={labelDraft}
            onChange={(event) => setLabelDraft(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter") {
                event.preventDefault();
                void saveLabel(labelKey);
              }
              if (event.key === "Escape") {
                event.preventDefault();
                setEditingLabelKey(null);
                setLabelDraft("");
              }
            }}
            onBlur={() => {
              setEditingLabelKey(null);
              setLabelDraft("");
            }}
          />
        ) : (
          <span>{labelValue}</span>
        )}
        {!editing ? (
          <button
            aria-label={`Edit label ${labelKey}`}
            type="button"
            className="rounded px-1 text-xs text-slate-400 hover:bg-slate-200 hover:text-slate-700"
            onClick={() => {
              setEditingLabelKey(labelKey);
              setLabelDraft(labelValue);
            }}
          >
            ✎
          </button>
        ) : null}
      </div>
    );
  }

  return (
    <ProtectedPage>
      <AppShell title={null}>
        <div className="mb-4 flex items-center gap-4 text-sm">
          <Link href={`/sub/${clientId}/media-buying`} className="text-indigo-600 transition-colors hover:text-indigo-700 hover:underline">Media Buying</Link>
          <Link href={`/sub/${clientId}/media-tracker`} className="text-indigo-600 transition-colors hover:text-indigo-700 hover:underline">Media Tracker</Link>
        </div>

        <section className="wm-card p-6">
          <h1 className="text-xl font-semibold text-slate-900">{title}</h1>
          <p className="mt-2 text-sm text-slate-600">
            Range: {tableData?.meta.effective_date_from ?? tableData?.meta.date_from ?? "—"} - {tableData?.meta.effective_date_to ?? tableData?.meta.date_to ?? "—"}
          </p>

          {isLeadTemplate ? (
            <div className="mt-3 flex items-center gap-2">
              <button
                type="button"
                className="rounded border border-slate-300 px-2 py-1 text-xs text-slate-700 hover:bg-slate-50"
                onClick={() => setColumnsPanelOpen((prev) => !prev)}
              >
                Customize columns
              </button>
              {columnsPanelOpen ? (
                <div className="relative z-[60] max-h-56 overflow-y-auto rounded border border-slate-200 bg-white p-2 text-xs shadow-sm">
                  {columnsMenu.map((item) => {
                    const required = MANDATORY_COLUMNS.has(item.key);
                    return (
                      <label key={item.key} className="flex items-center gap-2 py-0.5">
                        <input
                          type="checkbox"
                          checked={isVisible(item.key)}
                          disabled={required}
                          onChange={() => toggleColumn(item.key)}
                        />
                        <span>{item.label}{required ? " (required)" : ""}</span>
                      </label>
                    );
                  })}
                </div>
              ) : null}
            </div>
          ) : null}

          {labelFeedback?.message ? (
            <p className={`mt-2 text-xs ${labelFeedback.kind === "error" ? "text-red-600" : "text-emerald-600"}`}>{labelFeedback.message}</p>
          ) : null}

          {loading ? <p className="mt-4 text-sm text-slate-600">Loading Media Buying table...</p> : null}
          {!loading && error ? <p className="mt-4 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p> : null}

          {!loading && !error && !isLeadTemplate ? (
            <div className="mt-4 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
              Template not implemented yet for this client type ({clientType}).
            </div>
          ) : null}

          {!loading && !error && tableData && isLeadTemplate && sortedMonths.length === 0 ? (
            <div className="mt-4 rounded-lg border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-600">
              No data available for selected range.
            </div>
          ) : null}

          {!loading && !error && tableData && isLeadTemplate && sortedMonths.length > 0 ? (
            <div className="mt-4 max-h-[70vh] overflow-auto rounded-lg border border-slate-200 scrollbar-thin scrollbar-track-slate-100 scrollbar-thumb-slate-300">
              <table className="min-w-[1850px] wm-card text-left text-sm">
                <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-600">
                  <tr>
                    <th {...visibilityProps("date")} className={`${classFor("date")} ${stickyHeaderClass("date")}`}>Data</th>
                    <th {...visibilityProps("cost_google")} className={`${classFor("cost_google")} ${stickyHeaderClass("cost_google")}`}>Cost Google</th>
                    <th {...visibilityProps("cost_meta")} className={`${classFor("cost_meta")} ${stickyHeaderClass("cost_meta")}`}>Cost Meta</th>
                    <th {...visibilityProps("cost_tiktok")} className={`${classFor("cost_tiktok")} ${stickyHeaderClass("cost_tiktok")}`}>Cost TikTok</th>
                    <th {...visibilityProps("cost_total")} className={`${classFor("cost_total")} ${stickyHeaderClass("cost_total")}`}>Cost Total</th>
                    <th {...visibilityProps("percent_change")} className={`${classFor("percent_change")} ${stickyHeaderClass("percent_change")}`}>%^</th>
                    <th {...visibilityProps("leads")} className={`${classFor("leads")} ${stickyHeaderClass("leads")}`}>Lead-uri</th>
                    <th {...visibilityProps("phones")} className={`${classFor("phones")} ${stickyHeaderClass("phones")}`}>Telefoane</th>
                    <th {...visibilityProps("total_leads")} className={`${classFor("total_leads")} ${stickyHeaderClass("total_leads")}`}>Total Lead-uri</th>
                    <th {...visibilityProps("custom_value_1_count")} className={`${classFor("custom_value_1_count")} ${stickyHeaderClass("custom_value_1_count")}`}>{renderEditableHeader("custom_label_1")}</th>
                    <th {...visibilityProps("custom_value_2_count")} className={`${classFor("custom_value_2_count")} ${stickyHeaderClass("custom_value_2_count")}`}>{renderEditableHeader("custom_label_2")}</th>
                    <th {...visibilityProps("custom_value_3_amount_ron")} className={`${classFor("custom_value_3_amount_ron")} ${stickyHeaderClass("custom_value_3_amount_ron")}`}>{renderEditableHeader("custom_label_3")}</th>
                    <th {...visibilityProps("custom_value_4_amount_ron")} className={`${classFor("custom_value_4_amount_ron")} ${stickyHeaderClass("custom_value_4_amount_ron")}`}>{renderEditableHeader("custom_label_4")}</th>
                    <th {...visibilityProps("custom_value_5_amount_ron")} className={`${classFor("custom_value_5_amount_ron")} ${stickyHeaderClass("custom_value_5_amount_ron")}`}>{renderEditableHeader("custom_label_5")}</th>
                    <th {...visibilityProps("sales_count")} className={`${classFor("sales_count")} ${stickyHeaderClass("sales_count")}`}>Vânzări</th>
                    <th {...visibilityProps("custom_value_rate_1")} className={`${classFor("custom_value_rate_1")} ${stickyHeaderClass("custom_value_rate_1")}`}>{renderEditableHeader("custom_rate_label_1")}</th>
                    <th {...visibilityProps("custom_value_rate_2")} className={`${classFor("custom_value_rate_2")} ${stickyHeaderClass("custom_value_rate_2")}`}>{renderEditableHeader("custom_rate_label_2")}</th>
                    <th {...visibilityProps("cost_per_lead")} className={`${classFor("cost_per_lead")} ${stickyHeaderClass("cost_per_lead")}`}>Cost per Lead</th>
                    <th {...visibilityProps("cost_custom_value_1")} className={`${classFor("cost_custom_value_1")} ${stickyHeaderClass("cost_custom_value_1")}`}>{renderEditableHeader("custom_cost_label_1")}</th>
                    <th {...visibilityProps("cost_custom_value_2")} className={`${classFor("cost_custom_value_2")} ${stickyHeaderClass("cost_custom_value_2")}`}>{renderEditableHeader("custom_cost_label_2")}</th>
                    <th {...visibilityProps("cost_per_sale")} className={`${classFor("cost_per_sale")} ${stickyHeaderClass("cost_per_sale")}`}>Cost per Sale</th>
                  </tr>
                </thead>
                <tbody>
                  {sortedMonths.map((month) => {
                    const open = Boolean(expandedMonths[month.month]);
                    const monthTotals = month.totals;
                    return (
                      <React.Fragment key={month.month}>
                        <tr className="border-t border-slate-300 bg-slate-100 font-semibold text-slate-900">
                          <td {...visibilityProps("date")} className={`${classFor("date")} ${stickyDateCellClass("month")}`}>
                            <button
                              type="button"
                              onClick={() => setExpandedMonths((prev) => ({ ...prev, [month.month]: !open }))}
                              className="text-left"
                            >
                              {open ? "▾" : "▸"} {monthLabel(month.month)}
                            </button>
                          </td>
                          <td {...visibilityProps("cost_google")} className={classFor("cost_google")}>{formatMoney(monthTotals.cost_google, displayCurrency)}</td>
                          <td {...visibilityProps("cost_meta")} className={classFor("cost_meta")}>{formatMoney(monthTotals.cost_meta, displayCurrency)}</td>
                          <td {...visibilityProps("cost_tiktok")} className={classFor("cost_tiktok")}>{formatMoney(monthTotals.cost_tiktok, displayCurrency)}</td>
                          <td {...visibilityProps("cost_total")} className={classFor("cost_total")}>{formatMoney(monthTotals.cost_total, displayCurrency)}</td>
                          <td {...visibilityProps("percent_change")} className={classFor("percent_change")}>{formatRate(monthTotals.percent_change)}</td>
                          <td {...visibilityProps("leads")} className={classFor("leads")}>{formatCount(monthTotals.leads)}</td>
                          <td {...visibilityProps("phones")} className={classFor("phones")}>{formatCount(monthTotals.phones)}</td>
                          <td {...visibilityProps("total_leads")} className={classFor("total_leads")}>{formatCount(monthTotals.total_leads)}</td>
                          <td {...visibilityProps("custom_value_1_count")} className={classFor("custom_value_1_count")}>{formatCount(monthTotals.custom_value_1_count)}</td>
                          <td {...visibilityProps("custom_value_2_count")} className={classFor("custom_value_2_count")}>{formatCount(monthTotals.custom_value_2_count)}</td>
                          <td {...visibilityProps("custom_value_3_amount_ron")} className={classFor("custom_value_3_amount_ron")}>{formatMoney(monthTotals.custom_value_3_amount_ron, displayCurrency)}</td>
                          <td {...visibilityProps("custom_value_4_amount_ron")} className={classFor("custom_value_4_amount_ron")}><span className="text-slate-900">{formatUnrealizedMoney(monthTotals.custom_value_4_amount_ron, displayCurrency)}</span></td>
                          <td {...visibilityProps("custom_value_5_amount_ron")} className={classFor("custom_value_5_amount_ron")}>{formatMoney(monthTotals.custom_value_5_amount_ron, displayCurrency)}</td>
                          <td {...visibilityProps("sales_count")} className={classFor("sales_count")}>{formatCount(monthTotals.sales_count)}</td>
                          <td {...visibilityProps("custom_value_rate_1")} className={classFor("custom_value_rate_1")}>{formatRate(monthTotals.custom_value_rate_1)}</td>
                          <td {...visibilityProps("custom_value_rate_2")} className={classFor("custom_value_rate_2")}>{formatRate(monthTotals.custom_value_rate_2)}</td>
                          <td {...visibilityProps("cost_per_lead")} className={classFor("cost_per_lead")}>{formatMoney(monthTotals.cost_per_lead, displayCurrency)}</td>
                          <td {...visibilityProps("cost_custom_value_1")} className={classFor("cost_custom_value_1")}>{formatMoney(monthTotals.cost_custom_value_1, displayCurrency)}</td>
                          <td {...visibilityProps("cost_custom_value_2")} className={classFor("cost_custom_value_2")}>{formatMoney(monthTotals.cost_custom_value_2, displayCurrency)}</td>
                          <td {...visibilityProps("cost_per_sale")} className={classFor("cost_per_sale")}>{formatMoney(monthTotals.cost_per_sale, displayCurrency)}</td>
                        </tr>

                        {open
                          ? month.days.map((day) => {
                              const draft = editingByDate[day.date];
                              const errors = draft ? validateDraft(draft) : {};
                              const changed = draft ? hasChanges(draft, day) : false;
                              const invalid = draft ? Object.keys(errors).length > 0 : false;
                              const saving = Boolean(savingByDate[day.date]);
                              const feedback = rowFeedback[day.date];

                              return (
                                <tr key={day.date} className="border-t border-slate-200 bg-white text-slate-800">
                                  <td {...visibilityProps("date")} className={`${classFor("date")} ${stickyDateCellClass("day")} pl-8 align-top`}>
                                    <div>{shortDayLabel(day.date)}</div>
                                    <div className="mt-1 flex gap-2">
                                      {draft ? (
                                        <>
                                          <button
                                            type="button"
                                            className="rounded border border-slate-300 px-2 py-0.5 text-xs hover:bg-slate-50 disabled:opacity-50"
                                            onClick={() => void saveRow(day)}
                                            disabled={!changed || invalid || saving}
                                          >
                                            {saving ? "Saving..." : "Save"}
                                          </button>
                                          <button
                                            type="button"
                                            className="rounded border border-slate-300 px-2 py-0.5 text-xs hover:bg-slate-50 disabled:opacity-50"
                                            onClick={() => setEditingByDate((prev) => {
                                              const next = { ...prev };
                                              delete next[day.date];
                                              return next;
                                            })}
                                            disabled={saving}
                                          >
                                            Cancel
                                          </button>
                                        </>
                                      ) : (
                                        <button
                                          type="button"
                                          className="rounded border border-slate-300 px-2 py-0.5 text-xs hover:bg-slate-50"
                                          onClick={() => setEditingByDate((prev) => ({ ...prev, [day.date]: makeDraft(day) }))}
                                        >
                                          Edit
                                        </button>
                                      )}
                                    </div>
                                    {feedback?.message ? (
                                      <p className={`mt-1 text-xs ${feedback.kind === "error" ? "text-red-600" : "text-emerald-600"}`}>{feedback.message}</p>
                                    ) : null}
                                  </td>
                                  <td {...visibilityProps("cost_google")} className={classFor("cost_google")}>{formatMoney(day.cost_google, displayCurrency)}</td>
                                  <td {...visibilityProps("cost_meta")} className={classFor("cost_meta")}>{formatMoney(day.cost_meta, displayCurrency)}</td>
                                  <td {...visibilityProps("cost_tiktok")} className={classFor("cost_tiktok")}>{formatMoney(day.cost_tiktok, displayCurrency)}</td>
                                  <td {...visibilityProps("cost_total")} className={classFor("cost_total")}>{formatMoney(day.cost_total, displayCurrency)}</td>
                                  <td {...visibilityProps("percent_change")} className={classFor("percent_change")}>{formatRate(day.percent_change)}</td>
                                  <td {...visibilityProps("leads")} className={classFor("leads")}>
                                    {draft ? <input aria-label={`Leads ${day.date}`} className="w-20 rounded border border-slate-300 px-2 py-1" value={draft.leads} onChange={(e) => setEditingByDate((prev) => ({ ...prev, [day.date]: { ...draft, leads: e.target.value } }))} /> : formatCount(day.leads)}
                                    {errors.leads ? <p className="text-xs text-red-600">{errors.leads}</p> : null}
                                  </td>
                                  <td {...visibilityProps("phones")} className={classFor("phones")}>
                                    {draft ? <input aria-label={`Phones ${day.date}`} className="w-20 rounded border border-slate-300 px-2 py-1" value={draft.phones} onChange={(e) => setEditingByDate((prev) => ({ ...prev, [day.date]: { ...draft, phones: e.target.value } }))} /> : formatCount(day.phones)}
                                    {errors.phones ? <p className="text-xs text-red-600">{errors.phones}</p> : null}
                                  </td>
                                  <td {...visibilityProps("total_leads")} className={classFor("total_leads")}>{formatCount(day.total_leads)}</td>
                                  <td {...visibilityProps("custom_value_1_count")} className={classFor("custom_value_1_count")}>
                                    {draft ? <input aria-label={`Custom Value 1 ${day.date}`} className="w-20 rounded border border-slate-300 px-2 py-1" value={draft.custom_value_1_count} onChange={(e) => setEditingByDate((prev) => ({ ...prev, [day.date]: { ...draft, custom_value_1_count: e.target.value } }))} /> : formatCount(day.custom_value_1_count)}
                                    {errors.custom_value_1_count ? <p className="text-xs text-red-600">{errors.custom_value_1_count}</p> : null}
                                  </td>
                                  <td {...visibilityProps("custom_value_2_count")} className={classFor("custom_value_2_count")}>
                                    {draft ? <input aria-label={`Custom Value 2 ${day.date}`} className="w-20 rounded border border-slate-300 px-2 py-1" value={draft.custom_value_2_count} onChange={(e) => setEditingByDate((prev) => ({ ...prev, [day.date]: { ...draft, custom_value_2_count: e.target.value } }))} /> : formatCount(day.custom_value_2_count)}
                                    {errors.custom_value_2_count ? <p className="text-xs text-red-600">{errors.custom_value_2_count}</p> : null}
                                  </td>
                                  <td {...visibilityProps("custom_value_3_amount_ron")} className={classFor("custom_value_3_amount_ron")}>
                                    {draft ? <input aria-label={`Custom Value 3 ${day.date}`} className="w-24 rounded border border-slate-300 px-2 py-1" value={draft.custom_value_3_amount_ron} onChange={(e) => setEditingByDate((prev) => ({ ...prev, [day.date]: { ...draft, custom_value_3_amount_ron: e.target.value } }))} /> : formatMoney(day.custom_value_3_amount_ron, displayCurrency)}
                                    {errors.custom_value_3_amount_ron ? <p className="text-xs text-red-600">{errors.custom_value_3_amount_ron}</p> : null}
                                  </td>
                                  <td {...visibilityProps("custom_value_4_amount_ron")} className={classFor("custom_value_4_amount_ron")}>
                                    {draft ? <input aria-label={`Custom Value 4 ${day.date}`} className="w-24 rounded border border-slate-300 px-2 py-1" value={draft.custom_value_4_amount_ron} onChange={(e) => setEditingByDate((prev) => ({ ...prev, [day.date]: { ...draft, custom_value_4_amount_ron: e.target.value } }))} /> : <span className="text-slate-900">{formatUnrealizedMoney(day.custom_value_4_amount_ron, displayCurrency)}</span>}
                                    {errors.custom_value_4_amount_ron ? <p className="text-xs text-red-600">{errors.custom_value_4_amount_ron}</p> : null}
                                  </td>
                                  <td {...visibilityProps("custom_value_5_amount_ron")} className={classFor("custom_value_5_amount_ron")}>
                                    {draft ? <input aria-label={`Custom Value 5 ${day.date}`} className="w-24 rounded border border-slate-300 px-2 py-1" value={draft.custom_value_5_amount_ron} onChange={(e) => setEditingByDate((prev) => ({ ...prev, [day.date]: { ...draft, custom_value_5_amount_ron: e.target.value } }))} /> : <span className="text-slate-900">{formatMoney(day.custom_value_5_amount_ron, displayCurrency)}</span>}
                                    {errors.custom_value_5_amount_ron ? <p className="text-xs text-red-600">{errors.custom_value_5_amount_ron}</p> : null}
                                  </td>
                                  <td {...visibilityProps("sales_count")} className={classFor("sales_count")}>
                                    {draft ? <input aria-label={`Sales ${day.date}`} className="w-20 rounded border border-slate-300 px-2 py-1" value={draft.sales_count} onChange={(e) => setEditingByDate((prev) => ({ ...prev, [day.date]: { ...draft, sales_count: e.target.value } }))} /> : formatCount(day.sales_count)}
                                    {errors.sales_count ? <p className="text-xs text-red-600">{errors.sales_count}</p> : null}
                                  </td>
                                  <td {...visibilityProps("custom_value_rate_1")} className={classFor("custom_value_rate_1")}>{formatRate(day.custom_value_rate_1)}</td>
                                  <td {...visibilityProps("custom_value_rate_2")} className={classFor("custom_value_rate_2")}>{formatRate(day.custom_value_rate_2)}</td>
                                  <td {...visibilityProps("cost_per_lead")} className={classFor("cost_per_lead")}>{formatMoney(day.cost_per_lead, displayCurrency)}</td>
                                  <td {...visibilityProps("cost_custom_value_1")} className={classFor("cost_custom_value_1")}>{formatMoney(day.cost_custom_value_1, displayCurrency)}</td>
                                  <td {...visibilityProps("cost_custom_value_2")} className={classFor("cost_custom_value_2")}>{formatMoney(day.cost_custom_value_2, displayCurrency)}</td>
                                  <td {...visibilityProps("cost_per_sale")} className={classFor("cost_per_sale")}>{formatMoney(day.cost_per_sale, displayCurrency)}</td>
                                </tr>
                              );
                            })
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
