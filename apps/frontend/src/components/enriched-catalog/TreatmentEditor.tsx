"use client";

import { useState } from "react";
import { Plus, Loader2 } from "lucide-react";
import { TreatmentFilterRow } from "./TreatmentFilterRow";
import type { TreatmentFilter, CreateTreatmentPayload } from "@/lib/hooks/useTreatments";
import type { CreativeTemplate } from "@/lib/hooks/useCreativeTemplates";

interface TreatmentEditorProps {
  outputFeedId: string;
  templates: CreativeTemplate[];
  onSave: (payload: CreateTreatmentPayload) => Promise<void>;
  onCancel: () => void;
  isSaving: boolean;
  initial?: {
    name: string;
    template_id: string;
    filters: TreatmentFilter[];
    is_default: boolean;
  };
}

export function TreatmentEditor({ outputFeedId, templates, onSave, onCancel, isSaving, initial }: TreatmentEditorProps) {
  const [name, setName] = useState(initial?.name || "");
  const [templateId, setTemplateId] = useState(initial?.template_id || "");
  const [filters, setFilters] = useState<TreatmentFilter[]>(initial?.filters || []);
  const [isDefault, setIsDefault] = useState(initial?.is_default || false);

  const handleSubmit = async () => {
    if (!name.trim() || !templateId) return;
    await onSave({
      name: name.trim(),
      template_id: templateId,
      output_feed_id: outputFeedId,
      filters,
      is_default: isDefault,
    });
  };

  const addFilter = () => {
    setFilters([...filters, { field_name: "", operator: "equals", value: "" }]);
  };

  const updateFilter = (index: number, updated: TreatmentFilter) => {
    const next = [...filters];
    next[index] = updated;
    setFilters(next);
  };

  const removeFilter = (index: number) => {
    setFilters(filters.filter((_, i) => i !== index));
  };

  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4 dark:border-slate-700 dark:bg-slate-800">
      <h4 className="mb-4 text-sm font-semibold text-slate-900 dark:text-slate-100">
        {initial ? "Edit Treatment" : "New Treatment"}
      </h4>

      <div className="space-y-4">
        {/* Name */}
        <div>
          <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">Name</label>
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="e.g. Blue Theme, Category: Shoes"
            className="mcc-input w-full rounded-md border px-3 py-2 text-sm"
          />
        </div>

        {/* Template */}
        <div>
          <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">Template</label>
          <select
            value={templateId}
            onChange={(e) => setTemplateId(e.target.value)}
            className="mcc-input w-full rounded-md border px-3 py-2 text-sm"
          >
            <option value="">Select a template...</option>
            {templates.map((t) => (
              <option key={t.id} value={t.id}>
                {t.name} ({t.canvas_width}x{t.canvas_height})
              </option>
            ))}
          </select>
        </div>

        {/* Default */}
        <label className="flex items-center gap-2 text-sm text-slate-700 dark:text-slate-300">
          <input
            type="checkbox"
            checked={isDefault}
            onChange={(e) => setIsDefault(e.target.checked)}
            className="accent-indigo-600"
          />
          Default treatment (applies when no filter matches)
        </label>

        {/* Filters */}
        <div>
          <div className="mb-2 flex items-center justify-between">
            <label className="text-sm font-medium text-slate-700 dark:text-slate-300">
              Filters {filters.length > 0 && `(${filters.length})`}
            </label>
            <button
              onClick={addFilter}
              className="flex items-center gap-1 text-xs text-indigo-600 hover:text-indigo-700 dark:text-indigo-400"
            >
              <Plus className="h-3 w-3" /> Add Filter
            </button>
          </div>
          {filters.length === 0 ? (
            <p className="text-xs text-slate-400 dark:text-slate-500">
              No filters — this treatment will match all products (if default) or none.
            </p>
          ) : (
            <div className="space-y-2">
              {filters.map((f, idx) => (
                <TreatmentFilterRow
                  key={idx}
                  filter={f}
                  onChange={(updated) => updateFilter(idx, updated)}
                  onRemove={() => removeFilter(idx)}
                />
              ))}
            </div>
          )}
        </div>
      </div>

      <div className="mt-6 flex justify-end gap-3">
        <button
          onClick={onCancel}
          className="rounded-md px-4 py-2 text-sm text-slate-600 hover:bg-slate-100 dark:text-slate-400 dark:hover:bg-slate-700"
        >
          Cancel
        </button>
        <button
          onClick={handleSubmit}
          disabled={!name.trim() || !templateId || isSaving}
          className="wm-btn-primary inline-flex items-center gap-2 rounded-md px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
        >
          {isSaving && <Loader2 className="h-4 w-4 animate-spin" />}
          {initial ? "Update" : "Create"}
        </button>
      </div>
    </div>
  );
}
