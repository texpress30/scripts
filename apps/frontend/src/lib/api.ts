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

export class ApiRequestError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiRequestError";
    this.status = status;
  }
}

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
    throw new ApiRequestError(extractErrorMessage(detail, response.status, requestUrl), response.status);
  }

  return (await response.json()) as T;
}

export type ForgotPasswordApiResponse = {
  message: string;
};

export type ResetPasswordConfirmApiResponse = {
  message: string;
};

export async function forgotPassword(email: string): Promise<ForgotPasswordApiResponse> {
  return apiRequest<ForgotPasswordApiResponse>("/auth/forgot-password", {
    method: "POST",
    body: JSON.stringify({ email }),
  });
}

export async function confirmResetPassword(token: string, newPassword: string): Promise<ResetPasswordConfirmApiResponse> {
  return apiRequest<ResetPasswordConfirmApiResponse>("/auth/reset-password/confirm", {
    method: "POST",
    body: JSON.stringify({ token, new_password: newPassword }),
  });
}


export type AccountSyncRun = {
  job_id: string;
  platform?: string | null;
  account_id?: string | null;
  batch_id?: string | null;
  job_type?: string | null;
  grain?: string | null;
  status?: string | null;
  operational_status?: string | null;
  date_start?: string | null;
  date_end?: string | null;
  chunks_total?: number | null;
  chunks_done?: number | null;
  rows_written?: number | null;
  error_count?: number | null;
  error?: string | null;
  last_error_summary?: string | null;
  last_error_details?: Record<string, unknown> | null;
  last_error_category?: string | null;
  created_at?: string | null;
  started_at?: string | null;
  finished_at?: string | null;
  trigger_source?: string | null;
  metadata?: Record<string, unknown> | null;
};

export type PlatformAccountsResponse = {
  platform: string;
  sync_enabled?: boolean | null;
  items?: Record<string, unknown>[];
  count?: number;
  last_import_at?: string | null;
};

type AccountRunsResponse = {
  platform: string;
  account_id: string;
  limit: number;
  runs: AccountSyncRun[];
};

export async function listAccountSyncRuns(platform: string, accountId: string, limit = 100): Promise<AccountSyncRun[]> {
  const payload = await apiRequest<AccountRunsResponse>(
    `/agency/sync-runs/accounts/${encodeURIComponent(platform)}/${encodeURIComponent(accountId)}?limit=${Math.max(1, Math.floor(limit))}`,
  );
  return payload.runs ?? [];
}


export type AccountSyncProgressActiveRun = {
  job_id: string;
  job_type?: string | null;
  status?: string | null;
  date_start?: string | null;
  date_end?: string | null;
  chunks_done?: number | null;
  chunks_total?: number | null;
  errors_count?: number | null;
  error_chunks?: number | null;
  last_error_summary?: string | null;
  last_error_details?: Record<string, unknown> | null;
  last_error_category?: string | null;
};

export type AccountSyncProgressBatchResult = {
  account_id: string;
  active_run: AccountSyncProgressActiveRun | null;
};

type AccountSyncProgressBatchResponse = {
  platform: string;
  requested_count: number;
  results: AccountSyncProgressBatchResult[];
};

export async function postAccountSyncProgressBatch(
  platform: string,
  accountIds: string[],
  limitActiveOnly = true,
): Promise<AccountSyncProgressBatchResponse> {
  const normalizedPlatform = encodeURIComponent(String(platform).trim());
  const normalizedAccountIds: string[] = [];
  for (const raw of accountIds) {
    const candidate = String(raw).trim();
    if (!candidate) continue;
    if (!normalizedAccountIds.includes(candidate)) normalizedAccountIds.push(candidate);
  }

  return apiRequest<AccountSyncProgressBatchResponse>(`/agency/sync-runs/accounts/${normalizedPlatform}/progress`, {
    method: "POST",
    body: JSON.stringify({
      account_ids: normalizedAccountIds,
      limit_active_only: Boolean(limitActiveOnly),
    }),
  });
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


export type SubaccountTeamMemberItem = {
  membership_id: number;
  user_id: number;
  display_id: string;
  first_name: string;
  last_name: string;
  email: string;
  phone: string;
  extension: string;
  role_key: string;
  role_label: string;
  source_scope: string;
  source_label: string;
  is_active: boolean;
  is_inherited: boolean;
};

export type SubaccountTeamMemberListResponse = {
  items: SubaccountTeamMemberItem[];
  total: number;
  page: number;
  page_size: number;
  subaccount_id: number;
};

export type ListSubaccountTeamMembersParams = {
  subaccountId: number;
  search?: string;
  userRole?: string;
  page?: number;
  pageSize?: number;
};

export type CreateSubaccountTeamMemberPayload = {
  first_name: string;
  last_name: string;
  email: string;
  phone?: string;
  extension?: string;
  user_role?: "subaccount_admin" | "subaccount_user" | "subaccount_viewer";
  password?: string;
};

export async function listSubaccountTeamMembers(params: ListSubaccountTeamMembersParams): Promise<SubaccountTeamMemberListResponse> {
  const qp = new URLSearchParams();
  qp.set("search", params.search ?? "");
  qp.set("user_role", params.userRole ?? "");
  qp.set("page", String(params.page ?? 1));
  qp.set("page_size", String(params.pageSize ?? 10));
  return apiRequest<SubaccountTeamMemberListResponse>(`/team/subaccounts/${encodeURIComponent(String(params.subaccountId))}/members?${qp.toString()}`);
}

export async function createSubaccountTeamMember(subaccountId: number, payload: CreateSubaccountTeamMemberPayload): Promise<{ item: SubaccountTeamMemberItem }> {
  return apiRequest<{ item: SubaccountTeamMemberItem }>(`/team/subaccounts/${encodeURIComponent(String(subaccountId))}/members`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}



export type TeamInviteResponse = {
  message: string;
};

export async function inviteTeamMember(membershipId: string | number): Promise<TeamInviteResponse> {
  return apiRequest<TeamInviteResponse>(`/team/members/${encodeURIComponent(String(membershipId))}/invite`, {
    method: "POST",
    body: JSON.stringify({}),
  });
}

export type MailgunStatusResponse = {
  configured: boolean;
  enabled: boolean;
  domain: string;
  base_url: string;
  from_email: string;
  from_name: string;
  reply_to: string;
  api_key_masked: string;
};

export type MailgunConfigPayload = {
  api_key: string;
  domain: string;
  base_url: string;
  from_email: string;
  from_name: string;
  reply_to?: string;
  enabled?: boolean;
};

export type MailgunTestPayload = {
  to_email: string;
  subject?: string;
  text?: string;
};

export async function getMailgunStatus(): Promise<MailgunStatusResponse> {
  return apiRequest<MailgunStatusResponse>("/agency/integrations/mailgun/status");
}

export async function saveMailgunConfig(payload: MailgunConfigPayload): Promise<MailgunStatusResponse> {
  return apiRequest<MailgunStatusResponse>("/agency/integrations/mailgun/config", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function sendMailgunTestEmail(payload: MailgunTestPayload): Promise<{ ok: boolean; message?: string; id?: string; to_email?: string; subject?: string }> {
  return apiRequest<{ ok: boolean; message?: string; id?: string; to_email?: string; subject?: string }>("/agency/integrations/mailgun/test", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}
