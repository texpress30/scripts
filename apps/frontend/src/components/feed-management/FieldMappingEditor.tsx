"use client";

import { useState } from "react";
import type { CatalogField, FieldMappingRule, TransformationType } from "@/lib/types/feed-management";
import { CatalogFieldsList } from "./CatalogFieldsList";
import { MappingRuleConfig } from "./MappingRuleConfig";
import { cn } from "@/lib/utils";
import { ArrowRight, Plus } from "lucide-react";

export function FieldMappingEditor({
  catalogFields,
  sourceFields,
  rules,
  onSaveRule,
  isUpdating,
}: {
  catalogFields: CatalogField[];
  sourceFields: string[];
  rules: FieldMappingRule[];
  onSaveRule: (rule: { target_field: string; source_field: string | null; transformation: TransformationType; config: Record<string, string> }) => void;
  isUpdating: boolean;
}) {
  const [selectedTargetField, setSelectedTargetField] = useState<string | null>(null);

  const selectedCatalogField = selectedTargetField
    ? catalogFields.find((f) => f.key === selectedTargetField) ?? null
    : null;

  const existingRule = selectedTargetField
    ? rules.find((r) => r.target_field === selectedTargetField)
    : undefined;

  function handleSaveRule(ruleConfig: { source_field: string | null; transformation: TransformationType; config: Record<string, string> }) {
    if (!selectedTargetField) return;
    onSaveRule({ target_field: selectedTargetField, ...ruleConfig });
    setSelectedTargetField(null);
  }

  return (
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
      {/* LEFT: Source Fields */}
      <div className="wm-card p-4">
        <h3 className="mb-3 text-sm font-semibold text-slate-900 dark:text-slate-100">Source Fields</h3>
        <div className="max-h-[500px] space-y-1 overflow-y-auto pr-1">
          {sourceFields.map((field) => {
            const usedInRule = rules.find((r) => r.source_field === field);
            return (
              <div
                key={field}
                className={cn(
                  "flex items-center justify-between rounded-lg px-3 py-2 text-sm",
                  usedInRule
                    ? "bg-emerald-50 dark:bg-emerald-950/20"
                    : "bg-white dark:bg-slate-900",
                )}
              >
                <span className="font-mono text-xs text-slate-700 dark:text-slate-300">{field}</span>
                {usedInRule && (
                  <span className="flex items-center gap-1 text-[10px] text-emerald-600 dark:text-emerald-400">
                    <ArrowRight className="h-3 w-3" />
                    {usedInRule.target_field}
                  </span>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* RIGHT: Target Fields + Config */}
      <div className="space-y-4">
        <div className="wm-card p-4">
          <div className="mb-3 flex items-center justify-between">
            <h3 className="text-sm font-semibold text-slate-900 dark:text-slate-100">Target Fields</h3>
            <span className="text-xs text-slate-400">
              {rules.length}/{catalogFields.length} mapped
            </span>
          </div>
          <div className="max-h-[400px] overflow-y-auto pr-1">
            <CatalogFieldsList
              fields={catalogFields}
              rules={rules}
              selectedField={selectedTargetField}
              onSelectField={setSelectedTargetField}
            />
          </div>
        </div>

        {/* Rule Configuration Panel */}
        {selectedCatalogField && (
          <MappingRuleConfig
            targetField={selectedCatalogField}
            sourceFields={sourceFields}
            initialRule={existingRule ? {
              source_field: existingRule.source_field,
              transformation: existingRule.transformation,
              config: existingRule.config,
            } : undefined}
            onSave={handleSaveRule}
            onClose={() => setSelectedTargetField(null)}
            busy={isUpdating}
          />
        )}

        {!selectedCatalogField && (
          <div className="rounded-xl border-2 border-dashed border-slate-200 p-6 text-center dark:border-slate-700">
            <Plus className="mx-auto mb-2 h-6 w-6 text-slate-300 dark:text-slate-600" />
            <p className="text-sm text-slate-400 dark:text-slate-500">
              Click a target field above to configure its mapping rule
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
