export const API_BASE_URL = "/api";


type RepairRunApiResponse = {
  job_id: string;
  outcome: "repaired" | "noop_not_active" | "noop_active_fresh" | "not_found";
  reason?: string;
  stale_after_minutes?: number;
  active_chunks?: number;
  stale_chunks?: number;
  stale_chunks_closed?: number;
  final_status?: string;
  run?: Record<string, unknown>;
};

export type RepairSyncRunResult =
  | { ok: true; payload: RepairRunApiResponse }
  | { ok: false; outcome: "not_found" | "error"; message: string; status: number };

type RetryFailedRunApiResponse = {
  outcome: "created" | "already_exists" | "no_failed_chunks" | "not_retryable" | "not_found";
  source_job_id?: string;
  retry_job_id?: string;
  platform?: string;
  account_id?: string;
  status?: string;
  chunks_created?: number;
  failed_chunks_count?: number;
};

export type RetryFailedSyncRunResult =
  | { ok: true; payload: RetryFailedRunApiResponse }
  | {
      ok: false;
      outcome: "not_found" | "error";
      message: string;
      status: number;
    };

function extractErrorMessage(detail: string, status: number, requestUrl: string): string {
  const raw = detail.trim();
  if (!raw) return `Request failed: ${status} (${requestUrl})`;
  try {
    const parsed = JSON.parse(raw) as { detail?: unknown; message?: unknown };
    if (typeof parsed.detail === "string" && parsed.detail.trim()) return parsed.detail.trim();
    if (typeof parsed.message === "string" && parsed.message.trim()) return parsed.message.trim();
    if (parsed.detail && typeof parsed.detail === "object") {
      const maybeMessage = (parsed.detail as { message?: unknown }).message;
      if (typeof maybeMessage === "string" && maybeMessage.trim()) return maybeMessage.trim();
    }
  } catch {
    // fallback to raw text below
  }
  return raw;
}

export function getAuthToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("mcc_token");
}

export async function apiRequest<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = getAuthToken();
  const headers = new Headers(options.headers ?? {});
  headers.set("Content-Type", "application/json");
  if (token) headers.set("Authorization", `Bearer ${token}`);

  const requestUrl = `${API_BASE_URL}${path}`;
  const response = await fetch(requestUrl, {
    ...options,
    headers,
    cache: "no-store"
  });

  if (!response.ok) {
    const detail = await response.text();
    throw new Error(extractErrorMessage(detail, response.status, requestUrl));
  }

  return (await response.json()) as T;
}

export async function repairSyncRun(jobId: string): Promise<RepairSyncRunResult> {
  const token = getAuthToken();
  const headers = new Headers();
  headers.set("Content-Type", "application/json");
  if (token) headers.set("Authorization", `Bearer ${token}`);

  const requestUrl = `${API_BASE_URL}/agency/sync-runs/${encodeURIComponent(jobId)}/repair`;
  const response = await fetch(requestUrl, {
    method: "POST",
    headers,
    cache: "no-store",
  });

  const text = await response.text();
  let parsed: { detail?: unknown; message?: unknown; outcome?: unknown } = {};
  if (text) {
    try {
      parsed = JSON.parse(text) as { detail?: unknown; message?: unknown; outcome?: unknown };
    } catch {
      parsed = {};
    }
  }

  if (!response.ok) {
    const detailOutcome =
      typeof parsed.detail === "object" && parsed.detail !== null
        ? (parsed.detail as { outcome?: unknown }).outcome
        : undefined;
    if (detailOutcome === "not_found") {
      return { ok: false, outcome: "not_found", message: "Run-ul nu a fost găsit pentru repair.", status: response.status };
    }
    return {
      ok: false,
      outcome: "error",
      message: extractErrorMessage(text, response.status, requestUrl),
      status: response.status,
    };
  }

  return { ok: true, payload: parsed as RepairRunApiResponse };
}

export async function retryFailedSyncRun(jobId: string): Promise<RetryFailedSyncRunResult> {
  const token = getAuthToken();
  const headers = new Headers();
  headers.set("Content-Type", "application/json");
  if (token) headers.set("Authorization", `Bearer ${token}`);

  const requestUrl = `${API_BASE_URL}/agency/sync-runs/${encodeURIComponent(jobId)}/retry-failed`;
  const response = await fetch(requestUrl, {
    method: "POST",
    headers,
    cache: "no-store",
  });

  const text = await response.text();
  let parsed: { detail?: unknown; message?: unknown; outcome?: unknown } = {};
  if (text) {
    try {
      parsed = JSON.parse(text) as { detail?: unknown; message?: unknown; outcome?: unknown };
    } catch {
      parsed = {};
    }
  }

  if (!response.ok) {
    const detailOutcome =
      typeof parsed.detail === "object" && parsed.detail !== null
        ? (parsed.detail as { outcome?: unknown }).outcome
        : undefined;
    if (detailOutcome === "not_found") {
      return { ok: false, outcome: "not_found", message: "Run-ul nu a fost găsit pentru retry-failed.", status: response.status };
    }
    return {
      ok: false,
      outcome: "error",
      message: extractErrorMessage(text, response.status, requestUrl),
      status: response.status,
    };
  }

  return { ok: true, payload: parsed as RetryFailedRunApiResponse };
}
