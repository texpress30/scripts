import React from "react";
import { useMemo, useState } from "react";

import { deriveAccountSyncStatus } from "@/lib/accountSyncStatus";

type AccountSyncStatusProps = {
  platform: string;
  account: Record<string, unknown>;
};

const BADGE_STYLES: Record<string, string> = {
  healthy: "bg-emerald-50 text-emerald-700 border-emerald-200",
  warning: "bg-amber-50 text-amber-700 border-amber-200",
  error: "bg-rose-50 text-rose-700 border-rose-200",
  unknown: "bg-slate-100 text-slate-600 border-slate-200",
};

function renderIfPresent(label: string, value: string | number | boolean | undefined) {
  if (value === undefined || value === null || value === "") return null;
  return (
    <div className="flex items-center justify-between gap-2">
      <span className="text-slate-500">{label}</span>
      <span className="font-medium text-slate-700">{String(value)}</span>
    </div>
  );
}

export function AccountSyncStatus({ platform, account }: AccountSyncStatusProps) {
  const [expanded, setExpanded] = useState(false);
  const ui = useMemo(() => deriveAccountSyncStatus(platform, account), [platform, account]);

  return (
    <div className="mt-2 rounded-md border border-slate-200 bg-slate-50 px-2 py-2 text-xs">
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <span className={`inline-flex items-center rounded-full border px-2 py-0.5 font-medium ${BADGE_STYLES[ui.uiStatus]}`}>{ui.uiLabel}</span>
          {ui.shortReason ? <span className="text-slate-600 line-clamp-1 max-w-[190px]">{ui.shortReason}</span> : null}
        </div>
        <button type="button" className="text-slate-500 hover:text-slate-700" onClick={() => setExpanded((s) => !s)}>
          {expanded ? "Hide" : "Details"}
        </button>
      </div>
      {expanded ? (
        <div className="mt-2 space-y-1">
          {renderIfPresent("Coverage", ui.details.coverageStatus ?? ui.details.syncHealthStatus)}
          {renderIfPresent("Last sync", ui.details.lastSyncAt)}
          {renderIfPresent("Requested", ui.details.requestedStartDate && ui.details.requestedEndDate ? `${ui.details.requestedStartDate} → ${ui.details.requestedEndDate}` : undefined)}
          {renderIfPresent("Chunks", ui.details.totalChunkCount !== undefined ? `${ui.details.successfulChunkCount ?? 0}/${ui.details.totalChunkCount} ok, ${ui.details.failedChunkCount ?? 0} failed` : undefined)}
          {renderIfPresent("Retry", ui.details.retryAttempted !== undefined ? `${ui.details.retryAttempted ? "yes" : "no"}${ui.details.retryRecoveredChunkCount !== undefined ? ` (recovered: ${ui.details.retryRecoveredChunkCount})` : ""}` : undefined)}
          {renderIfPresent("Rows written", ui.details.rowsWrittenCount)}
          {renderIfPresent("Persisted range", ui.details.firstPersistedDate && ui.details.lastPersistedDate ? `${ui.details.firstPersistedDate} → ${ui.details.lastPersistedDate}` : undefined)}
          {renderIfPresent("Error", ui.details.lastErrorSummary ?? ui.details.lastError)}
        </div>
      ) : null}
    </div>
  );
}
