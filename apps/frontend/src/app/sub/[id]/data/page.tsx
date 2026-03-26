"use client";

import { addMonths, endOfMonth, format, getISOWeek, parse, startOfMonth } from "date-fns";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import React, { useEffect, useMemo, useState } from "react";

import { SubReportingNav } from "@/app/sub/[id]/_components/SubReportingNav";
import { AppShell } from "@/components/AppShell";
import { ProtectedPage } from "@/components/ProtectedPage";
import { apiRequest } from "@/lib/api";

type ClientItem = { id: number; name: string };
type SourceItem = { key: string; label: string };

type FixedFieldConfig = { key: string; label: string };
type DerivedFieldConfig = { key: string; label: string; value_kind?: "count" | "amount" };
type DynamicCustomFieldConfig = { id: number; field_key: string; label: string; value_kind?: "count" | "amount"; sort_order?: number; is_active?: boolean };

type DataConfigResponse = {
  currency_code?: string;
  display_currency?: string;
  sources?: SourceItem[];
  fixed_fields?: FixedFieldConfig[];
  derived_fields?: DerivedFieldConfig[];
  dynamic_custom_fields?: DynamicCustomFieldConfig[];
  custom_fields?: DynamicCustomFieldConfig[];
};

type DynamicCustomValueRow = {
  custom_field_id: number;
  label?: string;
  value_kind?: "count" | "amount";
  numeric_value: number | string;
  is_active?: boolean;
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
    custom_value_5_amount?: number | string;
    gross_profit_amount?: number | string;
  };
  sale_entries?: Array<{
    id: number;
    brand?: string | null;
    model?: string | null;
    sale_price_amount?: number | string;
    actual_price_amount?: number | string;
    gross_profit_amount?: number | string;
  }>;
  dynamic_custom_values?: DynamicCustomValueRow[];
  custom_values?: DynamicCustomValueRow[];
};

type DataTableResponse = { rows: DataTableRow[] };
type CustomFieldListResponse = { items?: DynamicCustomFieldConfig[] };

type DailyRowDraft = {
  metric_date: string;
  source: string;
  leads: string;
  phones: string;
  custom_value_1_count: string;
  custom_value_2_count: string;
  custom_value_3_amount: string;
  custom_value_4_amount: string;
  sales_count: string;
  dynamicValues: Record<number, string>;
};

type SingleSaleDraft = {
  brand: string;
  model: string;
  sale_price_amount: string;
  actual_price_amount: string;
};

const FIXED_FIELD_FALLBACK_LABELS: Record<string, string> = {
  leads: "Lead-uri",
  phones: "Telefoane",
  custom_value_1_count: "Custom 1",
  custom_value_2_count: "Custom 2",
  custom_value_3_amount: "Custom 3",
  custom_value_4_amount: "Custom 4",
  sales_count: "Vânzări",
};

const DERIVED_FIELD_FALLBACK_LABELS: Record<string, string> = {
  custom_value_4_amount: "Custom Value 4",
  custom_value_5_amount: "Custom Value 5",
  sales_count: "Vânzări",
  revenue_amount: "Venit",
  cogs_amount: "COGS",
  gross_profit_amount: "Profit Brut",
};

const SOURCE_FALLBACKS: SourceItem[] = [
  { key: "meta_ads", label: "Meta" },
  { key: "google_ads", label: "Google" },
  { key: "tiktok_ads", label: "TikTok" },
  { key: "organic", label: "Organic" },
  { key: "direct", label: "Direct" },
];

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

function formatWeekLabel(metricDate: string): string {
  try {
    return `Săpt. ${getISOWeek(parse(metricDate, "yyyy-MM-dd", new Date()))}`;
  } catch {
    return "—";
  }
}

