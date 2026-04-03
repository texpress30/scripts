"use client";

import { useState, useCallback } from "react";
import { ChevronDown, ChevronUp, RotateCcw, Save, Loader2 } from "lucide-react";
import {
  useChannelFields,
  type ChannelSchemaField,
  type ChannelFieldMapping,
  type SourceField,
} from "@/lib/hooks/useMasterFields";
import { apiRequest } from "@/lib/api";

const CHANNEL_TYPE_LABELS: Record<string, string> = {
  google_vehicle_ads_v3: "Google Vehicle Ads",
  google_vehicle_listings: "Google Vehicle Listings",
  google_shopping: "Google Shopping",
  facebook_product_ads: "Facebook Product Ads",
  tiktok_auto_inventory: "TikTok Automotive Inventory",
  tiktok_catalog: "TikTok Catalog",
  meta_catalog: "Meta Catalog",
  custom: "Custom",
};

type OverrideEdit = {
  canonical_key: string;
  source_field: string | null;
  mapping_type: "direct" | "static" | "template";
  static_value: string | null;
  template_value: string | null;
};

type Props = {
  channelId: string;
  sourceFields?: SourceField[];
};

export function ChannelFieldsSection({ channelId, sourceFields = [] }: Props) {
  const { data, isLoading, error, refetch } = useChannelFields(channelId);
  const [expanded, setExpanded] = useState(true);
  const [editingField, setEditingField] = useState<string | null>(null);
  const [overrideEdits, setOverrideEdits] = useState<Record<string, OverrideEdit>>({});
  const [saving, setSaving] = useState(false);
  const [saveMsg, setSaveMsg] = useState<string | null>(null);

  const handleStartOverride = useCallback((field: ChannelSchemaField) => {
    const mapping = field.mapping;
    setEditingField(field.canonical_key);
    setOverrideEdits((prev) => ({
      ...prev,
      [field.canonical_key]: {
        canonical_key: field.canonical_key,
        source_field: mapping?.source_field ?? null,
        mapping_type: (mapping?.type as "direct" | "static" | "template") ?? "direct",
        static_value: mapping?.static_value ?? null,
        template_value: mapping?.template_value ?? null,
      },
    }));
  }, []);

  const handleCancelEdit = useCallback(() => {
    setEditingField(null);
  }, []);

  const handleSaveOverride = useCallback(
    async (canonicalKey: string) => {
      const edit = overrideEdits[canonicalKey];
      if (!edit) return;

      setSaving(true);
      setSaveMsg(null);
      try {
        await apiRequest(`/channels/${channelId}/overrides`, {
          method: "POST",
          body: JSON.stringify({
            overrides: [
              {
                target_field: canonicalKey,
                source_field: edit.source_field,
                mapping_type: edit.mapping_type,
                static_value: edit.static_value,
                template_value: edit.template_value,
              },
            ],
          }),
        });
        setEditingField(null);
        refetch();
        setSaveMsg("Override saved");
        setTimeout(() => setSaveMsg(null), 2000);
      } catch (err) {
        setSaveMsg(err instanceof Error ? err.message : "Failed to save");
      } finally {
        setSaving(false);
      }
    },
    [channelId, overrideEdits, refetch],
  );

  const handleResetToMaster = useCallback(
    async (canonicalKey: string) => {
      setSaving(true);
      try {
        // Get current overrides, remove this one
        const res = await apiRequest<{ items: Array<{ target_field: string }> }>(
          `/channels/${channelId}/overrides`,
        );
        const remaining = (res.items || [])
          .filter((o) => o.target_field !== canonicalKey);
        await apiRequest(`/channels/${channelId}/overrides`, {
          method: "POST",
          body: JSON.stringify({ overrides: remaining }),
        });
        setEditingField(null);
        refetch();
        setSaveMsg("Reset to master mapping");
        setTimeout(() => setSaveMsg(null), 2000);
      } catch (err) {
        setSaveMsg(err instanceof Error ? err.message : "Failed to reset");
      } finally {
        setSaving(false);
      }
    },
    [channelId, refetch],
  );

  if (isLoading) {
    return (
      <div className="wm-card p-4">
        <div className="flex items-center gap-2 text-sm text-slate-400">
          <Loader2 className="h-4 w-4 animate-spin" />
          Loading channel fields...
        </div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="wm-card p-4">
        <p className="text-sm text-slate-400">Channel fields not available.</p>
      </div>
    );
  }

  const channelLabel = CHANNEL_TYPE_LABELS[data.channel_type] ?? data.channel_type;

  return (
    <div className="wm-card">
      {/* Header */}
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        className="flex w-full items-center justify-between p-4 text-left"
      >
        <div>
          <h2 className="text-sm font-semibold text-slate-700 dark:text-slate-300">
            Channel Fields
          </h2>
          <p className="mt-0.5 text-xs text-slate-400 dark:text-slate-500">
            {channelLabel} &mdash; {data.total} fields ({data.required_count} required, {data.optional_count} optional)
            &mdash; {data.mapped_count} mapped, {data.total - data.mapped_count} unmapped
          </p>
        </div>
        {expanded ? (
          <ChevronUp className="h-4 w-4 text-slate-400" />
        ) : (
          <ChevronDown className="h-4 w-4 text-slate-400" />
        )}
      </button>

      {saveMsg && (
        <div className="mx-4 mb-2 rounded bg-emerald-50 px-3 py-1.5 text-xs text-emerald-700 dark:bg-emerald-900/20 dark:text-emerald-400">
          {saveMsg}
        </div>
      )}

      {expanded && (
        <div className="border-t border-slate-200 dark:border-slate-700">
          {/* Table header */}
          <div className="flex items-center border-b border-slate-200 bg-slate-50 text-[11px] font-semibold uppercase tracking-wider text-slate-500 dark:border-slate-700 dark:bg-slate-800/50 dark:text-slate-400">
            <div className="w-[200px] shrink-0 border-r border-slate-200 px-3 py-2 dark:border-slate-700">
              Channel Field
            </div>
            <div className="w-[120px] shrink-0 border-r border-slate-200 px-2 py-2 dark:border-slate-700">
              Canonical
            </div>
            <div className="w-[80px] shrink-0 border-r border-slate-200 px-2 py-2 text-center dark:border-slate-700">
              Status
            </div>
            <div className="min-w-0 flex-1 border-r border-slate-200 px-3 py-2 dark:border-slate-700">
              Mapping
            </div>
            <div className="w-[100px] shrink-0 px-2 py-2 text-center">Actions</div>
          </div>

          {/* Rows */}
          <div className="divide-y divide-slate-200 dark:divide-slate-700">
            {data.fields.map((field) => {
              const isEditing = editingField === field.canonical_key;
              const edit = overrideEdits[field.canonical_key];
              const isMapped = field.mapping !== null;
              const isOverride = field.mapping?.inherited_from === "channel_override";

              return (
                <div
                  key={`${field.canonical_key}-${field.channel_field_name}`}
                  className={`flex items-start bg-white dark:bg-slate-900 ${
                    field.is_required && !isMapped
                      ? "border-l-2 border-l-red-400"
                      : ""
                  }`}
                >
                  {/* Channel field name */}
                  <div className="flex w-[200px] shrink-0 flex-col gap-0.5 border-r border-slate-200 px-3 py-2.5 dark:border-slate-700">
                    <span className="text-sm font-medium text-slate-900 dark:text-slate-100">
                      {field.channel_field_name}
                    </span>
                    {field.is_required && (
                      <span className="inline-block w-fit rounded bg-red-100 px-1.5 py-0.5 text-[10px] font-semibold text-red-700 dark:bg-red-900/40 dark:text-red-400">
                        Required
                      </span>
                    )}
                    {field.source_description && (
                      <span className="text-[10px] text-slate-400 dark:text-slate-500 line-clamp-2">
                        {field.source_description}
                      </span>
                    )}
                  </div>

                  {/* Canonical key */}
                  <div className="w-[120px] shrink-0 border-r border-slate-200 px-2 py-2.5 dark:border-slate-700">
                    <span className="font-mono text-[11px] text-slate-500 dark:text-slate-400">
                      {field.canonical_key}
                    </span>
                  </div>

                  {/* Status */}
                  <div className="flex w-[80px] shrink-0 items-center justify-center border-r border-slate-200 px-2 py-2.5 dark:border-slate-700">
                    {isMapped ? (
                      <span className="rounded bg-emerald-100 px-1.5 py-0.5 text-[10px] font-medium text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400">
                        Mapped
                      </span>
                    ) : (
                      <span className={`rounded px-1.5 py-0.5 text-[10px] font-medium ${
                        field.is_required
                          ? "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400"
                          : "bg-slate-100 text-slate-500 dark:bg-slate-700 dark:text-slate-400"
                      }`}>
                        Unmapped
                      </span>
                    )}
                  </div>

                  {/* Mapping info / edit */}
                  <div className="min-w-0 flex-1 border-r border-slate-200 px-3 py-2.5 dark:border-slate-700">
                    {isEditing && edit ? (
                      <div className="space-y-2">
                        <select
                          value={edit.source_field ?? ""}
                          onChange={(e) =>
                            setOverrideEdits((prev) => ({
                              ...prev,
                              [field.canonical_key]: {
                                ...edit,
                                source_field: e.target.value || null,
                                mapping_type: "direct",
                              },
                            }))
                          }
                          className="wm-input w-full text-xs"
                        >
                          <option value="">-- Select source field --</option>
                          {sourceFields.map((sf) => (
                            <option key={sf.field} value={sf.field}>
                              {sf.field}
                            </option>
                          ))}
                        </select>
                        <div className="flex items-center gap-2">
                          <button
                            type="button"
                            onClick={() => void handleSaveOverride(field.canonical_key)}
                            disabled={saving}
                            className="inline-flex items-center gap-1 rounded bg-indigo-600 px-2 py-1 text-[11px] font-medium text-white hover:bg-indigo-700"
                          >
                            {saving ? <Loader2 className="h-3 w-3 animate-spin" /> : <Save className="h-3 w-3" />}
                            Save
                          </button>
                          <button
                            type="button"
                            onClick={handleCancelEdit}
                            className="rounded px-2 py-1 text-[11px] text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-800"
                          >
                            Cancel
                          </button>
                        </div>
                      </div>
                    ) : (
                      <>
                        {field.mapping ? (
                          <div className="text-xs text-slate-600 dark:text-slate-400">
                            <span className="font-medium">
                              {field.mapping.type === "direct" && field.mapping.source_field
                                ? field.mapping.source_field
                                : field.mapping.type === "static"
                                  ? `"${field.mapping.static_value}"`
                                  : field.mapping.type === "template"
                                    ? field.mapping.template_value
                                    : "—"}
                            </span>
                            <span className={`ml-1.5 text-[10px] ${
                              isOverride
                                ? "text-amber-600 dark:text-amber-400"
                                : "text-slate-400 dark:text-slate-500"
                            }`}>
                              ({isOverride ? "channel override" : "inherited"})
                            </span>
                          </div>
                        ) : (
                          <span className="text-xs text-slate-300 dark:text-slate-600">—</span>
                        )}
                      </>
                    )}
                  </div>

                  {/* Actions */}
                  <div className="flex w-[100px] shrink-0 items-center justify-center gap-1 px-2 py-2.5">
                    {!isEditing && (
                      <button
                        type="button"
                        onClick={() => handleStartOverride(field)}
                        className="rounded px-2 py-1 text-[11px] text-indigo-600 hover:bg-indigo-50 dark:text-indigo-400 dark:hover:bg-indigo-900/20"
                      >
                        Override
                      </button>
                    )}
                    {!isEditing && isOverride && (
                      <button
                        type="button"
                        onClick={() => void handleResetToMaster(field.canonical_key)}
                        disabled={saving}
                        className="inline-flex items-center gap-0.5 rounded px-1.5 py-1 text-[10px] text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-800"
                        title="Reset to Master"
                      >
                        <RotateCcw className="h-3 w-3" />
                      </button>
                    )}
                  </div>
                </div>
              );
            })}
          </div>

          {data.fields.length === 0 && (
            <div className="p-6 text-center text-sm text-slate-400">
              No schema fields found for this channel type. Import a schema first.
            </div>
          )}
        </div>
      )}
    </div>
  );
}
