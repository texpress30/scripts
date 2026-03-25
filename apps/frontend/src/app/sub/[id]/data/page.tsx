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
type DynamicCustomFieldConfig = { id: number; field_key: string; label: string; value_kind?: "count" | "amount"; sort_order?: number; is_active?: boolean };

type DataConfigResponse = {
  currency_code?: string;
  display_currency?: string;
  sources?: SourceItem[];
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
  sort_order?: number | null;
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
  custom_value_5_amount: string;
  sales_count: string;
  notes: string;
  dynamicValues: Record<number, string>;
};

type SaleDraft = {
  brand: string;
  model: string;
  sale_price_amount: string;
  actual_price_amount: string;
  notes: string;
  sort_order: string;
};

type NewRowSaleDraft = {
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
  custom_value_5_amount: "Custom 5",
};

const SOURCE_FALLBACKS: SourceItem[] = [
  { key: "meta_ads", label: "Meta" },
  { key: "google_ads", label: "Google" },
  { key: "tiktok_ads", label: "TikTok" },
  { key: "organic", label: "Organic" },
  { key: "manual", label: "Manual" },
];

function parseMonthParam(value: string | null): Date {
  if (!value) return startOfMonth(new Date());
  const parsed = parse(value, "yyyy-MM", new Date());
  if (Number.isNaN(parsed.getTime())) return startOfMonth(new Date());
  return startOfMonth(parsed);
}

function parseNumericInput(value: string): number | string | undefined {
  const trimmed = value.trim();
  if (!trimmed) return undefined;
  const parsed = Number(trimmed);
  if (!Number.isFinite(parsed)) return trimmed;
  return parsed;
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
    custom_value_5_amount: String(row.custom_value_5_amount ?? ""),
    sales_count: String(row.sales_count ?? ""),
    notes: String(row.notes ?? ""),
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
    custom_value_5_amount: "",
    sales_count: "",
    notes: "",
    dynamicValues: {},
  };
}

function emptySaleDraft(): SaleDraft {
  return { brand: "", model: "", sale_price_amount: "", actual_price_amount: "", notes: "", sort_order: "" };
}

function emptyNewRowSaleDraft(): NewRowSaleDraft {
  return { brand: "", model: "", sale_price_amount: "", actual_price_amount: "" };
}