function getWeekNumberValue(metricDate: string): string {
  try {
    const parsed = parse(metricDate, "yyyy-MM-dd", new Date());
    if (Number.isNaN(parsed.getTime())) return "";
    return String(getISOWeek(parsed));
  } catch {
    return "";
  }
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

function normalizeDerivedLabels(config: DataConfigResponse | null): Record<string, string> {
  const mapped: Record<string, string> = { ...DERIVED_FIELD_FALLBACK_LABELS };
  for (const field of config?.derived_fields ?? []) {
    const key = String(field?.key || "").trim();
    const label = String(field?.label || "").trim();
    if (key && label) mapped[key] = label;
  }
  return mapped;
}

function normalizeActiveDynamicFields(config: DataConfigResponse | null): DynamicCustomFieldConfig[] {
  const fields = (config?.dynamic_custom_fields ?? config?.custom_fields ?? []).slice();
  return fields.filter((field) => Boolean(field?.is_active ?? true)).sort((a, b) => (Number(a.sort_order ?? 0) - Number(b.sort_order ?? 0)) || (Number(a.id) - Number(b.id)));
}

function normalizeRowCustomValues(row: DataTableRow): DynamicCustomValueRow[] {
  return (row.dynamic_custom_values ?? row.custom_values ?? []).slice();
}

function buildDailyDraft(row: DataTableRow): DailyRowDraft {
  const dynamicValues: Record<number, string> = {};
  for (const item of normalizeRowCustomValues(row)) {
    dynamicValues[Number(item.custom_field_id)] = String(item.numeric_value ?? "");
  }
  return {
    metric_date: row.metric_date,
    source: String(row.source ?? ""),
    leads: String(row.leads ?? ""),
    phones: String(row.phones ?? ""),
    custom_value_1_count: String(row.custom_value_1_count ?? ""),
    custom_value_2_count: String(row.custom_value_2_count ?? ""),
    custom_value_3_amount: String(row.custom_value_3_amount ?? ""),
    custom_value_4_amount: String(row.custom_value_4_amount ?? ""),
    sales_count: String(row.sales_count ?? ""),
    dynamicValues,
  };
}

function emptyDailyDraft(dateFrom: string): DailyRowDraft {
  return {
    metric_date: dateFrom,
    source: "",
    leads: "",
    phones: "",
    custom_value_1_count: "",
    custom_value_2_count: "",
    custom_value_3_amount: "",
    custom_value_4_amount: "",
    sales_count: "",
    dynamicValues: {},
  };
}

function emptySingleSaleDraft(): SingleSaleDraft {
  return {
    brand: "",
    model: "",
    sale_price_amount: "",
    actual_price_amount: "",
  };
}

export default function SubDataPage() {
  const params = useParams<{ id: string }>();
  const clientId = Number(params.id);
  const router = useRouter();
  const searchParams = useSearchParams();

  const monthDate = useMemo(() => parseMonthParam(searchParams.get("month")), [searchParams]);
  const dateFrom = useMemo(() => format(startOfMonth(monthDate), "yyyy-MM-dd"), [monthDate]);
  const dateTo = useMemo(() => format(endOfMonth(monthDate), "yyyy-MM-dd"), [monthDate]);

  const [clientName, setClientName] = useState("");
  const [config, setConfig] = useState<DataConfigResponse | null>(null);
  const [rows, setRows] = useState<DataTableRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [mutationError, setMutationError] = useState("");
  const [mutationSuccess, setMutationSuccess] = useState("");
  const [mutationLoadingKey, setMutationLoadingKey] = useState("");

  const [editingRowKey, setEditingRowKey] = useState("");
  const [editingRowDraft, setEditingRowDraft] = useState<DailyRowDraft | null>(null);
  const [addingRow, setAddingRow] = useState(false);
  const [newRowDraft, setNewRowDraft] = useState<DailyRowDraft>(() => emptyDailyDraft(format(startOfMonth(new Date()), "yyyy-MM-dd")));
  const [newRowSaleDraft, setNewRowSaleDraft] = useState<SingleSaleDraft>(() => emptySingleSaleDraft());

  const [openDetailsKeys, setOpenDetailsKeys] = useState<Record<string, boolean>>({});

  const [manageFieldsOpen, setManageFieldsOpen] = useState(false);
  const [showArchivedFields, setShowArchivedFields] = useState(false);
  const [managedCustomFields, setManagedCustomFields] = useState<DynamicCustomFieldConfig[]>([]);
  const [manageFieldsLoading, setManageFieldsLoading] = useState(false);
  const [manageFieldsError, setManageFieldsError] = useState("");
  const [createFieldDraft, setCreateFieldDraft] = useState({ label: "", value_kind: "count", sort_order: "" });
  const [editingFieldId, setEditingFieldId] = useState<number | null>(null);
  const [editingFieldDraft, setEditingFieldDraft] = useState({ label: "", value_kind: "count", sort_order: "" });

  const currencyCode = String(config?.currency_code || config?.display_currency || "USD").toUpperCase();
  const fixedLabels = useMemo(() => normalizeFixedLabels(config), [config]);
  const derivedLabels = useMemo(() => normalizeDerivedLabels(config), [config]);
  const activeDynamicFields = useMemo(() => normalizeActiveDynamicFields(config), [config]);
  const supportedSources = useMemo(() => (config?.sources?.length ? config.sources : SOURCE_FALLBACKS), [config?.sources]);

  const rowKeyOf = (row: DataTableRow) => `${row.metric_date}:${row.source ?? "unknown"}:${row.daily_input_id ?? ""}`;
  const newRowWeekValue = useMemo(() => getWeekNumberValue(newRowDraft.metric_date), [newRowDraft.metric_date]);
  const newRowCv3Raw = newRowDraft.custom_value_3_amount.trim();
  const newRowCv3Number = Number(newRowCv3Raw);
  const newRowHasValidCv3 = newRowCv3Raw !== "" && Number.isFinite(newRowCv3Number);
  const newRowCv4Raw = newRowDraft.custom_value_4_amount.trim();
  const newRowCv4Number = Number(newRowCv4Raw);
  const newRowHasValidCv4 = newRowCv4Raw !== "" && Number.isFinite(newRowCv4Number);
  const newRowSalePriceRaw = newRowSaleDraft.sale_price_amount.trim();
  const newRowActualPriceRaw = newRowSaleDraft.actual_price_amount.trim();
  const newRowSalePriceNumber = Number(newRowSalePriceRaw);
  const newRowActualPriceNumber = Number(newRowActualPriceRaw);
  const newRowSaleHasValidNumbers = newRowSalePriceRaw !== "" && newRowActualPriceRaw !== "" && Number.isFinite(newRowSalePriceNumber) && Number.isFinite(newRowActualPriceNumber);
  const newRowDerivedSoldAmount = newRowHasValidCv4 ? newRowCv4Number : 0;
  const newRowDerivedUnrealizedAmount = newRowHasValidCv3 ? (newRowCv3Number - newRowDerivedSoldAmount) : 0;
  const newRowDerivedGrossProfit = newRowSaleHasValidNumbers ? (newRowSalePriceNumber - newRowActualPriceNumber) : 0;

  async function loadClientName() {
    const result = await apiRequest<{ items: ClientItem[] }>("/clients");
    const match = result.items.find((item) => item.id === clientId);
    setClientName(match?.name || "");
  }

  async function loadConfig() {
    const configPayload = await apiRequest<DataConfigResponse>(`/clients/${clientId}/data/config`);
    setConfig(configPayload ?? null);
  }

  async function loadTable() {
    const tablePayload = await apiRequest<DataTableResponse>(`/clients/${clientId}/data/table?date_from=${dateFrom}&date_to=${dateTo}`);
    setRows(Array.isArray(tablePayload?.rows) ? tablePayload.rows : []);
  }

  async function refreshTable() {
    await loadTable();
  }

  async function refreshConfigAndTable() {
    await Promise.all([loadConfig(), loadTable()]);
  }

  async function loadManagedCustomFields(includeInactive: boolean) {
    setManageFieldsLoading(true);
    setManageFieldsError("");
    try {
      const query = includeInactive ? "?include_inactive=true" : "";
      const payload = await apiRequest<CustomFieldListResponse>(`/clients/${clientId}/data/custom-fields${query}`);
      const items = Array.isArray(payload?.items) ? payload.items : [];
      items.sort((a, b) => (Number(a.sort_order ?? 0) - Number(b.sort_order ?? 0)) || (Number(a.id) - Number(b.id)));
      setManagedCustomFields(items);
    } catch (err) {
      setManagedCustomFields([]);
      setManageFieldsError(err instanceof Error ? err.message : "Nu am putut încărca câmpurile custom.");
    } finally {
      setManageFieldsLoading(false);
    }
  }

  useEffect(() => {
    let ignore = false;
    async function run() {
      if (!Number.isFinite(clientId)) return;
      setLoading(true);
      setError("");
      try {
        await Promise.all([loadClientName(), refreshConfigAndTable()]);
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
    void run();
    return () => {
      ignore = true;
    };
  }, [clientId, dateFrom, dateTo]);

  useEffect(() => {
    if (!manageFieldsOpen) return;
    void loadManagedCustomFields(showArchivedFields);
  }, [manageFieldsOpen, showArchivedFields]);

  function updateMonth(next: Date) {
    const paramsCopy = new URLSearchParams(searchParams.toString());
    paramsCopy.set("month", format(startOfMonth(next), "yyyy-MM"));
    router.replace(`/sub/${clientId}/data?${paramsCopy.toString()}`);
  }

  function beginEditRow(row: DataTableRow) {
    setMutationError("");
    setMutationSuccess("");
    setEditingRowKey(rowKeyOf(row));
    setEditingRowDraft(buildDailyDraft(row));
  }

  async function saveRowDraft(currentRow: DataTableRow | null, draft: DailyRowDraft, isNew: boolean, saleDraft?: SingleSaleDraft) {
    const loadingKey = isNew ? "save-new-row" : `save-row:${editingRowKey}`;
    setMutationLoadingKey(loadingKey);
    setMutationError("");
    setMutationSuccess("");

    try {
      const normalizedSource = String(draft.source || "").trim().toLowerCase();
      const sourceKey = normalizedSource || "unknown";

      const dynamicCustomValuesPayload = activeDynamicFields
        .map((field) => {
          const raw = String(draft.dynamicValues[field.id] ?? "").trim();
          if (!raw) return null;
          const numeric = Number(raw);
          if (!Number.isFinite(numeric)) return null;
          return { custom_field_id: field.id, numeric_value: numeric };
        })
        .filter((item): item is { custom_field_id: number; numeric_value: number } => item !== null);

      const dailyPayload = {
        metric_date: draft.metric_date,
        source: sourceKey,
        leads: Number(draft.leads || 0),
        phones: Number(draft.phones || 0),
        custom_value_1_count: Number(draft.custom_value_1_count || 0),
        custom_value_2_count: Number(draft.custom_value_2_count || 0),
        custom_value_3_amount: Number(draft.custom_value_3_amount || 0),
        custom_value_4_amount: Number(draft.custom_value_4_amount || 0),
        sales_count: Number(draft.sales_count || 0),
        dynamic_custom_values: dynamicCustomValuesPayload,
      };

      const dailyInputWrite = isNew
        ? await apiRequest<{ id: number }>(`/clients/${clientId}/data/daily-inputs`, {
          method: "POST",
          body: JSON.stringify(dailyPayload),
        })
        : await apiRequest<{ id: number }>(`/clients/${clientId}/data/daily-inputs/${Number(currentRow?.daily_input_id ?? 0)}`, {
          method: "PATCH",
          body: JSON.stringify(dailyPayload),
        });

      if (isNew && saleDraft) {
        const rawSalePrice = String(saleDraft.sale_price_amount ?? "").trim();
        const rawActualPrice = String(saleDraft.actual_price_amount ?? "").trim();
        const hasSaleInput = [
          String(saleDraft.brand ?? "").trim(),
          String(saleDraft.model ?? "").trim(),
          rawSalePrice,
          rawActualPrice,
        ].some(Boolean);
        if (hasSaleInput) {
          const salePrice = Number(rawSalePrice);
          const actualPrice = Number(rawActualPrice);
          if (!rawSalePrice || !rawActualPrice || !Number.isFinite(salePrice) || !Number.isFinite(actualPrice)) {
            throw new Error("Completează coerent slotul de vânzare: Preț vânzare și Preț actual sunt obligatorii.");
          }
          if (salePrice < 0 || actualPrice < 0) {
            throw new Error("Preț vânzare și Preț actual trebuie să fie valori pozitive.");
          }
          await apiRequest(`/clients/${clientId}/data/sale-entries`, {
            method: "POST",
            body: JSON.stringify({
              daily_input_id: Number(dailyInputWrite.id),
              sale_price_amount: salePrice,
              actual_price_amount: actualPrice,
              ...(String(saleDraft.brand ?? "").trim() ? { brand: String(saleDraft.brand).trim() } : {}),
              ...(String(saleDraft.model ?? "").trim() ? { model: String(saleDraft.model).trim() } : {}),
            }),
          });
        }
      }

      await refreshTable();
      setMutationSuccess("Salvat");
      if (isNew) {
        setAddingRow(false);
        setNewRowDraft(emptyDailyDraft(dateFrom));
        setNewRowSaleDraft(emptySingleSaleDraft());
      } else {
        setEditingRowKey("");
        setEditingRowDraft(null);
      }
    } catch (err) {
      setMutationError(err instanceof Error ? err.message : "Nu am putut salva.");
    } finally {
      setMutationLoadingKey("");
    }
  }

  async function deleteRow(row: DataTableRow) {
    const dailyInputId = Number(row.daily_input_id ?? 0);
    if (!Number.isFinite(dailyInputId) || dailyInputId <= 0) {
      setMutationError("Nu am putut determina rândul pentru ștergere.");
      return;
    }
    if (typeof window !== "undefined" && !window.confirm("Ștergi definitiv acest rând?")) return;

    setMutationLoadingKey(`delete-row:${dailyInputId}`);
    setMutationError("");
    setMutationSuccess("");
    try {
      await apiRequest(`/clients/${clientId}/data/daily-inputs/${dailyInputId}`, { method: "DELETE" });
      await refreshTable();
      setMutationSuccess("Rândul a fost șters.");
    } catch (err) {
      setMutationError(err instanceof Error ? err.message : "Nu am putut șterge rândul.");
    } finally {
      setMutationLoadingKey("");
    }
  }

  async function createCustomField() {
    setMutationLoadingKey("create-custom-field");
    setMutationError("");
    setMutationSuccess("");
    try {
      await apiRequest(`/clients/${clientId}/data/custom-fields`, {
        method: "POST",
        body: JSON.stringify({
          label: createFieldDraft.label,
          value_kind: createFieldDraft.value_kind,
          ...(createFieldDraft.sort_order.trim() ? { sort_order: Number(createFieldDraft.sort_order) } : {}),
        }),
      });
      await Promise.all([loadConfig(), loadManagedCustomFields(showArchivedFields)]);
      setCreateFieldDraft({ label: "", value_kind: "count", sort_order: "" });
      setMutationSuccess("Câmpul custom a fost creat");
    } catch (err) {
      setMutationError(err instanceof Error ? err.message : "Nu am putut crea câmpul.");
    } finally {
      setMutationLoadingKey("");
    }
  }

  async function updateCustomField(fieldId: number) {
    setMutationLoadingKey(`update-custom-field:${fieldId}`);
    setMutationError("");
    setMutationSuccess("");
    try {
      await apiRequest(`/clients/${clientId}/data/custom-fields/${fieldId}`, {
        method: "PATCH",
        body: JSON.stringify({
          label: editingFieldDraft.label,
          value_kind: editingFieldDraft.value_kind,
          ...(editingFieldDraft.sort_order.trim() ? { sort_order: Number(editingFieldDraft.sort_order) } : {}),
        }),
      });
      await Promise.all([loadConfig(), loadManagedCustomFields(showArchivedFields)]);
      setEditingFieldId(null);
      setMutationSuccess("Câmpul custom a fost actualizat");
    } catch (err) {
      setMutationError(err instanceof Error ? err.message : "Nu am putut actualiza câmpul.");
    } finally {
      setMutationLoadingKey("");
    }
  }

  async function archiveCustomField(fieldId: number) {
    if (typeof window !== "undefined" && !window.confirm("Arhivezi acest câmp custom?")) return;
    setMutationLoadingKey(`archive-custom-field:${fieldId}`);
    setMutationError("");
    setMutationSuccess("");
    try {
      await apiRequest(`/clients/${clientId}/data/custom-fields/${fieldId}/archive`, { method: "POST" });
      await Promise.all([loadConfig(), loadManagedCustomFields(showArchivedFields)]);
      setMutationSuccess("Câmpul custom a fost arhivat");
    } catch (err) {
      setMutationError(err instanceof Error ? err.message : "Nu am putut arhiva câmpul.");
    } finally {
      setMutationLoadingKey("");
    }
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
              <p className="mt-1 text-sm text-slate-600">{dateFrom} - {dateTo} · Monedă: {currencyCode}</p>
              <p className="mt-1 text-sm text-indigo-700">Valorile salvate aici alimentează Media Buying și Media Tracker.</p>
            </div>
            <div className="flex items-center gap-2">
              <button type="button" className="rounded-md border border-slate-300 px-3 py-1.5 text-sm text-slate-700" onClick={() => updateMonth(addMonths(monthDate, -1))}>Luna anterioară</button>
              <span className="min-w-44 text-center text-sm font-medium text-slate-800">{formatMonthLabel(monthDate)}</span>
              <button type="button" className="rounded-md border border-slate-300 px-3 py-1.5 text-sm text-slate-700" onClick={() => updateMonth(addMonths(monthDate, 1))}>Luna următoare</button>
            </div>
          </div>

          <div className="mt-3 flex flex-wrap gap-2">
            <button type="button" className="rounded-md border border-indigo-300 px-3 py-1.5 text-sm text-indigo-700" onClick={() => { setAddingRow((v) => !v); setNewRowDraft(emptyDailyDraft(dateFrom)); setNewRowSaleDraft(emptySingleSaleDraft()); }}>
              Adaugă rând
            </button>
            <button type="button" className="rounded-md border border-indigo-300 px-3 py-1.5 text-sm text-indigo-700" onClick={() => setManageFieldsOpen((v) => !v)}>
              Gestionează câmpuri custom
            </button>
          </div>

          {mutationError ? <p className="mt-3 rounded-md border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">{mutationError}</p> : null}
          {mutationSuccess ? <p className="mt-3 rounded-md border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-700">{mutationSuccess}</p> : null}

          {manageFieldsOpen ? (
            <div className="mt-4 rounded-lg border border-slate-200 bg-white p-4">
              <h2 className="text-sm font-semibold text-slate-900">Gestionează câmpuri custom</h2>
              <label className="mt-2 inline-flex items-center gap-2 text-sm text-slate-700">
                <input
                  aria-label="Afișează și arhivate"
                  type="checkbox"
                  checked={showArchivedFields}
                  onChange={(e) => setShowArchivedFields(e.target.checked)}
                />
                Afișează și arhivate
              </label>
              <div className="mt-2 grid gap-2 md:grid-cols-4">
                <input aria-label="New field label" className="rounded border border-slate-300 px-2 py-1 text-sm" value={createFieldDraft.label} onChange={(e) => setCreateFieldDraft((p) => ({ ...p, label: e.target.value }))} placeholder="Label" />
                <select aria-label="New field type" className="rounded border border-slate-300 px-2 py-1 text-sm" value={createFieldDraft.value_kind} onChange={(e) => setCreateFieldDraft((p) => ({ ...p, value_kind: e.target.value }))}>
                  <option value="count">count</option>
                  <option value="amount">amount</option>
                </select>
                <input aria-label="New field sort" className="rounded border border-slate-300 px-2 py-1 text-sm" value={createFieldDraft.sort_order} onChange={(e) => setCreateFieldDraft((p) => ({ ...p, sort_order: e.target.value }))} placeholder="Sort order" />
                <button type="button" className="rounded border border-indigo-400 px-2 py-1 text-sm text-indigo-700" onClick={() => void createCustomField()} disabled={mutationLoadingKey === "create-custom-field"}>Creează câmp</button>
              </div>

              {manageFieldsLoading ? <p className="mt-3 text-sm text-slate-600">Se încarcă câmpurile custom...</p> : null}
              {!manageFieldsLoading && manageFieldsError ? <p className="mt-3 rounded border border-rose-200 bg-rose-50 px-2 py-1 text-sm text-rose-700">{manageFieldsError}</p> : null}
              {!manageFieldsLoading && !manageFieldsError && managedCustomFields.length === 0 ? <p className="mt-3 text-sm text-slate-600">Nu există câmpuri custom.</p> : null}

              <div className="mt-3 space-y-2">
                {managedCustomFields.map((field) => (
                  <div key={field.id} className={`rounded border p-2 text-sm ${field.is_active ? "border-slate-200" : "border-slate-300 bg-slate-50 text-slate-500"}`}>
                    {editingFieldId === field.id ? (
                      <div className="grid gap-2 md:grid-cols-4">
                        <input aria-label={`Editează label ${field.id}`} className="rounded border border-slate-300 px-2 py-1" value={editingFieldDraft.label} onChange={(e) => setEditingFieldDraft((p) => ({ ...p, label: e.target.value }))} />
                        <select aria-label={`Editează type ${field.id}`} className="rounded border border-slate-300 px-2 py-1" value={editingFieldDraft.value_kind} onChange={(e) => setEditingFieldDraft((p) => ({ ...p, value_kind: e.target.value }))}>
                          <option value="count">count</option>
                          <option value="amount">amount</option>
                        </select>
                        <input aria-label={`Editează sort ${field.id}`} className="rounded border border-slate-300 px-2 py-1" value={editingFieldDraft.sort_order} onChange={(e) => setEditingFieldDraft((p) => ({ ...p, sort_order: e.target.value }))} />
                        <div className="flex gap-2">
                          <button type="button" className="rounded border border-indigo-400 px-2 py-1 text-indigo-700" onClick={() => void updateCustomField(field.id)}>Save</button>
                          <button type="button" className="rounded border border-slate-300 px-2 py-1" onClick={() => setEditingFieldId(null)}>Anulează</button>
                        </div>
                      </div>
                    ) : (
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <span>{field.label} · {field.field_key} · {field.value_kind} · sort: {field.sort_order}{field.is_active ? "" : " · arhivat"}</span>
                        <div className="flex gap-2">
                          <button
                            type="button"
                            className="rounded border border-slate-300 px-2 py-1"
                            disabled={!field.is_active}
                            onClick={() => {
                              if (!field.is_active) return;
                              setEditingFieldId(field.id);
                              setEditingFieldDraft({ label: field.label, value_kind: field.value_kind || "count", sort_order: String(field.sort_order ?? "") });
                            }}
                          >
                            Editează
                          </button>
                          <button type="button" className="rounded border border-rose-300 px-2 py-1 text-rose-700 disabled:opacity-60" disabled={!field.is_active} onClick={() => void archiveCustomField(field.id)}>Arhivează</button>
                        </div>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          ) : null}

          {addingRow ? (
            <div className="mt-4 rounded-lg border border-slate-200 bg-slate-50 p-3 text-sm">
              <h3 className="mb-2 font-semibold text-slate-900">Adaugă rând</h3>
              <div className="grid gap-2 md:grid-cols-4">
                <div className="space-y-1"><label className="text-xs font-medium text-slate-700">Săptămâna</label><input aria-label="Săptămâna rând nou" className="w-full rounded border border-slate-300 bg-slate-100 px-2 py-1" value={newRowWeekValue} readOnly /></div>
                <div className="space-y-1"><label className="text-xs font-medium text-slate-700">Data vânzare</label><input aria-label="Data rând nou" type="date" className="w-full rounded border border-slate-300 px-2 py-1" value={newRowDraft.metric_date} onChange={(e) => setNewRowDraft((p) => ({ ...p, metric_date: e.target.value }))} /></div>
                <div className="space-y-1"><label className="text-xs font-medium text-slate-700">{fixedLabels.leads}</label><input aria-label="Lead-uri rând nou" className="w-full rounded border border-slate-300 px-2 py-1" value={newRowDraft.leads} onChange={(e) => setNewRowDraft((p) => ({ ...p, leads: e.target.value }))} /></div>
                <div className="space-y-1"><label className="text-xs font-medium text-slate-700">{fixedLabels.phones}</label><input aria-label="New row phones" className="w-full rounded border border-slate-300 px-2 py-1" value={newRowDraft.phones} onChange={(e) => setNewRowDraft((p) => ({ ...p, phones: e.target.value }))} /></div>
                <div className="space-y-1"><label className="text-xs font-medium text-slate-700">{fixedLabels.custom_value_1_count}</label><input aria-label="New row cv1" className="w-full rounded border border-slate-300 px-2 py-1" value={newRowDraft.custom_value_1_count} onChange={(e) => setNewRowDraft((p) => ({ ...p, custom_value_1_count: e.target.value }))} /></div>
                <div className="space-y-1"><label className="text-xs font-medium text-slate-700">{fixedLabels.custom_value_2_count}</label><input aria-label="New row cv2" className="w-full rounded border border-slate-300 px-2 py-1" value={newRowDraft.custom_value_2_count} onChange={(e) => setNewRowDraft((p) => ({ ...p, custom_value_2_count: e.target.value }))} /></div>
                <div className="space-y-1"><label className="text-xs font-medium text-slate-700">{fixedLabels.custom_value_3_amount}</label><input aria-label="New row cv3" className="w-full rounded border border-slate-300 px-2 py-1" value={newRowDraft.custom_value_3_amount} onChange={(e) => setNewRowDraft((p) => ({ ...p, custom_value_3_amount: e.target.value }))} /></div>
                <div className="space-y-1"><label className="text-xs font-medium text-slate-700">{fixedLabels.custom_value_4_amount}</label><input aria-label="Val. vândută rând nou" type="number" step="any" className="w-full rounded border border-slate-300 px-2 py-1" value={newRowDraft.custom_value_4_amount} onChange={(e) => setNewRowDraft((p) => ({ ...p, custom_value_4_amount: e.target.value }))} /></div>
                <div className="space-y-1"><label className="text-xs font-medium text-slate-700">{derivedLabels.custom_value_5_amount}</label><input aria-label="Val. nerealizată rând nou" className="w-full rounded border border-slate-300 bg-slate-100 px-2 py-1" value={newRowHasValidCv3 ? formatAmount(newRowDerivedUnrealizedAmount, currencyCode) : ""} readOnly /></div>
                <div className="space-y-1"><label className="text-xs font-medium text-slate-700">{fixedLabels.sales_count}</label><input aria-label="Vânzări rând nou" type="number" step="1" className="w-full rounded border border-slate-300 px-2 py-1" value={newRowDraft.sales_count} onChange={(e) => setNewRowDraft((p) => ({ ...p, sales_count: e.target.value }))} /></div>
                <div className="space-y-1"><label className="text-xs font-medium text-slate-700">Marcă</label><input aria-label="Marcă rând nou" className="w-full rounded border border-slate-300 px-2 py-1" value={newRowSaleDraft.brand} onChange={(e) => setNewRowSaleDraft((p) => ({ ...p, brand: e.target.value }))} /></div>
                <div className="space-y-1"><label className="text-xs font-medium text-slate-700">Model</label><input aria-label="Model rând nou" className="w-full rounded border border-slate-300 px-2 py-1" value={newRowSaleDraft.model} onChange={(e) => setNewRowSaleDraft((p) => ({ ...p, model: e.target.value }))} /></div>
                <div className="space-y-1"><label className="text-xs font-medium text-slate-700">Preț vânzare</label><input aria-label="Preț vânzare rând nou" type="number" step="any" className="w-full rounded border border-slate-300 px-2 py-1" value={newRowSaleDraft.sale_price_amount} onChange={(e) => setNewRowSaleDraft((p) => ({ ...p, sale_price_amount: e.target.value }))} /></div>
                <div className="space-y-1"><label className="text-xs font-medium text-slate-700">Preț actual</label><input aria-label="Preț actual rând nou" type="number" step="any" className="w-full rounded border border-slate-300 px-2 py-1" value={newRowSaleDraft.actual_price_amount} onChange={(e) => setNewRowSaleDraft((p) => ({ ...p, actual_price_amount: e.target.value }))} /></div>
                <div className="space-y-1"><label className="text-xs font-medium text-slate-700">{derivedLabels.gross_profit_amount}</label><input aria-label="Profit brut rând nou" className="w-full rounded border border-slate-300 bg-slate-100 px-2 py-1" value={newRowSaleHasValidNumbers ? formatAmount(newRowDerivedGrossProfit, currencyCode) : ""} readOnly /></div>
                <div className="space-y-1"><label className="text-xs font-medium text-slate-700">Sursa</label><select aria-label="Sursa rând nou" className="w-full rounded border border-slate-300 px-2 py-1" value={newRowDraft.source} onChange={(e) => setNewRowDraft((p) => ({ ...p, source: e.target.value }))}><option value=""> </option>{supportedSources.map((source) => <option key={source.key} value={source.key}>{source.label}</option>)}</select></div>
                {activeDynamicFields.map((field) => (
                  <div key={`new-dynamic-${field.id}`} className="space-y-1">
                    <label className="text-xs font-medium text-slate-700">{field.label}</label>
                    <input
                      aria-label={`Dynamic field ${field.label} rând nou`}
                      type="number"
                      step={field.value_kind === "count" ? "1" : "any"}
                      className="w-full rounded border border-slate-300 px-2 py-1"
                      value={newRowDraft.dynamicValues[field.id] ?? ""}
                      onChange={(e) => setNewRowDraft((p) => ({ ...p, dynamicValues: { ...p.dynamicValues, [field.id]: e.target.value } }))}
                    />
                  </div>
                ))}
              </div>
              <div className="mt-2 flex gap-2">
                <button type="button" className="rounded border border-indigo-400 px-3 py-1 text-indigo-700" disabled={mutationLoadingKey === "save-new-row"} onClick={() => void saveRowDraft(null, newRowDraft, true, newRowSaleDraft)}>Salvează rând</button>
                <button type="button" className="rounded border border-slate-300 px-3 py-1" onClick={() => setAddingRow(false)}>Anulează</button>
              </div>
            </div>
          ) : null}

          {loading ? <p className="mt-4 text-sm text-slate-600">Se încarcă tabelul de date...</p> : null}
          {!loading && error ? <p className="mt-4 rounded-md border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</p> : null}
          {!loading && !error && rows.length === 0 ? <p className="mt-4 rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-600">Nu există date pentru perioada selectată.</p> : null}

          {!loading && !error && rows.length > 0 ? (
            <div className="mt-4 overflow-x-auto">
              <table className="min-w-full border-collapse text-sm">
                <thead>
                  <tr className="bg-slate-50 text-left text-slate-700">
                    <th className="border border-slate-200 px-3 py-2">Săptămâna</th>
                    <th className="border border-slate-200 px-3 py-2">Data vânzare</th>
                    <th className="border border-slate-200 px-3 py-2">{fixedLabels.leads}</th>
                    <th className="border border-slate-200 px-3 py-2">{fixedLabels.phones}</th>
                    <th className="border border-slate-200 px-3 py-2">{fixedLabels.custom_value_1_count}</th>
                    <th className="border border-slate-200 px-3 py-2">{fixedLabels.custom_value_2_count}</th>
                    <th className="border border-slate-200 px-3 py-2">{fixedLabels.custom_value_3_amount}</th>
                    <th className="border border-slate-200 px-3 py-2">{fixedLabels.custom_value_4_amount}</th>
                    <th className="border border-slate-200 px-3 py-2">{derivedLabels.custom_value_5_amount}</th>
                    <th className="border border-slate-200 px-3 py-2">{fixedLabels.sales_count}</th>
                    <th className="border border-slate-200 px-3 py-2">Marcă</th>
                    <th className="border border-slate-200 px-3 py-2">Model</th>
                    <th className="border border-slate-200 px-3 py-2">Preț vânzare</th>
                    <th className="border border-slate-200 px-3 py-2">Preț actual</th>
                    <th className="border border-slate-200 px-3 py-2">{derivedLabels.gross_profit_amount}</th>
                    <th className="border border-slate-200 px-3 py-2">Sursa</th>
                    <th className="border border-slate-200 px-3 py-2">Acțiuni</th>
                    <th className="border border-slate-200 px-3 py-2">Detalii</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row) => {
                    const rowKey = rowKeyOf(row);
                    const isEditing = editingRowKey === rowKey && editingRowDraft !== null;
                    const draft = isEditing ? editingRowDraft : buildDailyDraft(row);
                    const derived = row.derived ?? {};
                    const firstSaleEntry = Array.isArray(row.sale_entries) && row.sale_entries.length > 0 ? row.sale_entries[0] : null;
                    const rowCustomValues = normalizeRowCustomValues(row);

                    return (
                      <React.Fragment key={rowKey}>
                        <tr className="align-top">
                          <td className="border border-slate-200 px-3 py-2">{formatWeekLabel(row.metric_date)}</td>
                          <td className="border border-slate-200 px-3 py-2">{row.metric_date}</td>
                          <td className="border border-slate-200 px-3 py-2">{isEditing ? <input aria-label={`Editează leads ${rowKey}`} className="w-24 rounded border border-slate-300 px-2 py-1" value={draft.leads} onChange={(e) => setEditingRowDraft((p) => (p ? { ...p, leads: e.target.value } : p))} /> : formatCount(row.leads)}</td>
                          <td className="border border-slate-200 px-3 py-2">{isEditing ? <input aria-label={`Editează phones ${rowKey}`} className="w-24 rounded border border-slate-300 px-2 py-1" value={draft.phones} onChange={(e) => setEditingRowDraft((p) => (p ? { ...p, phones: e.target.value } : p))} /> : formatCount(row.phones)}</td>
                          <td className="border border-slate-200 px-3 py-2">{isEditing ? <input className="w-24 rounded border border-slate-300 px-2 py-1" value={draft.custom_value_1_count} onChange={(e) => setEditingRowDraft((p) => (p ? { ...p, custom_value_1_count: e.target.value } : p))} /> : formatCount(row.custom_value_1_count)}</td>
                          <td className="border border-slate-200 px-3 py-2">{isEditing ? <input className="w-24 rounded border border-slate-300 px-2 py-1" value={draft.custom_value_2_count} onChange={(e) => setEditingRowDraft((p) => (p ? { ...p, custom_value_2_count: e.target.value } : p))} /> : formatCount(row.custom_value_2_count)}</td>
                          <td className="border border-slate-200 px-3 py-2">{isEditing ? <input className="w-24 rounded border border-slate-300 px-2 py-1" value={draft.custom_value_3_amount} onChange={(e) => setEditingRowDraft((p) => (p ? { ...p, custom_value_3_amount: e.target.value } : p))} /> : formatAmount(row.custom_value_3_amount, currencyCode)}</td>
                          <td className="border border-slate-200 px-3 py-2">{isEditing ? <input aria-label={`Editează val vândută ${rowKey}`} className="w-24 rounded border border-slate-300 px-2 py-1" value={draft.custom_value_4_amount} onChange={(e) => setEditingRowDraft((p) => (p ? { ...p, custom_value_4_amount: e.target.value } : p))} /> : formatAmount(row.custom_value_4_amount, currencyCode)}</td>
                          <td className="border border-slate-200 px-3 py-2">{formatAmount(derived.custom_value_5_amount ?? row.custom_value_5_amount, currencyCode)}</td>
                          <td className="border border-slate-200 px-3 py-2">{isEditing ? <input aria-label={`Editează vânzări ${rowKey}`} className="w-24 rounded border border-slate-300 px-2 py-1" value={draft.sales_count} onChange={(e) => setEditingRowDraft((p) => (p ? { ...p, sales_count: e.target.value } : p))} /> : formatCount(row.sales_count)}</td>
                          <td className="border border-slate-200 px-3 py-2">{firstSaleEntry?.brand || "—"}</td>
                          <td className="border border-slate-200 px-3 py-2">{firstSaleEntry?.model || "—"}</td>
                          <td className="border border-slate-200 px-3 py-2">{formatAmount(firstSaleEntry?.sale_price_amount, currencyCode)}</td>
                          <td className="border border-slate-200 px-3 py-2">{formatAmount(firstSaleEntry?.actual_price_amount, currencyCode)}</td>
                          <td className="border border-slate-200 px-3 py-2">{formatAmount(derived.gross_profit_amount ?? row.gross_profit_amount, currencyCode)}</td>
                          <td className="border border-slate-200 px-3 py-2">{row.source_label || "—"}</td>
                          <td className="border border-slate-200 px-3 py-2">
                            {isEditing ? (
                              <div className="flex gap-2">
                                <button type="button" className="rounded border border-indigo-400 px-2 py-1 text-xs text-indigo-700" disabled={mutationLoadingKey.startsWith("save-row") || mutationLoadingKey === "save-new-row"} onClick={() => void saveRowDraft(row, draft, false)}>Save</button>
                                <button type="button" className="rounded border border-slate-300 px-2 py-1 text-xs" onClick={() => { setEditingRowKey(""); setEditingRowDraft(null); }}>Anulează</button>
                              </div>
                            ) : (
                              <div className="flex gap-2">
                                <button type="button" className="rounded border border-slate-300 px-2 py-1 text-xs" onClick={() => beginEditRow(row)}>Editează</button>
                                <button
                                  type="button"
                                  className="rounded border border-rose-300 px-2 py-1 text-xs text-rose-700 disabled:opacity-60"
                                  disabled={mutationLoadingKey === `delete-row:${row.daily_input_id}`}
                                  onClick={() => void deleteRow(row)}
                                >
                                  Șterge rând
                                </button>
                              </div>
                            )}
                          </td>
                          <td className="border border-slate-200 px-3 py-2">
                            <details
                              open={Boolean(openDetailsKeys[rowKey])}
                              onToggle={(e) => {
                                const detailsElement = e.currentTarget as HTMLDetailsElement | null;
                                const isOpen = Boolean(detailsElement?.open);
                                setOpenDetailsKeys((prev) => ({ ...prev, [rowKey]: isOpen }));
                              }}
                            >
                              <summary className="cursor-pointer text-indigo-700">Vezi</summary>
                              <div className="mt-2 space-y-3">
                                {isEditing && activeDynamicFields.length > 0 ? (
                                  <div>
                                    <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-500">Câmpuri custom dinamice</p>
                                    <div className="grid gap-1 text-xs">
                                      {activeDynamicFields.map((field) => (
                                        <label key={`${rowKey}:edit-dynamic:${field.id}`} className="flex flex-col gap-1">
                                          <span>{field.label}</span>
                                          <input
                                            aria-label={`Editează dinamic ${field.label} ${rowKey}`}
                                            type="number"
                                            step={field.value_kind === "count" ? "1" : "any"}
                                            className="rounded border border-slate-300 px-2 py-1"
                                            value={draft.dynamicValues[field.id] ?? ""}
                                            onChange={(e) => setEditingRowDraft((p) => (p ? { ...p, dynamicValues: { ...p.dynamicValues, [field.id]: e.target.value } } : p))}
                                          />
                                        </label>
                                      ))}
                                    </div>
                                  </div>
                                ) : null}

                                <div>
                                  <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-500">Valori custom dinamice (istoric)</p>
                                  {rowCustomValues.length === 0 ? <p className="text-xs text-slate-500">—</p> : (
                                    <ul className="space-y-1 text-xs text-slate-700">
                                      {rowCustomValues.map((item, idx) => (
                                        <li key={`${rowKey}:custom:${item.custom_field_id}:${idx}`}>
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
