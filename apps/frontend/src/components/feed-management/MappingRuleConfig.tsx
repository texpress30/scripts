"use client";

import { useState, useEffect, useCallback } from "react";
import type { TransformationType, CatalogField } from "@/lib/types/feed-management";
import { X } from "lucide-react";

const TRANSFORMATIONS: { value: TransformationType; label: string; description: string }[] = [
  { value: "direct", label: "Direct", description: "Map source field value directly" },
  { value: "static", label: "Static Value", description: "Use a fixed static value" },
  { value: "template", label: "Template", description: "Build value using {{field}} syntax" },
  { value: "conditional", label: "Conditional", description: "If/else logic based on source value" },
  { value: "truncate", label: "Truncate", description: "Limit text to max length" },
  { value: "replace", label: "Replace", description: "Search and replace in text" },
  { value: "concatenate", label: "Concatenate", description: "Join multiple fields together" },
  { value: "lowercase", label: "Lowercase", description: "Convert to lowercase" },
  { value: "uppercase", label: "Uppercase", description: "Convert to uppercase" },
];

type RuleConfig = {
  source_field: string | null;
  transformation: TransformationType;
  config: Record<string, string>;
};

export function MappingRuleConfig({
  targetField,
  sourceFields,
  initialRule,
  onSave,
  onClose,
  busy,
}: {
  targetField: CatalogField;
  sourceFields: string[];
  initialRule?: RuleConfig;
  onSave: (rule: RuleConfig) => void;
  onClose: () => void;
  busy?: boolean;
}) {
  const [sourceField, setSourceField] = useState(initialRule?.source_field ?? "");
  const [transformation, setTransformation] = useState<TransformationType>(initialRule?.transformation ?? "direct");
  const [config, setConfig] = useState<Record<string, string>>(initialRule?.config ?? {});

  const computePreview = useCallback(() => {
    const sampleValue = sourceField ? `<${sourceField}>` : "";
    switch (transformation) {
      case "direct":
        return sampleValue;
      case "static":
        return config.value ?? "";
      case "template":
        return config.template?.replace(/\{\{(\w+)\}\}/g, (_, k: string) => `<${k}>`) ?? "";
      case "conditional":
        return `if (${config.condition ?? "..."}) → "${config.if_true ?? ""}" else → "${config.if_false ?? ""}"`;
      case "truncate":
        return sampleValue ? `${sampleValue.slice(0, Number(config.max_length ?? 100))}...` : "";
      case "replace":
        return sampleValue ? sampleValue.replace(config.search ?? "", config.replace_with ?? "") : "";
      case "lowercase":
        return sampleValue.toLowerCase();
      case "uppercase":
        return sampleValue.toUpperCase();
      case "concatenate":
        return config.fields?.split(",").map((f) => `<${f.trim()}>`).join(config.separator ?? " ") ?? "";
      default:
        return sampleValue;
    }
  }, [sourceField, transformation, config]);

  const [preview, setPreview] = useState("");

  useEffect(() => {
    const timer = setTimeout(() => setPreview(computePreview()), 300);
    return () => clearTimeout(timer);
  }, [computePreview]);

  function handleSetConfig(key: string, value: string) {
    setConfig((prev) => ({ ...prev, [key]: value }));
  }

  function handleSave() {
    onSave({
      source_field: transformation === "static" ? null : sourceField || null,
      transformation,
      config,
    });
  }

  return (
    <div className="wm-card border-indigo-200 p-5 dark:border-indigo-800">
      <div className="mb-4 flex items-start justify-between">
        <div>
          <h3 className="text-sm font-semibold text-slate-900 dark:text-slate-100">
            Configure: {targetField.label}
          </h3>
          <p className="mt-0.5 text-xs text-slate-500 dark:text-slate-400">{targetField.description}</p>
          <div className="mt-1 flex items-center gap-2">
            {targetField.required && (
              <span className="rounded bg-red-100 px-1.5 py-0.5 text-[10px] font-semibold text-red-700 dark:bg-red-900/40 dark:text-red-400">Required</span>
            )}
            <span className="text-[10px] text-slate-400">Type: {targetField.type}</span>
          </div>
        </div>
        <button type="button" onClick={onClose} className="rounded p-1 text-slate-400 hover:text-slate-600 dark:hover:text-slate-300">
          <X className="h-4 w-4" />
        </button>
      </div>

      <div className="space-y-4">
        {/* Source Field */}
        {transformation !== "static" && (
          <div>
            <label className="mb-1 block text-xs font-medium text-slate-600 dark:text-slate-400">Source Field</label>
            <select
              value={sourceField}
              onChange={(e) => setSourceField(e.target.value)}
              className="wm-input w-full"
            >
              <option value="">-- Select source field --</option>
              {sourceFields.map((f) => (
                <option key={f} value={f}>{f}</option>
              ))}
            </select>
          </div>
        )}

        {/* Transformation Type */}
        <div>
          <label className="mb-1 block text-xs font-medium text-slate-600 dark:text-slate-400">Transformation</label>
          <select
            value={transformation}
            onChange={(e) => {
              setTransformation(e.target.value as TransformationType);
              setConfig({});
            }}
            className="wm-input w-full"
          >
            {TRANSFORMATIONS.map((t) => (
              <option key={t.value} value={t.value}>{t.label} — {t.description}</option>
            ))}
          </select>
        </div>

        {/* Transformation-specific config */}
        {transformation === "static" && (
          <div>
            <label className="mb-1 block text-xs font-medium text-slate-600 dark:text-slate-400">Static Value</label>
            <input type="text" value={config.value ?? ""} onChange={(e) => handleSetConfig("value", e.target.value)} className="wm-input w-full" placeholder="Enter fixed value..." />
          </div>
        )}

        {transformation === "template" && (
          <div>
            <label className="mb-1 block text-xs font-medium text-slate-600 dark:text-slate-400">Template</label>
            <textarea
              value={config.template ?? ""}
              onChange={(e) => handleSetConfig("template", e.target.value)}
              className="wm-input w-full font-mono text-xs"
              rows={3}
              placeholder="e.g. https://store.com/products/{{handle}}"
            />
            <p className="mt-1 text-[10px] text-slate-400">{"Use {{field_name}} to reference source fields"}</p>
          </div>
        )}

        {transformation === "conditional" && (
          <div className="space-y-2">
            <div>
              <label className="mb-1 block text-xs font-medium text-slate-600 dark:text-slate-400">Condition</label>
              <input type="text" value={config.condition ?? ""} onChange={(e) => handleSetConfig("condition", e.target.value)} className="wm-input w-full font-mono text-xs" placeholder='e.g. value > 0' />
            </div>
            <div className="grid grid-cols-2 gap-2">
              <div>
                <label className="mb-1 block text-xs font-medium text-slate-600 dark:text-slate-400">If True</label>
                <input type="text" value={config.if_true ?? ""} onChange={(e) => handleSetConfig("if_true", e.target.value)} className="wm-input w-full" placeholder="in_stock" />
              </div>
              <div>
                <label className="mb-1 block text-xs font-medium text-slate-600 dark:text-slate-400">If False</label>
                <input type="text" value={config.if_false ?? ""} onChange={(e) => handleSetConfig("if_false", e.target.value)} className="wm-input w-full" placeholder="out_of_stock" />
              </div>
            </div>
          </div>
        )}

        {transformation === "truncate" && (
          <div>
            <label className="mb-1 block text-xs font-medium text-slate-600 dark:text-slate-400">Max Length</label>
            <input type="number" value={config.max_length ?? "150"} onChange={(e) => handleSetConfig("max_length", e.target.value)} className="wm-input w-32" min={1} />
          </div>
        )}

        {transformation === "replace" && (
          <div className="grid grid-cols-2 gap-2">
            <div>
              <label className="mb-1 block text-xs font-medium text-slate-600 dark:text-slate-400">Search</label>
              <input type="text" value={config.search ?? ""} onChange={(e) => handleSetConfig("search", e.target.value)} className="wm-input w-full" placeholder="text to find" />
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-slate-600 dark:text-slate-400">Replace With</label>
              <input type="text" value={config.replace_with ?? ""} onChange={(e) => handleSetConfig("replace_with", e.target.value)} className="wm-input w-full" placeholder="replacement" />
            </div>
          </div>
        )}

        {transformation === "concatenate" && (
          <div className="space-y-2">
            <div>
              <label className="mb-1 block text-xs font-medium text-slate-600 dark:text-slate-400">Fields (comma-separated)</label>
              <input type="text" value={config.fields ?? ""} onChange={(e) => handleSetConfig("fields", e.target.value)} className="wm-input w-full font-mono text-xs" placeholder="field1, field2, field3" />
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-slate-600 dark:text-slate-400">Separator</label>
              <input type="text" value={config.separator ?? " "} onChange={(e) => handleSetConfig("separator", e.target.value)} className="wm-input w-24" placeholder=" " />
            </div>
          </div>
        )}

        {/* Live Preview */}
        <div className="rounded-lg border border-slate-200 bg-slate-50 p-3 dark:border-slate-700 dark:bg-slate-800/50">
          <p className="mb-1 text-[10px] font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">Preview</p>
          <p className="font-mono text-xs text-slate-700 dark:text-slate-300">
            {preview || <span className="italic text-slate-400">No preview available</span>}
          </p>
        </div>

        {/* Actions */}
        <div className="flex justify-end gap-2 pt-2">
          <button type="button" onClick={onClose} className="wm-btn-secondary text-sm">Cancel</button>
          <button type="button" onClick={handleSave} disabled={busy} className="wm-btn-primary text-sm">
            {busy ? "Saving..." : "Save Rule"}
          </button>
        </div>
      </div>
    </div>
  );
}
