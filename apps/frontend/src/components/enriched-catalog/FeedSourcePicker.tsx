"use client";

import { useFeedManagement } from "@/lib/contexts/FeedManagementContext";
import { useFeedSources } from "@/lib/hooks/useFeedSources";

interface FeedSourcePickerProps {
  value: string;
  onChange: (sourceId: string) => void;
}

export function FeedSourcePicker({ value, onChange }: FeedSourcePickerProps) {
  const { selectedId } = useFeedManagement();
  const { sources, isLoading } = useFeedSources(selectedId);

  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className="mcc-input w-full rounded-md border px-3 py-2 text-sm"
      disabled={isLoading}
    >
      <option value="">
        {isLoading ? "Loading sources..." : "Select a feed source..."}
      </option>
      {sources.map((src) => (
        <option key={src.id} value={src.id}>
          {src.name} ({src.source_type}) — {src.product_count} products
        </option>
      ))}
    </select>
  );
}
