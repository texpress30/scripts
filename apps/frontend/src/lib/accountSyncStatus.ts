export type UiSyncStatus = "healthy" | "warning" | "error" | "unknown";

export type SyncStatusDetails = {
  coverageStatus?: string;
  syncHealthStatus?: string;
  lastSyncAt?: string;
  requestedStartDate?: string;
  requestedEndDate?: string;
  totalChunkCount?: number;
  successfulChunkCount?: number;
  failedChunkCount?: number;
  retryAttempted?: boolean;
  retryRecoveredChunkCount?: number;
  rowsWrittenCount?: number;
  firstPersistedDate?: string;
  lastPersistedDate?: string;
  lastErrorSummary?: string;
  lastError?: string;
};

export type SyncStatusUi = {
  uiStatus: UiSyncStatus;
  uiLabel: string;
  shortReason?: string;
  details: SyncStatusDetails;
};

export type PlatformSyncSummaryUi = {
  uiStatus: UiSyncStatus;
  uiLabel: string;
  affectedAccountCount: number;
  warningCount: number;
  errorCount: number;
  accounts: Array<{ id: string; name: string; ui: SyncStatusUi }>;
};

function toNumberOrUndefined(value: unknown): number | undefined {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string" && value.trim() !== "") {
    const parsed = Number(value);
    if (Number.isFinite(parsed)) return parsed;
  }
  return undefined;
}

function toStringOrUndefined(value: unknown): string | undefined {
  if (typeof value !== "string") return undefined;
  const normalized = value.trim();
  return normalized === "" ? undefined : normalized;
}

export function deriveAccountSyncStatus(platform: string, account: Record<string, unknown>): SyncStatusUi {
  const normalizedPlatform = String(platform || "").trim().toLowerCase();
  const coverageStatus = toStringOrUndefined(account.coverage_status) ?? toStringOrUndefined(account.sync_health_status);
  const syncHealthStatus = toStringOrUndefined(account.sync_health_status) ?? coverageStatus;
  const lastErrorSummary = toStringOrUndefined(account.last_error_summary);
  const lastError = toStringOrUndefined(account.last_error);

  const details: SyncStatusDetails = {
    coverageStatus,
    syncHealthStatus,
    lastSyncAt: toStringOrUndefined(account.last_sync_at) ?? toStringOrUndefined(account.last_success_at),
    requestedStartDate: toStringOrUndefined(account.requested_start_date),
    requestedEndDate: toStringOrUndefined(account.requested_end_date),
    totalChunkCount: toNumberOrUndefined(account.total_chunk_count),
    successfulChunkCount: toNumberOrUndefined(account.successful_chunk_count),
    failedChunkCount: toNumberOrUndefined(account.failed_chunk_count),
    retryAttempted: typeof account.retry_attempted === "boolean" ? account.retry_attempted : undefined,
    retryRecoveredChunkCount: toNumberOrUndefined(account.retry_recovered_chunk_count),
    rowsWrittenCount: toNumberOrUndefined(account.rows_written_count),
    firstPersistedDate: toStringOrUndefined(account.first_persisted_date),
    lastPersistedDate: toStringOrUndefined(account.last_persisted_date),
    lastErrorSummary,
    lastError,
  };

  if (coverageStatus === "failed_request_coverage") {
    return { uiStatus: "error", uiLabel: "Error", shortReason: "Sync failed coverage", details };
  }
  if (coverageStatus === "partial_request_coverage") {
    return { uiStatus: "warning", uiLabel: "Warning", shortReason: "Partial coverage", details };
  }
  if (coverageStatus === "full_request_coverage") {
    return { uiStatus: "healthy", uiLabel: "Healthy", shortReason: "Full coverage", details };
  }
  if (coverageStatus === "empty_success") {
    return { uiStatus: "healthy", uiLabel: "Healthy", shortReason: "No data in selected window", details };
  }

  if (lastErrorSummary || lastError) {
    const failedHint = [syncHealthStatus, coverageStatus, toStringOrUndefined(account.last_run_status)]
      .filter(Boolean)
      .join(" ")
      .toLowerCase();
    const isFailure = failedHint.includes("fail") || failedHint.includes("error");
    return {
      uiStatus: isFailure ? "error" : "warning",
      uiLabel: isFailure ? "Error" : "Warning",
      shortReason: lastErrorSummary ?? lastError,
      details,
    };
  }

  if (normalizedPlatform !== "meta_ads" && normalizedPlatform !== "tiktok_ads") {
    return { uiStatus: "unknown", uiLabel: "Unknown", shortReason: undefined, details };
  }

  return { uiStatus: "unknown", uiLabel: "Unknown", shortReason: "No sync metadata", details };
}

export function derivePlatformSyncStatus(platform: string, accounts: Array<Record<string, unknown>>): PlatformSyncSummaryUi {
  const accountRows = accounts.map((account) => ({
    id: toStringOrUndefined(account.id) ?? "",
    name: toStringOrUndefined(account.name) ?? toStringOrUndefined(account.id) ?? "Unknown account",
    ui: deriveAccountSyncStatus(platform, account),
  }));

  const errorCount = accountRows.filter((item) => item.ui.uiStatus === "error").length;
  const warningCount = accountRows.filter((item) => item.ui.uiStatus === "warning").length;
  const healthyCount = accountRows.filter((item) => item.ui.uiStatus === "healthy").length;

  const uiStatus: UiSyncStatus = errorCount > 0 ? "error" : warningCount > 0 ? "warning" : healthyCount > 0 ? "healthy" : "unknown";
  const uiLabel = uiStatus === "error" ? "Error" : uiStatus === "warning" ? "Warning" : uiStatus === "healthy" ? "Healthy" : "Unknown";

  return {
    uiStatus,
    uiLabel,
    affectedAccountCount: errorCount + warningCount,
    warningCount,
    errorCount,
    accounts: accountRows,
  };
}
