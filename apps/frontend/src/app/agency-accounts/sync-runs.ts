import type { AccountSyncRun } from "@/lib/api";

export function normalizeStatus(status?: string | null): string {
  return String(status ?? "").trim().toLowerCase();
}

export function normalizeJobType(jobType?: string | null): string {
  return String(jobType ?? "").trim().toLowerCase();
}

export function isRunActive(status?: string | null): boolean {
  return ["queued", "running", "pending"].includes(normalizeStatus(status));
}

export function isRunSuccess(status?: string | null): boolean {
  return ["done", "success", "completed"].includes(normalizeStatus(status));
}

export function isRunFailure(status?: string | null): boolean {
  return ["error", "failed", "partial"].includes(normalizeStatus(status));
}

function parseTimestamp(value?: string | null): number {
  if (!value) return 0;
  const ts = new Date(value).getTime();
  return Number.isFinite(ts) ? ts : 0;
}

function parseDateOnly(value?: string | null): number | null {
  const raw = String(value ?? "").trim();
  if (!raw) return null;
  const parsed = Date.parse(raw.length <= 10 ? `${raw}T00:00:00Z` : raw);
  if (Number.isNaN(parsed)) return null;
  return parsed;
}

function retrySourceJobId(run: AccountSyncRun): string {
  const metadata = run.metadata && typeof run.metadata === "object" ? run.metadata : {};
  const retryReason = String((metadata as { retry_reason?: unknown }).retry_reason ?? "").trim();
  if (retryReason !== "failed_chunks") return "";
  return String((metadata as { retry_of_job_id?: unknown }).retry_of_job_id ?? "").trim();
}

function matchesScopeConservatively(failed: AccountSyncRun, success: AccountSyncRun): boolean {
  const failedAccountId = String(failed.account_id ?? "").trim();
  const successAccountId = String(success.account_id ?? "").trim();
  if (failedAccountId && successAccountId && failedAccountId !== successAccountId) return false;

  const failedPlatform = String(failed.platform ?? "").trim();
  const successPlatform = String(success.platform ?? "").trim();
  if (failedPlatform && successPlatform && failedPlatform !== successPlatform) return false;

  const failedGrain = String(failed.grain ?? "").trim();
  const successGrain = String(success.grain ?? "").trim();
  if (failedGrain && successGrain && failedGrain !== successGrain) return false;

  const failedStart = parseDateOnly(failed.date_start);
  const failedEnd = parseDateOnly(failed.date_end);
  const successStart = parseDateOnly(success.date_start);
  const successEnd = parseDateOnly(success.date_end);

  if (failedStart !== null && failedEnd !== null) {
    if (successStart === null || successEnd === null) return false;
    return successStart <= failedStart && successEnd >= failedEnd;
  }

  if (failedStart !== null) {
    if (successStart === null) return false;
    return successStart <= failedStart;
  }

  if (failedEnd !== null) {
    if (successEnd === null) return false;
    return successEnd >= failedEnd;
  }

  return true;
}

function rangeCoveredByAccountMeta(run: AccountSyncRun, accountSyncStart?: string | null, accountBackfillThrough?: string | null): boolean {
  const accountStart = parseDateOnly(accountSyncStart);
  const accountEnd = parseDateOnly(accountBackfillThrough);
  const runStart = parseDateOnly(run.date_start);
  const runEnd = parseDateOnly(run.date_end);
  if (accountStart === null || accountEnd === null || runStart === null || runEnd === null) return false;
  return accountStart <= runStart && accountEnd >= runEnd;
}

function runTime(run: AccountSyncRun): number {
  return parseTimestamp(run.finished_at) || parseTimestamp(run.started_at) || parseTimestamp(run.created_at);
}

export function isRunSupersededByLaterSuccess(
  run: AccountSyncRun,
  allRuns: AccountSyncRun[],
  options?: { accountSyncStart?: string | null; accountBackfillThrough?: string | null },
): boolean {
  if (normalizeJobType(run.job_type) !== "historical_backfill") return false;
  if (!isRunFailure(run.status)) return false;

  const failedTime = runTime(run);
  if (failedTime <= 0) return false;

  return allRuns.some((candidate) => {
    if (candidate.job_id === run.job_id) return false;
    if (normalizeJobType(candidate.job_type) !== "historical_backfill") return false;
    if (!isRunSuccess(candidate.status)) return false;
    if (runTime(candidate) <= failedTime) return false;
    if (retrySourceJobId(candidate) === run.job_id) {
      return rangeCoveredByAccountMeta(run, options?.accountSyncStart, options?.accountBackfillThrough);
    }
    return matchesScopeConservatively(run, candidate);
  });
}

export function shouldDisplayRunByDefault(
  run: AccountSyncRun,
  allRuns: AccountSyncRun[],
  options?: { accountSyncStart?: string | null; accountBackfillThrough?: string | null },
): boolean {
  return !isRunSupersededByLaterSuccess(run, allRuns, options);
}

export function getEffectiveAccountStatus(input: {
  rowStatus?: string | null;
  lastRunStatus?: string | null;
  hasActiveSync?: boolean | null;
  lastSuccessAt?: string | null;
}): string {
  const row = normalizeStatus(input.rowStatus);
  if (row) return row;

  const lastRunStatus = normalizeStatus(input.lastRunStatus);
  if (lastRunStatus) return lastRunStatus;

  if (input.hasActiveSync) return "running";
  if (String(input.lastSuccessAt ?? "").trim()) return "done";
  return "idle";
}

export type TikTokErrorPresentation = {
  title: string;
  details: string | null;
};

export function getTikTokErrorPresentation(errorCategory?: string | null, fallbackMessage?: string | null): TikTokErrorPresentation {
  const normalizedCategory = String(errorCategory ?? "").trim().toLowerCase();
  const fallback = String(fallbackMessage ?? "").trim();

  const titleByCategory: Record<string, string> = {
    local_attachment_error: "Cont TikTok neatașat clientului",
    provider_access_denied: "Acces refuzat de TikTok la advertiser",
    token_missing_or_invalid: "Token TikTok lipsă sau invalid",
    provider_http_error_generic: "Eroare TikTok API",
    integration_disabled: "TikTok sync este dezactivat în acest environment",
  };

  const title = titleByCategory[normalizedCategory] ?? (fallback || "Eroare TikTok API");
  if (!fallback || fallback === title) {
    return { title, details: null };
  }

  return { title, details: fallback };
}
