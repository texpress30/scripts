"use client";

import { useState, useCallback, useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, ArrowRight, Loader2, Save, CheckCircle2, ChevronRight } from "lucide-react";
import { MasterFieldRow, type MasterFieldRowValue } from "@/components/feed-management/MasterFieldRow";
import { useMasterFields, useSaveMasterFields, type BulkMappingItem } from "@/lib/hooks/useMasterFields";

const CATALOG_LABELS: Record<string, string> = {
  product: "Product",
  vehicle: "Vehicle",
  vehicle_offer: "Vehicle Offer",
  home_listing: "Home Listing",
  hotel: "Hotel",
  hotel_room: "Hotel Room",
  flight: "Flight",
  trip: "Trip",
  media: "Media",
};

export default function MasterFieldsPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const sourceId = params.id;

  const { data, isLoading, error } = useMasterFields(sourceId);
  const { save, isSaving } = useSaveMasterFields(sourceId);

  const [localMappings, setLocalMappings] = useState<Record<string, MasterFieldRowValue>>({});
  const [saveStatus, setSaveStatus] = useState<"idle" | "saved">("idle");
  const [showSourceFields, setShowSourceFields] = useState(false);

  // Initialize local state from fetched data
  useEffect(() => {
    if (!data) return;
    const map: Record<string, MasterFieldRowValue> = {};

    // Existing mappings
    for (const m of data.mappings) {
      map[m.target_field] = {
        target_field: m.target_field,
        source_field: m.source_field,
        mapping_type: m.mapping_type,
        static_value: m.static_value,
        template_value: m.template_value,
        is_required: m.is_required,
        sort_order: m.sort_order,
      };
    }

    // Suggestions for unmapped fields (pre-fill with suggested source field)
    for (const s of data.suggestions) {
      if (!map[s.target_field]) {
        map[s.target_field] = {
          target_field: s.target_field,
          source_field: s.suggested_source_field,
          mapping_type: "direct",
          static_value: null,
          template_value: null,
          is_required: s.required,
          sort_order: 0,
        };
      }
    }

    setLocalMappings(map);
  }, [data]);

  const handleChange = useCallback((target: string, value: MasterFieldRowValue) => {
    setLocalMappings((prev) => ({ ...prev, [target]: value }));
    setSaveStatus("idle");
  }, []);

  async function handleSave() {
    const items: BulkMappingItem[] = Object.values(localMappings)
      .filter((m) => m.source_field || m.static_value || m.template_value)
      .map((m, i) => ({
        target_field: m.target_field,
        source_field: m.source_field,
        mapping_type: m.mapping_type,
        static_value: m.static_value,
        template_value: m.template_value,
        is_required: m.is_required,
        sort_order: i,
      }));
    await save(items);
    setSaveStatus("saved");
    setTimeout(() => setSaveStatus("idle"), 3000);
  }

  async function handleSaveAndGoToChannels() {
    await handleSave();
    router.push("/agency/feed-management/channels");
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-16">
        <Loader2 className="h-6 w-6 animate-spin text-slate-400" />
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="py-8">
        <Link
          href="/agency/feed-management/field-mapping"
          className="mb-4 inline-flex items-center gap-1 text-sm text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-300"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to Field Mapping
        </Link>
        <p className="text-red-600">{error ?? "Source not found."}</p>
      </div>
    );
  }

  // Split into required and optional
  const allFields = [...data.mappings.map((m) => ({
    target_field: m.target_field,
    display_name: m.target_field.replace(/_/g, " ").replace(/\b\w/g, (c: string) => c.toUpperCase()),
    description: "",
    field_type: "string",
    required: m.is_required,
    category: "mapped",
    suggested_source_field: null as string | null,
  })), ...data.suggestions];

  // Deduplicate by target_field
  const seen = new Set<string>();
  const uniqueFields = allFields.filter((f) => {
    if (seen.has(f.target_field)) return false;
    seen.add(f.target_field);
    return true;
  });

  const requiredFields = uniqueFields.filter((f) => f.required);
  const optionalFields = uniqueFields.filter((f) => !f.required);

  return (
    <>
      <Link
        href="/agency/feed-management/field-mapping"
        className="mb-4 inline-flex items-center gap-1 text-sm text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-300"
      >
        <ArrowLeft className="h-4 w-4" />
        Back to Field Mapping
      </Link>

      {/* Header */}
      <div className="mb-6">
        <h1 className="text-xl font-semibold text-slate-900 dark:text-slate-100">
          Map Master Fields &mdash; {data.source_name}
        </h1>
        <div className="mt-1 flex items-center gap-2">
          <span className="rounded bg-indigo-100 px-2 py-0.5 text-xs font-medium text-indigo-700 dark:bg-indigo-900/40 dark:text-indigo-400">
            {CATALOG_LABELS[data.catalog_type] ?? data.catalog_type}
          </span>
          <span className="text-xs text-slate-400">
            {data.mapped_count} / {data.total_schema_fields} fields mapped
          </span>
        </div>
        <p className="mt-2 text-sm text-slate-500 dark:text-slate-400">
          This is a library of universal rules for your feed. You can use them later for every channel.
        </p>
      </div>

      {/* Source Fields Reference Panel */}
      {data.source_fields.length > 0 && (
        <div className="mb-6 rounded-lg border border-slate-200 bg-slate-50 dark:border-slate-700 dark:bg-slate-900/50">
          <button
            type="button"
            onClick={() => setShowSourceFields((v) => !v)}
            className="flex w-full items-center justify-between p-3 text-left"
          >
            <div>
              <h2 className="text-sm font-semibold text-slate-700 dark:text-slate-300">
                Available Source Fields ({data.source_fields.length})
              </h2>
              <p className="text-xs text-slate-400 dark:text-slate-500">
                These fields are available from your connected source. Use them in the mappings below.
              </p>
            </div>
            <ChevronRight
              className={`h-4 w-4 text-slate-400 transition-transform ${showSourceFields ? "rotate-90" : ""}`}
            />
          </button>
          {showSourceFields && (
            <div className="border-t border-slate-200 p-3 dark:border-slate-700">
              <div className="grid grid-cols-1 gap-1 sm:grid-cols-2 lg:grid-cols-3">
                {data.source_fields.map((sf) => (
                  <div
                    key={sf.field}
                    className="flex items-center gap-2 rounded px-2 py-1.5 text-sm hover:bg-white dark:hover:bg-slate-800"
                  >
                    <span className="font-mono text-xs font-medium text-slate-700 dark:text-slate-300">
                      {sf.field}
                    </span>
                    <span className="rounded bg-slate-200 px-1 py-0.5 text-[10px] text-slate-500 dark:bg-slate-700 dark:text-slate-400">
                      {sf.type}
                    </span>
                    {sf.sample && (
                      <span
                        className="truncate text-[11px] text-slate-400 dark:text-slate-500"
                        title={sf.sample}
                      >
                        {sf.sample.length > 30 ? sf.sample.slice(0, 30) + "…" : sf.sample}
                      </span>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Required Fields */}
      {requiredFields.length > 0 && (
        <div className="mb-6">
          <h2 className="mb-3 text-sm font-semibold text-slate-700 dark:text-slate-300">
            Required Fields ({requiredFields.length})
          </h2>
          <div className="space-y-2">
            {requiredFields.map((field) => (
              <MasterFieldRow
                key={field.target_field}
                targetField={field.target_field}
                displayName={field.display_name}
                description={field.description}
                required={true}
                category={field.category}
                fieldType={field.field_type}
                suggestedSourceField={field.suggested_source_field}
                sourceFields={data.source_fields}
                value={localMappings[field.target_field] ?? {
                  target_field: field.target_field,
                  source_field: null,
                  mapping_type: "direct" as const,
                  static_value: null,
                  template_value: null,
                  is_required: true,
                  sort_order: 0,
                }}
                onChange={(v) => handleChange(field.target_field, v)}
              />
            ))}
          </div>
        </div>
      )}

      {/* Optional Fields */}
      {optionalFields.length > 0 && (
        <div className="mb-6">
          <h2 className="mb-3 text-sm font-semibold text-slate-700 dark:text-slate-300">
            Optional Fields ({optionalFields.length})
          </h2>
          <div className="space-y-2">
            {optionalFields.map((field) => (
              <MasterFieldRow
                key={field.target_field}
                targetField={field.target_field}
                displayName={field.display_name}
                description={field.description}
                required={false}
                category={field.category}
                fieldType={field.field_type}
                suggestedSourceField={field.suggested_source_field}
                sourceFields={data.source_fields}
                value={localMappings[field.target_field] ?? {
                  target_field: field.target_field,
                  source_field: null,
                  mapping_type: "direct" as const,
                  static_value: null,
                  template_value: null,
                  is_required: false,
                  sort_order: 0,
                }}
                onChange={(v) => handleChange(field.target_field, v)}
              />
            ))}
          </div>
        </div>
      )}

      {/* Actions */}
      <div className="sticky bottom-0 flex items-center gap-3 border-t border-slate-200 bg-white py-4 dark:border-slate-700 dark:bg-slate-950">
        <button
          type="button"
          onClick={() => void handleSave()}
          disabled={isSaving}
          className="wm-btn-secondary inline-flex items-center gap-2"
        >
          {isSaving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
          Save Changes
        </button>
        <button
          type="button"
          onClick={() => void handleSaveAndGoToChannels()}
          disabled={isSaving}
          className="wm-btn-primary inline-flex items-center gap-2"
        >
          {isSaving ? <Loader2 className="h-4 w-4 animate-spin" /> : <ArrowRight className="h-4 w-4" />}
          Save and Go to Channels
        </button>
        {saveStatus === "saved" && (
          <span className="inline-flex items-center gap-1 text-sm text-emerald-600 dark:text-emerald-400">
            <CheckCircle2 className="h-4 w-4" />
            Saved
          </span>
        )}
      </div>
    </>
  );
}
