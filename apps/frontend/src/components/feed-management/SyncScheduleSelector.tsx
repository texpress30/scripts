"use client";

import { useState } from "react";
import { Calendar, Loader2 } from "lucide-react";
import type { SyncSchedule } from "@/lib/types/feed-management";

const SCHEDULE_OPTIONS: { value: SyncSchedule; label: string; description: string }[] = [
  { value: "manual", label: "Manual only", description: "Sync doar la cerere" },
  { value: "hourly", label: "Every hour", description: "La fiecare oră" },
  { value: "every_6h", label: "Every 6 hours", description: "De 4 ori pe zi" },
  { value: "every_12h", label: "Every 12 hours", description: "De 2 ori pe zi" },
  { value: "daily", label: "Daily", description: "O dată pe zi" },
  { value: "weekly", label: "Weekly", description: "O dată pe săptămână" },
];

function formatTimeUntil(date: string | null | undefined): string {
  if (!date) return "";
  const diff = new Date(date).getTime() - Date.now();
  if (diff <= 0) return "due now";
  const minutes = Math.floor(diff / (1000 * 60));
  const hours = Math.floor(minutes / 60);
  const days = Math.floor(hours / 24);
  if (days > 0) return `in ${days}d ${hours % 24}h`;
  if (hours > 0) return `in ${hours}h ${minutes % 60}m`;
  return `in ${minutes}m`;
}

export function SyncScheduleSelector({
  currentSchedule,
  nextSync,
  onScheduleChange,
  isSaving,
}: {
  currentSchedule: SyncSchedule;
  nextSync?: string | null;
  onScheduleChange: (schedule: SyncSchedule) => void;
  isSaving?: boolean;
}) {
  return (
    <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
      <div className="flex items-center gap-2 text-sm text-slate-600 dark:text-slate-400">
        <Calendar className="h-4 w-4" />
        <span className="font-medium">Sync Schedule:</span>
      </div>
      <div className="flex items-center gap-3">
        <select
          value={currentSchedule}
          onChange={(e) => onScheduleChange(e.target.value as SyncSchedule)}
          disabled={isSaving}
          className="wm-input max-w-xs text-sm"
        >
          {SCHEDULE_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>{opt.label}</option>
          ))}
        </select>
        {isSaving && <Loader2 className="h-4 w-4 animate-spin text-slate-400" />}
        {!isSaving && currentSchedule !== "manual" && nextSync && (
          <span className="text-xs text-slate-500 dark:text-slate-400" title={new Date(nextSync).toLocaleString()}>
            Next sync {formatTimeUntil(nextSync)}
          </span>
        )}
      </div>
    </div>
  );
}
