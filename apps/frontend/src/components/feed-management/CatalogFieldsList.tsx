"use client";

import type { CatalogField, FieldMappingRule } from "@/lib/types/feed-management";
import { cn } from "@/lib/utils";
import { CheckCircle2, AlertTriangle } from "lucide-react";

const TYPE_BADGES: Record<string, { label: string; color: string }> = {
  string: { label: "String", color: "bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-400" },
  number: { label: "Number", color: "bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-400" },
  boolean: { label: "Bool", color: "bg-purple-100 text-purple-700 dark:bg-purple-900/40 dark:text-purple-400" },
  url: { label: "URL", color: "bg-sky-100 text-sky-700 dark:bg-sky-900/40 dark:text-sky-400" },
  currency: { label: "Currency", color: "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-400" },
  date: { label: "Date", color: "bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-400" },
  enum: { label: "Enum", color: "bg-orange-100 text-orange-700 dark:bg-orange-900/40 dark:text-orange-400" },
  array: { label: "Array", color: "bg-rose-100 text-rose-700 dark:bg-rose-900/40 dark:text-rose-400" },
};

export function CatalogFieldsList({
  fields,
  rules,
  selectedField,
  onSelectField,
}: {
  fields: CatalogField[];
  rules: FieldMappingRule[];
  selectedField: string | null;
  onSelectField: (fieldKey: string) => void;
}) {
  const mappedFields = new Set(rules.map((r) => r.target_field));
  const requiredFields = fields.filter((f) => f.required);
  const optionalFields = fields.filter((f) => !f.required);

  return (
    <div className="space-y-4">
      <FieldGroup
        title="Required Fields"
        fields={requiredFields}
        mappedFields={mappedFields}
        selectedField={selectedField}
        onSelectField={onSelectField}
        showWarning
      />
      <FieldGroup
        title="Optional Fields"
        fields={optionalFields}
        mappedFields={mappedFields}
        selectedField={selectedField}
        onSelectField={onSelectField}
        showWarning={false}
      />
    </div>
  );
}

function FieldGroup({
  title,
  fields,
  mappedFields,
  selectedField,
  onSelectField,
  showWarning,
}: {
  title: string;
  fields: CatalogField[];
  mappedFields: Set<string>;
  selectedField: string | null;
  onSelectField: (fieldKey: string) => void;
  showWarning: boolean;
}) {
  if (fields.length === 0) return null;

  const unmappedRequired = showWarning ? fields.filter((f) => !mappedFields.has(f.key)).length : 0;

  return (
    <div>
      <div className="mb-2 flex items-center gap-2">
        <h4 className="text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">{title}</h4>
        {showWarning && unmappedRequired > 0 && (
          <span className="rounded-full bg-red-100 px-2 py-0.5 text-[10px] font-semibold text-red-700 dark:bg-red-900/40 dark:text-red-400">
            {unmappedRequired} unmapped
          </span>
        )}
      </div>
      <div className="space-y-1">
        {fields.map((field) => {
          const isMapped = mappedFields.has(field.key);
          const isSelected = selectedField === field.key;
          const badge = TYPE_BADGES[field.type] ?? TYPE_BADGES.string;

          return (
            <button
              key={field.key}
              type="button"
              onClick={() => onSelectField(field.key)}
              title={field.description}
              className={cn(
                "flex w-full items-center gap-2 rounded-lg border px-3 py-2 text-left text-sm transition",
                isSelected
                  ? "border-indigo-500 bg-indigo-50 dark:border-indigo-400 dark:bg-indigo-950/30"
                  : "border-transparent hover:bg-slate-50 dark:hover:bg-slate-800/50",
                !isMapped && field.required && !isSelected && "border-red-200 bg-red-50/50 dark:border-red-900/40 dark:bg-red-950/20",
              )}
            >
              {isMapped ? (
                <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-500" />
              ) : field.required ? (
                <AlertTriangle className="h-4 w-4 shrink-0 text-red-500" />
              ) : (
                <div className="h-4 w-4 shrink-0 rounded-full border-2 border-slate-300 dark:border-slate-600" />
              )}
              <span className={cn("flex-1 truncate", isSelected ? "font-medium text-slate-900 dark:text-slate-100" : "text-slate-700 dark:text-slate-300")}>
                {field.label}
              </span>
              <span className={cn("rounded px-1.5 py-0.5 text-[10px] font-medium", badge.color)}>
                {badge.label}
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
