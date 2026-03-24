"use client";

import { addMonths, endOfMonth, format, parse, startOfMonth } from "date-fns";
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

type DailyRowDraft = {
  metric_date: string;
  source: string;
  leads: string;
  phones: string;
  custom_value_1_count: string;
  custom_value_2_count: string;
  custom_value_3_amount: string;
  custom_value_5_amount: string;
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
    custom_value_5_amount: String(row.custom_value_5_amount ?? ""),
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
    custom_value_5_amount: "",
    notes: "",
    dynamicValues: {},
  };
}

function emptySaleDraft(): SaleDraft {
  return { brand: "", model: "", sale_price_amount: "", actual_price_amount: "", notes: "", sort_order: "" };
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

  const [openDetailsKeys, setOpenDetailsKeys] = useState<Record<string, boolean>>({});
  const [addSaleForRowKey, setAddSaleForRowKey] = useState("");
  const [addSaleDraft, setAddSaleDraft] = useState<SaleDraft>(emptySaleDraft);
  const [editingSaleId, setEditingSaleId] = useState<number | null>(null);
  const [editingSaleDraft, setEditingSaleDraft] = useState<SaleDraft>(emptySaleDraft);

  const [manageFieldsOpen, setManageFieldsOpen] = useState(false);
  const [createFieldDraft, setCreateFieldDraft] = useState({ label: "", value_kind: "count", sort_order: "" });
  const [editingFieldId, setEditingFieldId] = useState<number | null>(null);
  const [editingFieldDraft, setEditingFieldDraft] = useState({ label: "", value_kind: "count", sort_order: "" });

  const currencyCode = String(config?.currency_code || config?.display_currency || "USD").toUpperCase();
  const fixedLabels = useMemo(() => normalizeFixedLabels(config), [config]);
  const activeDynamicFields = useMemo(() => normalizeActiveDynamicFields(config), [config]);
  const supportedSources = useMemo(() => (config?.sources?.length ? config.sources : SOURCE_FALLBACKS), [config?.sources]);

  const rowKeyOf = (row: DataTableRow) => `${row.metric_date}:${row.source ?? "unknown"}:${row.daily_input_id ?? ""}`;

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
      const dailyPayload = {
        metric_date: draft.metric_date,
        source: draft.source,
        leads: Number(draft.leads || 0),
        phones: Number(draft.phones || 0),
        custom_value_1_count: Number(draft.custom_value_1_count || 0),
        custom_value_2_count: Number(draft.custom_value_2_count || 0),
        custom_value_3_amount: Number(draft.custom_value_3_amount || 0),
        custom_value_5_amount: Number(draft.custom_value_5_amount || 0),
        notes: draft.notes.trim() || null,
      };

      const savedDaily = await apiRequest<{ id: number }>(`/clients/${clientId}/data/daily-input`, {
        method: "PUT",
        body: JSON.stringify(dailyPayload),
      });

      const dailyInputId = Number(savedDaily.id || currentRow?.daily_input_id || 0);
      if (dailyInputId > 0) {
        const beforeByField = new Map<number, DynamicCustomValueRow>(
          (currentRow ? normalizeRowCustomValues(currentRow) : []).map((item) => [Number(item.custom_field_id), item]),
        );

        for (const field of activeDynamicFields) {
          const draftValue = String(draft.dynamicValues[field.id] ?? "").trim();
          const existed = beforeByField.get(field.id);
          if (draftValue === "") {
            if (existed) {
              await apiRequest(`/clients/${clientId}/data/daily-inputs/${dailyInputId}/custom-values/${field.id}`, {
                method: "DELETE",
              });
            }
            continue;
          }

          await apiRequest(`/clients/${clientId}/data/daily-inputs/${dailyInputId}/custom-values/${field.id}`, {
            method: "PUT",
            body: JSON.stringify({ numeric_value: parseNumericInput(draftValue) ?? draftValue }),
          });
        }
      }

      await refreshTable();
      setMutationSuccess("Saved");
      if (isNew) {
        setAddingRow(false);
        setNewRowDraft(emptyDailyDraft(dateFrom));
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
      setMutationSuccess("Saved");
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
    if (typeof window !== "undefined" && !window.confirm("Delete sale entry?")) return;
    setMutationLoadingKey(`delete-sale:${saleId}`);
    setMutationError("");
    setMutationSuccess("");
    try {
      await apiRequest(`/clients/${clientId}/data/sale-entries/${saleId}`, { method: "DELETE" });
      await refreshTable();
      setOpenDetailsKeys((prev) => ({ ...prev, [rowKey]: true }));
      setMutationSuccess("Deleted");
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
      await refreshConfigAndTable();
      setCreateFieldDraft({ label: "", value_kind: "count", sort_order: "" });
      setMutationSuccess("Custom field created");
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
      await refreshConfigAndTable();
      setEditingFieldId(null);
      setMutationSuccess("Custom field updated");
    } catch (err) {
      setMutationError(err instanceof Error ? err.message : "Nu am putut actualiza câmpul.");
    } finally {
      setMutationLoadingKey("");
    }
  }

  async function archiveCustomField(fieldId: number) {
    if (typeof window !== "undefined" && !window.confirm("Archive custom field?")) return;
    setMutationLoadingKey(`archive-custom-field:${fieldId}`);
    setMutationError("");
    setMutationSuccess("");
    try {
      await apiRequest(`/clients/${clientId}/data/custom-fields/${fieldId}`, { method: "DELETE" });
      await refreshConfigAndTable();
      setMutationSuccess("Custom field archived");
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
              <p className="mt-1 text-sm text-slate-600">{dateFrom} - {dateTo} · Currency: {currencyCode}</p>
            </div>
            <div className="flex items-center gap-2">
              <button type="button" className="rounded-md border border-slate-300 px-3 py-1.5 text-sm text-slate-700" onClick={() => updateMonth(addMonths(monthDate, -1))}>Previous</button>
              <span className="min-w-44 text-center text-sm font-medium text-slate-800">{formatMonthLabel(monthDate)}</span>
              <button type="button" className="rounded-md border border-slate-300 px-3 py-1.5 text-sm text-slate-700" onClick={() => updateMonth(addMonths(monthDate, 1))}>Next</button>
            </div>
          </div>

          <div className="mt-3 flex flex-wrap gap-2">
            <button type="button" className="rounded-md border border-indigo-300 px-3 py-1.5 text-sm text-indigo-700" onClick={() => { setAddingRow((v) => !v); setNewRowDraft(emptyDailyDraft(dateFrom)); }}>
              Add row
            </button>
            <button type="button" className="rounded-md border border-indigo-300 px-3 py-1.5 text-sm text-indigo-700" onClick={() => setManageFieldsOpen((v) => !v)}>
              Manage custom fields
            </button>
          </div>

          {mutationError ? <p className="mt-3 rounded-md border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">{mutationError}</p> : null}
          {mutationSuccess ? <p className="mt-3 rounded-md border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-700">{mutationSuccess}</p> : null}

          {manageFieldsOpen ? (
            <div className="mt-4 rounded-lg border border-slate-200 bg-white p-4">
              <h2 className="text-sm font-semibold text-slate-900">Manage custom fields</h2>
              <div className="mt-2 grid gap-2 md:grid-cols-4">
                <input aria-label="New field label" className="rounded border border-slate-300 px-2 py-1 text-sm" value={createFieldDraft.label} onChange={(e) => setCreateFieldDraft((p) => ({ ...p, label: e.target.value }))} placeholder="Label" />
                <select aria-label="New field type" className="rounded border border-slate-300 px-2 py-1 text-sm" value={createFieldDraft.value_kind} onChange={(e) => setCreateFieldDraft((p) => ({ ...p, value_kind: e.target.value }))}>
                  <option value="count">count</option>
                  <option value="amount">amount</option>
                </select>
                <input aria-label="New field sort" className="rounded border border-slate-300 px-2 py-1 text-sm" value={createFieldDraft.sort_order} onChange={(e) => setCreateFieldDraft((p) => ({ ...p, sort_order: e.target.value }))} placeholder="Sort order" />
                <button type="button" className="rounded border border-indigo-400 px-2 py-1 text-sm text-indigo-700" onClick={() => void createCustomField()} disabled={mutationLoadingKey === "create-custom-field"}>Create field</button>
              </div>

              <div className="mt-3 space-y-2">
                {activeDynamicFields.map((field) => (
                  <div key={field.id} className="rounded border border-slate-200 p-2 text-sm">
                    {editingFieldId === field.id ? (
                      <div className="grid gap-2 md:grid-cols-4">
                        <input aria-label={`Edit label ${field.id}`} className="rounded border border-slate-300 px-2 py-1" value={editingFieldDraft.label} onChange={(e) => setEditingFieldDraft((p) => ({ ...p, label: e.target.value }))} />
                        <select aria-label={`Edit type ${field.id}`} className="rounded border border-slate-300 px-2 py-1" value={editingFieldDraft.value_kind} onChange={(e) => setEditingFieldDraft((p) => ({ ...p, value_kind: e.target.value }))}>
                          <option value="count">count</option>
                          <option value="amount">amount</option>
                        </select>
                        <input aria-label={`Edit sort ${field.id}`} className="rounded border border-slate-300 px-2 py-1" value={editingFieldDraft.sort_order} onChange={(e) => setEditingFieldDraft((p) => ({ ...p, sort_order: e.target.value }))} />
                        <div className="flex gap-2">
                          <button type="button" className="rounded border border-indigo-400 px-2 py-1 text-indigo-700" onClick={() => void updateCustomField(field.id)}>Save</button>
                          <button type="button" className="rounded border border-slate-300 px-2 py-1" onClick={() => setEditingFieldId(null)}>Cancel</button>
                        </div>
                      </div>
                    ) : (
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <span>{field.label} ({field.value_kind})</span>
                        <div className="flex gap-2">
                          <button
                            type="button"
                            className="rounded border border-slate-300 px-2 py-1"
                            onClick={() => {
                              setEditingFieldId(field.id);
                              setEditingFieldDraft({ label: field.label, value_kind: field.value_kind || "count", sort_order: String(field.sort_order ?? "") });
                            }}
                          >
                            Edit
                          </button>
                          <button type="button" className="rounded border border-rose-300 px-2 py-1 text-rose-700" onClick={() => void archiveCustomField(field.id)}>Archive</button>
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
              <h3 className="mb-2 font-semibold text-slate-900">Add row</h3>
              <div className="grid gap-2 md:grid-cols-4">
                <input aria-label="New row date" type="date" className="rounded border border-slate-300 px-2 py-1" value={newRowDraft.metric_date} onChange={(e) => setNewRowDraft((p) => ({ ...p, metric_date: e.target.value }))} />
                <select aria-label="New row source" className="rounded border border-slate-300 px-2 py-1" value={newRowDraft.source} onChange={(e) => setNewRowDraft((p) => ({ ...p, source: e.target.value }))}>
                  <option value="">Select source</option>
                  {supportedSources.map((source) => <option key={source.key} value={source.key}>{source.label}</option>)}
                </select>
                <input aria-label="New row leads" className="rounded border border-slate-300 px-2 py-1" value={newRowDraft.leads} onChange={(e) => setNewRowDraft((p) => ({ ...p, leads: e.target.value }))} placeholder={fixedLabels.leads} />
                <input aria-label="New row phones" className="rounded border border-slate-300 px-2 py-1" value={newRowDraft.phones} onChange={(e) => setNewRowDraft((p) => ({ ...p, phones: e.target.value }))} placeholder={fixedLabels.phones} />
                <input aria-label="New row cv1" className="rounded border border-slate-300 px-2 py-1" value={newRowDraft.custom_value_1_count} onChange={(e) => setNewRowDraft((p) => ({ ...p, custom_value_1_count: e.target.value }))} placeholder={fixedLabels.custom_value_1_count} />
                <input aria-label="New row cv2" className="rounded border border-slate-300 px-2 py-1" value={newRowDraft.custom_value_2_count} onChange={(e) => setNewRowDraft((p) => ({ ...p, custom_value_2_count: e.target.value }))} placeholder={fixedLabels.custom_value_2_count} />
                <input aria-label="New row cv3" className="rounded border border-slate-300 px-2 py-1" value={newRowDraft.custom_value_3_amount} onChange={(e) => setNewRowDraft((p) => ({ ...p, custom_value_3_amount: e.target.value }))} placeholder={fixedLabels.custom_value_3_amount} />
                <input aria-label="New row cv5" className="rounded border border-slate-300 px-2 py-1" value={newRowDraft.custom_value_5_amount} onChange={(e) => setNewRowDraft((p) => ({ ...p, custom_value_5_amount: e.target.value }))} placeholder={fixedLabels.custom_value_5_amount} />
              </div>
              <textarea aria-label="New row notes" className="mt-2 w-full rounded border border-slate-300 px-2 py-1" rows={2} value={newRowDraft.notes} onChange={(e) => setNewRowDraft((p) => ({ ...p, notes: e.target.value }))} placeholder="Mențiuni" />
              <div className="mt-2 flex gap-2">
                <button type="button" className="rounded border border-indigo-400 px-3 py-1 text-indigo-700" disabled={mutationLoadingKey === "save-new-row"} onClick={() => void saveRowDraft(null, newRowDraft, true)}>Save row</button>
                <button type="button" className="rounded border border-slate-300 px-3 py-1" onClick={() => setAddingRow(false)}>Cancel</button>
              </div>
            </div>
          ) : null}

          {loading ? <p className="mt-4 text-sm text-slate-600">Loading data table...</p> : null}
          {!loading && error ? <p className="mt-4 rounded-md border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</p> : null}
          {!loading && !error && rows.length === 0 ? <p className="mt-4 rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-600">Nu există date pentru perioada selectată.</p> : null}

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
                    {activeDynamicFields.map((field) => <th key={field.id} className="border border-slate-200 px-3 py-2">{field.label}</th>)}
                    <th className="border border-slate-200 px-3 py-2">Vânzări</th>
                    <th className="border border-slate-200 px-3 py-2">Venit</th>
                    <th className="border border-slate-200 px-3 py-2">COGS</th>
                    <th className="border border-slate-200 px-3 py-2">Profit Brut</th>
                    <th className="border border-slate-200 px-3 py-2">Mențiuni</th>
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
                          <td className="border border-slate-200 px-3 py-2">{row.metric_date}</td>
                          <td className="border border-slate-200 px-3 py-2">{row.source_label || "—"}</td>
                          <td className="border border-slate-200 px-3 py-2">{isEditing ? <input aria-label={`Edit leads ${rowKey}`} className="w-24 rounded border border-slate-300 px-2 py-1" value={draft.leads} onChange={(e) => setEditingRowDraft((p) => (p ? { ...p, leads: e.target.value } : p))} /> : formatCount(row.leads)}</td>
                          <td className="border border-slate-200 px-3 py-2">{isEditing ? <input aria-label={`Edit phones ${rowKey}`} className="w-24 rounded border border-slate-300 px-2 py-1" value={draft.phones} onChange={(e) => setEditingRowDraft((p) => (p ? { ...p, phones: e.target.value } : p))} /> : formatCount(row.phones)}</td>
                          <td className="border border-slate-200 px-3 py-2">{isEditing ? <input className="w-24 rounded border border-slate-300 px-2 py-1" value={draft.custom_value_1_count} onChange={(e) => setEditingRowDraft((p) => (p ? { ...p, custom_value_1_count: e.target.value } : p))} /> : formatCount(row.custom_value_1_count)}</td>
                          <td className="border border-slate-200 px-3 py-2">{isEditing ? <input className="w-24 rounded border border-slate-300 px-2 py-1" value={draft.custom_value_2_count} onChange={(e) => setEditingRowDraft((p) => (p ? { ...p, custom_value_2_count: e.target.value } : p))} /> : formatCount(row.custom_value_2_count)}</td>
                          <td className="border border-slate-200 px-3 py-2">{isEditing ? <input className="w-24 rounded border border-slate-300 px-2 py-1" value={draft.custom_value_3_amount} onChange={(e) => setEditingRowDraft((p) => (p ? { ...p, custom_value_3_amount: e.target.value } : p))} /> : formatAmount(row.custom_value_3_amount, currencyCode)}</td>
                          <td className="border border-slate-200 px-3 py-2">{formatAmount(derived.custom_value_4_amount ?? row.custom_value_4_amount, currencyCode)}</td>
                          <td className="border border-slate-200 px-3 py-2">{isEditing ? <input className="w-24 rounded border border-slate-300 px-2 py-1" value={draft.custom_value_5_amount} onChange={(e) => setEditingRowDraft((p) => (p ? { ...p, custom_value_5_amount: e.target.value } : p))} /> : formatAmount(row.custom_value_5_amount, currencyCode)}</td>
                          {activeDynamicFields.map((field) => (
                            <td key={field.id} className="border border-slate-200 px-3 py-2">
                              {isEditing ? (
                                <input
                                  aria-label={`Edit dynamic ${field.id} ${rowKey}`}
                                  className="w-24 rounded border border-slate-300 px-2 py-1"
                                  value={draft.dynamicValues[field.id] ?? ""}
                                  onChange={(e) => setEditingRowDraft((p) => (p ? { ...p, dynamicValues: { ...p.dynamicValues, [field.id]: e.target.value } } : p))}
                                />
                              ) : (
                                byField.get(field.id) ? (byField.get(field.id)?.value_kind === "amount" ? formatAmount(byField.get(field.id)?.numeric_value, currencyCode) : formatCount(byField.get(field.id)?.numeric_value)) : "—"
                              )}
                            </td>
                          ))}
                          <td className="border border-slate-200 px-3 py-2">{formatCount(derived.sales_count ?? row.sales_count)}</td>
                          <td className="border border-slate-200 px-3 py-2">{formatAmount(derived.revenue_amount ?? row.revenue_amount, currencyCode)}</td>
                          <td className="border border-slate-200 px-3 py-2">{formatAmount(derived.cogs_amount ?? row.cogs_amount, currencyCode)}</td>
                          <td className="border border-slate-200 px-3 py-2">{formatAmount(derived.gross_profit_amount ?? row.gross_profit_amount, currencyCode)}</td>
                          <td className="border border-slate-200 px-3 py-2">{isEditing ? <textarea aria-label={`Edit notes ${rowKey}`} className="w-40 rounded border border-slate-300 px-2 py-1" rows={2} value={draft.notes} onChange={(e) => setEditingRowDraft((p) => (p ? { ...p, notes: e.target.value } : p))} /> : String(row.notes || "").trim() || "—"}</td>
                          <td className="border border-slate-200 px-3 py-2">
                            {isEditing ? (
                              <div className="flex gap-2">
                                <button type="button" className="rounded border border-indigo-400 px-2 py-1 text-xs text-indigo-700" disabled={mutationLoadingKey.startsWith("save-row") || mutationLoadingKey === "save-new-row"} onClick={() => void saveRowDraft(row, draft, false)}>Save</button>
                                <button type="button" className="rounded border border-slate-300 px-2 py-1 text-xs" onClick={() => { setEditingRowKey(""); setEditingRowDraft(null); }}>Cancel</button>
                              </div>
                            ) : (
                              <button type="button" className="rounded border border-slate-300 px-2 py-1 text-xs" onClick={() => beginEditRow(row)}>Edit</button>
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
                              <summary className="cursor-pointer text-indigo-700">View</summary>
                              <div className="mt-2 space-y-3">
                                <div>
                                  <div className="mb-1 flex items-center justify-between gap-2">
                                    <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Sale entries</p>
                                    <button type="button" className="rounded border border-indigo-300 px-2 py-0.5 text-xs text-indigo-700" onClick={() => { setAddSaleForRowKey(rowKey); setAddSaleDraft(emptySaleDraft()); }}>Add sale</button>
                                  </div>
                                  {addSaleForRowKey === rowKey ? (
                                    <div className="mb-2 grid gap-1 text-xs">
                                      <input aria-label={`Add sale brand ${rowKey}`} className="rounded border border-slate-300 px-2 py-1" value={addSaleDraft.brand} onChange={(e) => setAddSaleDraft((p) => ({ ...p, brand: e.target.value }))} placeholder="Brand" />
                                      <input className="rounded border border-slate-300 px-2 py-1" value={addSaleDraft.model} onChange={(e) => setAddSaleDraft((p) => ({ ...p, model: e.target.value }))} placeholder="Model" />
                                      <input aria-label={`Add sale price ${rowKey}`} className="rounded border border-slate-300 px-2 py-1" value={addSaleDraft.sale_price_amount} onChange={(e) => setAddSaleDraft((p) => ({ ...p, sale_price_amount: e.target.value }))} placeholder="Preț Vânzare" />
                                      <input className="rounded border border-slate-300 px-2 py-1" value={addSaleDraft.actual_price_amount} onChange={(e) => setAddSaleDraft((p) => ({ ...p, actual_price_amount: e.target.value }))} placeholder="Preț Actual" />
                                      <input className="rounded border border-slate-300 px-2 py-1" value={addSaleDraft.notes} onChange={(e) => setAddSaleDraft((p) => ({ ...p, notes: e.target.value }))} placeholder="Mențiuni" />
                                      <div className="flex gap-1">
                                        <button type="button" className="rounded border border-indigo-300 px-2 py-0.5 text-indigo-700" onClick={() => void saveSale(row)}>Save sale</button>
                                        <button type="button" className="rounded border border-slate-300 px-2 py-0.5" onClick={() => setAddSaleForRowKey("")}>Cancel</button>
                                      </div>
                                    </div>
                                  ) : null}

                                  {saleEntries.length === 0 ? <p className="text-xs text-slate-500">—</p> : (
                                    <table className="min-w-full border-collapse text-xs">
                                      <thead>
                                        <tr className="bg-slate-50 text-left">
                                          <th className="border border-slate-200 px-2 py-1">Brand</th>
                                          <th className="border border-slate-200 px-2 py-1">Model</th>
                                          <th className="border border-slate-200 px-2 py-1">Preț Vânzare</th>
                                          <th className="border border-slate-200 px-2 py-1">Preț Actual</th>
                                          <th className="border border-slate-200 px-2 py-1">Profit Brut</th>
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
                                              <td className="border border-slate-200 px-2 py-1">{isEditingSale ? <input aria-label={`Edit sale price ${saleId}`} value={editingSaleDraft.sale_price_amount} onChange={(e) => setEditingSaleDraft((p) => ({ ...p, sale_price_amount: e.target.value }))} className="w-20 rounded border border-slate-300 px-1 py-0.5" /> : formatAmount(entry.sale_price_amount, currencyCode)}</td>
                                              <td className="border border-slate-200 px-2 py-1">{isEditingSale ? <input value={editingSaleDraft.actual_price_amount} onChange={(e) => setEditingSaleDraft((p) => ({ ...p, actual_price_amount: e.target.value }))} className="w-20 rounded border border-slate-300 px-1 py-0.5" /> : formatAmount(entry.actual_price_amount, currencyCode)}</td>
                                              <td className="border border-slate-200 px-2 py-1">{formatAmount(entry.gross_profit_amount, currencyCode)}</td>
                                              <td className="border border-slate-200 px-2 py-1">{isEditingSale ? <input value={editingSaleDraft.notes} onChange={(e) => setEditingSaleDraft((p) => ({ ...p, notes: e.target.value }))} className="w-24 rounded border border-slate-300 px-1 py-0.5" /> : String(entry.notes || "").trim() || "—"}</td>
                                              <td className="border border-slate-200 px-2 py-1">
                                                {isEditingSale ? (
                                                  <div className="flex gap-1">
                                                    <button type="button" className="rounded border border-indigo-300 px-1 py-0.5 text-indigo-700" onClick={() => void saveSale(row, saleId)}>Save</button>
                                                    <button type="button" className="rounded border border-slate-300 px-1 py-0.5" onClick={() => setEditingSaleId(null)}>Cancel</button>
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
                                                      Edit
                                                    </button>
                                                    <button type="button" className="rounded border border-rose-300 px-1 py-0.5 text-rose-700" onClick={() => void deleteSale(rowKey, saleId)}>Delete</button>
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
                                  <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-500">Dynamic custom values (historical)</p>
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
