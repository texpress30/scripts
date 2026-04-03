"use client";

import { useState } from "react";
import { ChevronDown } from "lucide-react";
import type { SourceField, ChannelBadge, FieldAlias } from "@/lib/hooks/useMasterFields";

type MappingType = "direct" | "static" | "template";

export type MasterFieldRowValue = {
  target_field: string;
  source_field: string | null;
  mapping_type: MappingType;
  static_value: string | null;
  template_value: string | null;
  is_required: boolean;
  sort_order: number;
};

type Props = {
  targetField: string;
  displayName: string;
  description: string;
  required: boolean;
  category: string;
  fieldType: string;
  suggestedSourceField: string | null;
  sourceFields: SourceField[];
  channels?: ChannelBadge[];
  aliases?: FieldAlias[];
  aliasesCount?: number;
  channelsCount?: number;
  value: MasterFieldRowValue;
  onChange: (value: MasterFieldRowValue) => void;
};

const CHANNEL_BADGE_COLORS: Record<string, string> = {
  google_vehicle_ads_v3: "bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-400",
  google_vehicle_listings: "bg-blue-50 text-blue-600 dark:bg-blue-900/30 dark:text-blue-300",
  google_shopping: "bg-sky-100 text-sky-700 dark:bg-sky-900/40 dark:text-sky-400",
  facebook_product_ads: "bg-indigo-100 text-indigo-700 dark:bg-indigo-900/40 dark:text-indigo-400",
};

const CHANNEL_SHORT_NAMES: Record<string, string> = {
  google_vehicle_ads_v3: "Google Ads",
  google_vehicle_listings: "Google Listings",
  google_shopping: "Google Shopping",
  facebook_product_ads: "Facebook",
  tiktok_auto_inventory: "TikTok",
};

function formatChannelShort(slug: string): string {
  return CHANNEL_SHORT_NAMES[slug] ?? slug.replace(/_/g, " ").replace(/\bv\d+$/i, "").trim().replace(/\b\w/g, (c) => c.toUpperCase());
}