function hasAnySaleDraftInput(draft: NewRowSaleDraft): boolean {
  return Boolean(
    draft.brand.trim()
      || draft.model.trim()
      || draft.sale_price_amount.trim()
      || draft.actual_price_amount.trim(),
  );
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
  const [newRowSaleDrafts, setNewRowSaleDrafts] = useState<NewRowSaleDraft[]>([emptyNewRowSaleDraft()]);

  const [openDetailsKeys, setOpenDetailsKeys] = useState<Record<string, boolean>>({});
  const [addSaleForRowKey, setAddSaleForRowKey] = useState("");
  const [addSaleDraft, setAddSaleDraft] = useState<SaleDraft>(emptySaleDraft);
  const [editingSaleId, setEditingSaleId] = useState<number | null>(null);
  const [editingSaleDraft, setEditingSaleDraft] = useState<SaleDraft>(emptySaleDraft);

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
  const activeDynamicFields = useMemo(() => normalizeActiveDynamicFields(config), [config]);
  const supportedSources = useMemo(() => (config?.sources?.length ? config.sources : SOURCE_FALLBACKS), [config?.sources]);

  const rowKeyOf = (row: DataTableRow) => `${row.metric_date}:${row.source ?? "unknown"}:${row.daily_input_id ?? ""}`;
  const newRowWeekValue = useMemo(() => getWeekNumberValue(newRowDraft.metric_date), [newRowDraft.metric_date]);
  const hasAnyNewRowSaleInput = newRowSaleDrafts.some((draft) => hasAnySaleDraftInput(draft));
  const newRowCv3Raw = newRowDraft.custom_value_3_amount.trim();
  const newRowCv4Raw = newRowDraft.custom_value_4_amount.trim();
  const newRowCv3Number = Number(newRowCv3Raw);
  const newRowCv4Number = Number(newRowCv4Raw);
  const newRowHasValidCv3 = newRowCv3Raw !== "" && Number.isFinite(newRowCv3Number);
  const newRowHasValidCv4 = newRowCv4Raw !== "" && Number.isFinite(newRowCv4Number);
  const newRowDerivedUnrealizedDisplay = (newRowHasValidCv3 && newRowHasValidCv4) ? formatAmount(newRowCv3Number - newRowCv4Number, currencyCode) : "";

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

  async function saveRowDraft(currentRow: DataTableRow | null, draft: DailyRowDraft, isNew: boolean) {
    const loadingKey = isNew ? "save-new-row" : `save-row:${editingRowKey}`;
    setMutationLoadingKey(loadingKey);
    setMutationError("");
    setMutationSuccess("");

    try {
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
        source: draft.source,
        leads: Number(draft.leads || 0),
        phones: Number(draft.phones || 0),
        custom_value_1_count: Number(draft.custom_value_1_count || 0),
        custom_value_2_count: Number(draft.custom_value_2_count || 0),
        custom_value_3_amount: Number(draft.custom_value_3_amount || 0),
        custom_value_4_amount: Number(draft.custom_value_4_amount || 0),
        custom_value_5_amount: Number((Number(draft.custom_value_3_amount || 0) - Number(draft.custom_value_4_amount || 0))),
        sales_count: Number(draft.sales_count || 0),
        notes: draft.notes.trim() || null,
        dynamic_custom_values: dynamicCustomValuesPayload,
      };

      const savedDaily = await apiRequest<{ id: number }>(`/clients/${clientId}/data/daily-input`, {
        method: "PUT",
        body: JSON.stringify(dailyPayload),
      });

      const dailyInputId = Number(savedDaily.id || currentRow?.daily_input_id || 0);
      if (dailyInputId > 0 && isNew && hasAnyNewRowSaleInput) {
        const salePayloads = newRowSaleDrafts
          .map((draft) => {
            if (!hasAnySaleDraftInput(draft)) return null;
            const parsedSalePrice = parseNumericInput(draft.sale_price_amount);
            const parsedActualPrice = parseNumericInput(draft.actual_price_amount);
            if (parsedSalePrice == null || parsedActualPrice == null) {
              throw new Error("Completează cel puțin Preț vânzare și Preț actual pentru fiecare vânzare completată.");
            }
            return {
              daily_input_id: dailyInputId,
              brand: draft.brand.trim() || null,
              model: draft.model.trim() || null,
              sale_price_amount: parsedSalePrice,
              actual_price_amount: parsedActualPrice,
            };
          })
          .filter((entry): entry is { daily_input_id: number; brand: string | null; model: string | null; sale_price_amount: number | string; actual_price_amount: number | string } => entry !== null);

        for (const salePayload of salePayloads) {
          await apiRequest(`/clients/${clientId}/data/sale-entries`, {
            method: "POST",
            body: JSON.stringify(salePayload),
          });
        }
      }

      await refreshTable();
      setMutationSuccess("Salvat");
      if (isNew) {
        setAddingRow(false);
        setNewRowDraft(emptyDailyDraft(dateFrom));
        setNewRowSaleDrafts([emptyNewRowSaleDraft()]);
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

  async function saveSale(row: DataTableRow, saleId?: number) {
    const rowKey = rowKeyOf(row);
    const isEdit = Boolean(saleId);
    const loadingKey = isEdit ? `patch-sale:${saleId}` : `add-sale:${rowKey}`;
    setMutationLoadingKey(loadingKey);
    setMutationError("");
    setMutationSuccess("");

    try {
      const draft = isEdit ? editingSaleDraft : addSaleDraft;
      const payload = {
        brand: draft.brand,
        model: draft.model,
        sale_price_amount: parseNumericInput(draft.sale_price_amount),
        actual_price_amount: parseNumericInput(draft.actual_price_amount),
        notes: draft.notes,
        ...(draft.sort_order.trim() ? { sort_order: Number(draft.sort_order) } : {}),
      };

      if (!isEdit) {
        await apiRequest(`/clients/${clientId}/data/sale-entries`, {
          method: "POST",
          body: JSON.stringify({ ...payload, daily_input_id: row.daily_input_id }),
        });
      } else {
        await apiRequest(`/clients/${clientId}/data/sale-entries/${saleId}`, {
          method: "PATCH",
          body: JSON.stringify(payload),
        });
      }

      await refreshTable();
      setOpenDetailsKeys((prev) => ({ ...prev, [rowKey]: true }));
      setMutationSuccess("Salvat");
      setAddSaleForRowKey("");
      setAddSaleDraft(emptySaleDraft());
      setEditingSaleId(null);
      setEditingSaleDraft(emptySaleDraft());
    } catch (err) {
      setMutationError(err instanceof Error ? err.message : "Nu am putut salva vânzarea.");
    } finally {
      setMutationLoadingKey("");
    }
  }

  async function deleteSale(rowKey: string, saleId: number) {
    if (typeof window !== "undefined" && !window.confirm("Ștergi această vânzare?")) return;
    setMutationLoadingKey(`delete-sale:${saleId}`);
    setMutationError("");
    setMutationSuccess("");
    try {
      await apiRequest(`/clients/${clientId}/data/sale-entries/${saleId}`, { method: "DELETE" });
      await refreshTable();
      setOpenDetailsKeys((prev) => ({ ...prev, [rowKey]: true }));
      setMutationSuccess("Șters");
    } catch (err) {
      setMutationError(err instanceof Error ? err.message : "Nu am putut șterge vânzarea.");
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
            </div>
            <div className="flex items-center gap-2">
              <button type="button" className="rounded-md border border-slate-300 px-3 py-1.5 text-sm text-slate-700" onClick={() => updateMonth(addMonths(monthDate, -1))}>Luna anterioară</button>
              <span className="min-w-44 text-center text-sm font-medium text-slate-800">{formatMonthLabel(monthDate)}</span>
              <button type="button" className="rounded-md border border-slate-300 px-3 py-1.5 text-sm text-slate-700" onClick={() => updateMonth(addMonths(monthDate, 1))}>Luna următoare</button>
            </div>
          </div>

          <div className="mt-3 flex flex-wrap gap-2">
            <button type="button" className="rounded-md border border-indigo-300 px-3 py-1.5 text-sm text-indigo-700" onClick={() => { setAddingRow((v) => !v); setNewRowDraft(emptyDailyDraft(dateFrom)); setNewRowSaleDrafts([emptyNewRowSaleDraft()]); }}>
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
                <div className="space-y-1"><label className="text-xs font-medium text-slate-700">Sursa</label><select aria-label="Sursa rând nou" className="w-full rounded border border-slate-300 px-2 py-1" value={newRowDraft.source} onChange={(e) => setNewRowDraft((p) => ({ ...p, source: e.target.value }))}><option value=""> </option>{supportedSources.map((source) => <option key={source.key} value={source.key}>{source.label}</option>)}</select></div>
                <div className="space-y-1"><label className="text-xs font-medium text-slate-700">Lead-uri</label><input aria-label="Lead-uri rând nou" className="w-full rounded border border-slate-300 px-2 py-1" value={newRowDraft.leads} onChange={(e) => setNewRowDraft((p) => ({ ...p, leads: e.target.value }))} /></div>
                <div className="space-y-1"><label className="text-xs font-medium text-slate-700">Telefoane</label><input aria-label="New row phones" className="w-full rounded border border-slate-300 px-2 py-1" value={newRowDraft.phones} onChange={(e) => setNewRowDraft((p) => ({ ...p, phones: e.target.value }))} /></div>
                <div className="space-y-1"><label className="text-xs font-medium text-slate-700">{fixedLabels.custom_value_1_count}</label><input aria-label="New row cv1" className="w-full rounded border border-slate-300 px-2 py-1" value={newRowDraft.custom_value_1_count} onChange={(e) => setNewRowDraft((p) => ({ ...p, custom_value_1_count: e.target.value }))} /></div>
                <div className="space-y-1"><label className="text-xs font-medium text-slate-700">{fixedLabels.custom_value_2_count}</label><input aria-label="New row cv2" className="w-full rounded border border-slate-300 px-2 py-1" value={newRowDraft.custom_value_2_count} onChange={(e) => setNewRowDraft((p) => ({ ...p, custom_value_2_count: e.target.value }))} /></div>
                <div className="space-y-1"><label className="text-xs font-medium text-slate-700">{fixedLabels.custom_value_3_amount}</label><input aria-label="New row cv3" className="w-full rounded border border-slate-300 px-2 py-1" value={newRowDraft.custom_value_3_amount} onChange={(e) => setNewRowDraft((p) => ({ ...p, custom_value_3_amount: e.target.value }))} /></div>
                <div className="space-y-1"><label className="text-xs font-medium text-slate-700">{fixedLabels.custom_value_4_amount}</label><input aria-label="Custom Value 4 rând nou" className="w-full rounded border border-slate-300 px-2 py-1" value={newRowDraft.custom_value_4_amount} onChange={(e) => setNewRowDraft((p) => ({ ...p, custom_value_4_amount: e.target.value }))} /></div>
                <div className="space-y-1"><label className="text-xs font-medium text-slate-700">{fixedLabels.custom_value_5_amount}</label><input aria-label="New row cv5" className="w-full rounded border border-slate-300 bg-slate-100 px-2 py-1" value={newRowDerivedUnrealizedDisplay} readOnly /></div>
                <div className="space-y-1"><label className="text-xs font-medium text-slate-700">Vânzări</label><input aria-label="Vânzări rând nou" className="w-full rounded border border-slate-300 px-2 py-1" value={newRowDraft.sales_count} onChange={(e) => setNewRowDraft((p) => ({ ...p, sales_count: e.target.value }))} /></div>
                {newRowSaleDrafts.map((saleDraft, index) => {
                  const salePriceRaw = saleDraft.sale_price_amount.trim();
                  const actualPriceRaw = saleDraft.actual_price_amount.trim();
                  const salePriceNumber = Number(salePriceRaw);
                  const actualPriceNumber = Number(actualPriceRaw);
                  const hasValidSalePrice = salePriceRaw !== "" && Number.isFinite(salePriceNumber);
                  const hasValidActualPrice = actualPriceRaw !== "" && Number.isFinite(actualPriceNumber);
                  const derivedGrossProfitDisplay = (hasValidSalePrice && hasValidActualPrice)
                    ? formatAmount(salePriceNumber - actualPriceNumber, currencyCode)
                    : "";
                  const saleLabelSuffix = ` ${index + 1}`;
                  return (
                    <React.Fragment key={`new-row-sale-${index}`}>
                      <div className="space-y-1"><label className="text-xs font-medium text-slate-700">Marcă{saleLabelSuffix}</label><input aria-label={`Marcă rând nou${saleLabelSuffix}`} className="w-full rounded border border-slate-300 px-2 py-1" value={saleDraft.brand} onChange={(e) => setNewRowSaleDrafts((prev) => prev.map((item, itemIndex) => (itemIndex === index ? { ...item, brand: e.target.value } : item)))} /></div>
                      <div className="space-y-1"><label className="text-xs font-medium text-slate-700">Model{saleLabelSuffix}</label><input aria-label={`Model rând nou${saleLabelSuffix}`} className="w-full rounded border border-slate-300 px-2 py-1" value={saleDraft.model} onChange={(e) => setNewRowSaleDrafts((prev) => prev.map((item, itemIndex) => (itemIndex === index ? { ...item, model: e.target.value } : item)))} /></div>
                      <div className="space-y-1"><label className="text-xs font-medium text-slate-700">Preț vânzare{saleLabelSuffix}</label><input aria-label={`Preț vânzare rând nou${saleLabelSuffix}`} className="w-full rounded border border-slate-300 px-2 py-1" value={saleDraft.sale_price_amount} onChange={(e) => setNewRowSaleDrafts((prev) => prev.map((item, itemIndex) => (itemIndex === index ? { ...item, sale_price_amount: e.target.value } : item)))} /></div>
                      <div className="space-y-1"><label className="text-xs font-medium text-slate-700">Preț actual{saleLabelSuffix}</label><input aria-label={`Preț actual rând nou${saleLabelSuffix}`} className="w-full rounded border border-slate-300 px-2 py-1" value={saleDraft.actual_price_amount} onChange={(e) => setNewRowSaleDrafts((prev) => prev.map((item, itemIndex) => (itemIndex === index ? { ...item, actual_price_amount: e.target.value } : item)))} /></div>
                      <div className="space-y-1"><label className="text-xs font-medium text-slate-700">P/L brut{saleLabelSuffix}</label><input aria-label={`P/L brut rând nou${saleLabelSuffix}`} className="w-full rounded border border-slate-300 bg-slate-100 px-2 py-1" value={derivedGrossProfitDisplay} readOnly /></div>
                      <div className="flex items-end">
                        <button
                          type="button"
                          className="rounded border border-rose-300 px-2 py-1 text-rose-700 disabled:opacity-60"
                          disabled={newRowSaleDrafts.length <= 1}
                          onClick={() => setNewRowSaleDrafts((prev) => prev.filter((_, itemIndex) => itemIndex !== index))}
                        >
                          Șterge vânzarea {index + 1}
                        </button>
                      </div>
                    </React.Fragment>
                  );
                })}
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
              <div className="mt-2">
                <button
                  type="button"
                  className="rounded border border-indigo-300 px-3 py-1 text-indigo-700"
                  onClick={() => setNewRowSaleDrafts((prev) => [...prev, emptyNewRowSaleDraft()])}
                >
                  Adaugă încă o vânzare
                </button>
              </div>
              <div className="mt-2 space-y-1">
                <label className="text-xs font-medium text-slate-700">Mențiuni</label>
                <textarea aria-label="New row notes" className="w-full rounded border border-slate-300 px-2 py-1" rows={2} value={newRowDraft.notes} onChange={(e) => setNewRowDraft((p) => ({ ...p, notes: e.target.value }))} />
              </div>
              <div className="mt-2 flex gap-2">
                <button type="button" className="rounded border border-indigo-400 px-3 py-1 text-indigo-700" disabled={mutationLoadingKey === "save-new-row"} onClick={() => void saveRowDraft(null, newRowDraft, true)}>Salvează rând</button>
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
                    <th className="border border-slate-200 px-3 py-2">{fixedLabels.custom_value_5_amount}</th>
                    <th className="border border-slate-200 px-3 py-2">Vânzări</th>
                    <th className="border border-slate-200 px-3 py-2">Marcă</th>
                    <th className="border border-slate-200 px-3 py-2">Model</th>
                    <th className="border border-slate-200 px-3 py-2">Preț vânzare</th>
                    <th className="border border-slate-200 px-3 py-2">Preț actual</th>
                    <th className="border border-slate-200 px-3 py-2">P/L brut</th>
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
                    const saleEntries = row.sale_entries ?? [];
                    const rowCustomValues = normalizeRowCustomValues(row);
                    const byField = new Map(rowCustomValues.map((item) => [Number(item.custom_field_id), item]));

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
                          <td className="border border-slate-200 px-3 py-2">{formatAmount(derived.custom_value_4_amount ?? row.custom_value_4_amount, currencyCode)}</td>
                          <td className="border border-slate-200 px-3 py-2">{isEditing ? <input className="w-24 rounded border border-slate-300 px-2 py-1" value={draft.custom_value_5_amount} onChange={(e) => setEditingRowDraft((p) => (p ? { ...p, custom_value_5_amount: e.target.value } : p))} /> : formatAmount(row.custom_value_5_amount, currencyCode)}</td>
                          <td className="border border-slate-200 px-3 py-2">{formatCount(derived.sales_count ?? row.sales_count)}</td>
                          <td className="border border-slate-200 px-3 py-2">{String(saleEntries[0]?.brand || "").trim() || "—"}</td>
                          <td className="border border-slate-200 px-3 py-2">{String(saleEntries[0]?.model || "").trim() || "—"}</td>
                          <td className="border border-slate-200 px-3 py-2">{formatAmount(saleEntries[0]?.sale_price_amount, currencyCode)}</td>
                          <td className="border border-slate-200 px-3 py-2">{formatAmount(saleEntries[0]?.actual_price_amount, currencyCode)}</td>
                          <td className="border border-slate-200 px-3 py-2">{formatAmount(saleEntries[0]?.gross_profit_amount, currencyCode)}</td>
                          <td className="border border-slate-200 px-3 py-2">{row.source_label || "—"}</td>
                          <td className="border border-slate-200 px-3 py-2">
                            {isEditing ? (
                              <div className="flex gap-2">
                                <button type="button" className="rounded border border-indigo-400 px-2 py-1 text-xs text-indigo-700" disabled={mutationLoadingKey.startsWith("save-row") || mutationLoadingKey === "save-new-row"} onClick={() => void saveRowDraft(row, draft, false)}>Save</button>
                                <button type="button" className="rounded border border-slate-300 px-2 py-1 text-xs" onClick={() => { setEditingRowKey(""); setEditingRowDraft(null); }}>Anulează</button>
                              </div>
                            ) : (
                              <button type="button" className="rounded border border-slate-300 px-2 py-1 text-xs" onClick={() => beginEditRow(row)}>Editează</button>
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
                                  <div className="mb-1 flex items-center justify-between gap-2">
                                    <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Vânzări</p>
                                    <button type="button" className="rounded border border-indigo-300 px-2 py-0.5 text-xs text-indigo-700" onClick={() => { setAddSaleForRowKey(rowKey); setAddSaleDraft(emptySaleDraft()); }}>Adaugă vânzare</button>
                                  </div>
                                  {addSaleForRowKey === rowKey ? (
                                    <div className="mb-2 grid gap-1 text-xs">
                                      <input aria-label={`Adaugă vânzare brand ${rowKey}`} className="rounded border border-slate-300 px-2 py-1" value={addSaleDraft.brand} onChange={(e) => setAddSaleDraft((p) => ({ ...p, brand: e.target.value }))} placeholder="Marcă" />
                                      <input className="rounded border border-slate-300 px-2 py-1" value={addSaleDraft.model} onChange={(e) => setAddSaleDraft((p) => ({ ...p, model: e.target.value }))} placeholder="Model" />
                                      <input aria-label={`Adaugă vânzare price ${rowKey}`} className="rounded border border-slate-300 px-2 py-1" value={addSaleDraft.sale_price_amount} onChange={(e) => setAddSaleDraft((p) => ({ ...p, sale_price_amount: e.target.value }))} placeholder="Preț vânzare" />
                                      <input className="rounded border border-slate-300 px-2 py-1" value={addSaleDraft.actual_price_amount} onChange={(e) => setAddSaleDraft((p) => ({ ...p, actual_price_amount: e.target.value }))} placeholder="Preț actual" />
                                      <input className="rounded border border-slate-300 px-2 py-1" value={addSaleDraft.notes} onChange={(e) => setAddSaleDraft((p) => ({ ...p, notes: e.target.value }))} placeholder="Mențiuni" />
                                      <div className="flex gap-1">
                                        <button type="button" className="rounded border border-indigo-300 px-2 py-0.5 text-indigo-700" onClick={() => void saveSale(row)}>Salvează vânzarea</button>
                                        <button type="button" className="rounded border border-slate-300 px-2 py-0.5" onClick={() => setAddSaleForRowKey("")}>Anulează</button>
                                      </div>
                                    </div>
                                  ) : null}

                                  {saleEntries.length === 0 ? <p className="text-xs text-slate-500">—</p> : (
                                    <table className="min-w-full border-collapse text-xs">
                                      <thead>
                                        <tr className="bg-slate-50 text-left">
                                          <th className="border border-slate-200 px-2 py-1">Marcă</th>
                                          <th className="border border-slate-200 px-2 py-1">Model</th>
                                          <th className="border border-slate-200 px-2 py-1">Preț vânzare</th>
                                          <th className="border border-slate-200 px-2 py-1">Preț actual</th>
                                          <th className="border border-slate-200 px-2 py-1">P/L brut</th>
                                          <th className="border border-slate-200 px-2 py-1">Mențiuni</th>
                                          <th className="border border-slate-200 px-2 py-1">Acțiuni</th>
                                        </tr>
                                      </thead>
                                      <tbody>
                                        {saleEntries.map((entry, idx) => {
                                          const saleId = Number(entry.id || 0);
                                          const isEditingSale = editingSaleId === saleId;
                                          return (
                                            <tr key={`${rowKey}:sale:${saleId || idx}`}>
                                              <td className="border border-slate-200 px-2 py-1">{isEditingSale ? <input value={editingSaleDraft.brand} onChange={(e) => setEditingSaleDraft((p) => ({ ...p, brand: e.target.value }))} className="w-20 rounded border border-slate-300 px-1 py-0.5" /> : String(entry.brand || "").trim() || "—"}</td>
                                              <td className="border border-slate-200 px-2 py-1">{isEditingSale ? <input value={editingSaleDraft.model} onChange={(e) => setEditingSaleDraft((p) => ({ ...p, model: e.target.value }))} className="w-20 rounded border border-slate-300 px-1 py-0.5" /> : String(entry.model || "").trim() || "—"}</td>
                                              <td className="border border-slate-200 px-2 py-1">{isEditingSale ? <input aria-label={`Editează sale price ${saleId}`} value={editingSaleDraft.sale_price_amount} onChange={(e) => setEditingSaleDraft((p) => ({ ...p, sale_price_amount: e.target.value }))} className="w-20 rounded border border-slate-300 px-1 py-0.5" /> : formatAmount(entry.sale_price_amount, currencyCode)}</td>
                                              <td className="border border-slate-200 px-2 py-1">{isEditingSale ? <input value={editingSaleDraft.actual_price_amount} onChange={(e) => setEditingSaleDraft((p) => ({ ...p, actual_price_amount: e.target.value }))} className="w-20 rounded border border-slate-300 px-1 py-0.5" /> : formatAmount(entry.actual_price_amount, currencyCode)}</td>
                                              <td className="border border-slate-200 px-2 py-1">{formatAmount(entry.gross_profit_amount, currencyCode)}</td>
                                              <td className="border border-slate-200 px-2 py-1">{isEditingSale ? <input value={editingSaleDraft.notes} onChange={(e) => setEditingSaleDraft((p) => ({ ...p, notes: e.target.value }))} className="w-24 rounded border border-slate-300 px-1 py-0.5" /> : String(entry.notes || "").trim() || "—"}</td>
                                              <td className="border border-slate-200 px-2 py-1">
                                                {isEditingSale ? (
                                                  <div className="flex gap-1">
                                                    <button type="button" className="rounded border border-indigo-300 px-1 py-0.5 text-indigo-700" onClick={() => void saveSale(row, saleId)}>Save</button>
                                                    <button type="button" className="rounded border border-slate-300 px-1 py-0.5" onClick={() => setEditingSaleId(null)}>Anulează</button>
                                                  </div>
                                                ) : (
                                                  <div className="flex gap-1">
                                                    <button
                                                      type="button"
                                                      className="rounded border border-slate-300 px-1 py-0.5"
                                                      onClick={() => {
                                                        setEditingSaleId(saleId);
                                                        setEditingSaleDraft({
                                                          brand: String(entry.brand || ""),
                                                          model: String(entry.model || ""),
                                                          sale_price_amount: String(entry.sale_price_amount ?? ""),
                                                          actual_price_amount: String(entry.actual_price_amount ?? ""),
                                                          notes: String(entry.notes || ""),
                                                          sort_order: String(entry.sort_order ?? ""),
                                                        });
                                                      }}
                                                    >
                                                      Editează
                                                    </button>
                                                    <button type="button" className="rounded border border-rose-300 px-1 py-0.5 text-rose-700" onClick={() => void deleteSale(rowKey, saleId)}>Șterge</button>
                                                  </div>
                                                )}
                                              </td>
                                            </tr>
                                          );
                                        })}
                                      </tbody>
                                    </table>
                                  )}
                                </div>

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