export function MasterFieldRow({
  targetField,
  displayName,
  required,
  suggestedSourceField,
  sourceFields,
  channels,
  aliases,
  aliasesCount,
  channelsCount,
  value,
  onChange,
}: Props) {
  const [showAdvanced, setShowAdvanced] = useState(value.mapping_type !== "direct");

  const currentSourceField = value.source_field ?? "";
  const isSuggested = !value.source_field && !!suggestedSourceField;

  function handleSourceChange(e: React.ChangeEvent<HTMLSelectElement>) {
    const sf = e.target.value || null;
    onChange({ ...value, source_field: sf, mapping_type: "direct", static_value: null, template_value: null });
  }

  function handleMappingTypeChange(mt: MappingType) {
    setShowAdvanced(mt !== "direct");
    onChange({ ...value, mapping_type: mt, source_field: mt === "direct" ? value.source_field : null });
  }

  return (
    <div className="flex items-center bg-white dark:bg-slate-900">
      {/* Col 1: Target field name + badges */}
      <div className="flex w-[280px] shrink-0 flex-col gap-1 border-r border-slate-200 px-3 py-2.5 dark:border-slate-700">
        <div className="flex items-center gap-2">
          <span className={`h-2 w-2 shrink-0 rounded-full ${required ? "bg-indigo-500" : "bg-slate-300 dark:bg-slate-600"}`} />
          <div className="min-w-0">
            <span className="block truncate text-sm font-medium text-slate-900 dark:text-slate-100">
              {displayName}
            </span>
            <span className="font-mono text-[10px] text-slate-400">{targetField}</span>
          </div>
          {required && (
            <span className="ml-auto shrink-0 rounded bg-red-100 px-1.5 py-0.5 text-[10px] font-semibold text-red-700 dark:bg-red-900/40 dark:text-red-400">
              Required
            </span>
          )}
        </div>
        {/* Alias info */}
        {aliases && aliases.length > 0 && (
          <div className="pl-4 text-[10px] text-slate-400 dark:text-slate-500">
            <span className="text-slate-500 dark:text-slate-400">&rarr;</span>{" "}
            {aliases.map((a, i) => (
              <span key={a.alias_key}>
                {a.alias_key}
                {a.platform_hint ? ` (${a.platform_hint})` : ""}
                {i < aliases.length - 1 ? ", " : ""}
              </span>
            ))}
          </div>
        )}
        {/* Channel count badge */}
        {(channelsCount ?? 0) > 0 && (
          <div className="pl-4">
            <span className="inline-block rounded bg-slate-100 px-1.5 py-0.5 text-[9px] font-medium text-slate-500 dark:bg-slate-700 dark:text-slate-400">
              Used by {channelsCount} channel{channelsCount !== 1 ? "s" : ""}
            </span>
          </div>
        )}
        {/* Channel badges */}
        {channels && channels.length > 0 && !(aliases && aliases.length > 0) && (
          <div className="flex flex-wrap gap-1 pl-4">
            {channels.map((ch) => (
              <span
                key={ch.channel_slug}
                className={`inline-block rounded px-1.5 py-0.5 text-[9px] font-medium ${
                  CHANNEL_BADGE_COLORS[ch.channel_slug] ?? "bg-slate-100 text-slate-500 dark:bg-slate-700 dark:text-slate-400"
                } ${ch.is_required ? "font-semibold" : "opacity-70"}`}
                title={`${ch.channel_slug} — ${ch.is_required ? "obligatoriu" : "optional"}`}
              >
                {formatChannelShort(ch.channel_slug)}
              </span>
            ))}
          </div>
        )}
      </div>

      {/* Col 2: Mapping type toggle */}
      <div className="flex w-[140px] shrink-0 items-center justify-center gap-1 border-r border-slate-200 px-2 py-2.5 dark:border-slate-700">
        {(["direct", "static", "template"] as MappingType[]).map((mt) => (
          <button
            key={mt}
            type="button"
            onClick={() => handleMappingTypeChange(mt)}
            className={`rounded px-2 py-1 text-[11px] font-medium transition ${
              value.mapping_type === mt
                ? "bg-indigo-100 text-indigo-700 dark:bg-indigo-900/40 dark:text-indigo-400"
                : "text-slate-400 hover:bg-slate-100 hover:text-slate-600 dark:hover:bg-slate-800 dark:hover:text-slate-300"
            }`}
          >
            {mt === "direct" ? "Field" : mt === "static" ? "Static" : "Template"}
          </button>
        ))}
      </div>

      {/* Col 3: Source field / value input */}
      <div className="flex min-w-0 flex-1 items-center px-3 py-2.5">
        {value.mapping_type === "direct" && (
          <div className="relative w-full">
            <select
              value={currentSourceField || (isSuggested ? suggestedSourceField ?? "" : "")}
              onChange={handleSourceChange}
              className={`wm-input appearance-none pr-8 ${
                isSuggested ? "border-emerald-300 text-emerald-700 dark:border-emerald-700 dark:text-emerald-400" : ""
              }`}
            >
              <option value="">-- Select source field --</option>
              {sourceFields.map((sf) => (
                <option key={sf.field} value={sf.field}>
                  {sf.field} {sf.sample ? `(${sf.sample.slice(0, 40)})` : ""}
                </option>
              ))}
            </select>
            <ChevronDown className="pointer-events-none absolute right-2 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
            {isSuggested && (
              <span className="absolute -top-2 right-8 rounded bg-emerald-100 px-1.5 py-0.5 text-[9px] font-medium text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-400">
                Suggested
              </span>
            )}
          </div>
        )}

        {value.mapping_type === "static" && (
          <input
            type="text"
            value={value.static_value ?? ""}
            onChange={(e) => onChange({ ...value, static_value: e.target.value })}
            placeholder="Enter static value..."
            className="wm-input w-full"
          />
        )}

        {value.mapping_type === "template" && (
          <input
            type="text"
            value={value.template_value ?? ""}
            onChange={(e) => onChange({ ...value, template_value: e.target.value })}
            placeholder="e.g. {{make}} {{model}} {{year}}"
            className="wm-input w-full font-mono text-xs"
          />
        )}
      </div>
    </div>
  );
}
