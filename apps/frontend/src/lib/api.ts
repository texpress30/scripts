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

export type ResetPasswordTokenContextApiResponse = {
  valid: boolean;
  token_type: "invite_user" | "password_reset" | null;
  email_hint?: string | null;
  reason?: string | null;
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

export async function getResetPasswordTokenContext(token: string): Promise<ResetPasswordTokenContextApiResponse> {
  return apiRequest<ResetPasswordTokenContextApiResponse>(`/auth/reset-password/context?token=${encodeURIComponent(token)}`);
}

export type LoginApiRequest = {
  email: string;
  password: string;
  role?: string;
};

export type LoginApiResponse = {
  access_token: string;
  token_type: string;
};

export async function loginWithPassword(payload: LoginApiRequest): Promise<LoginApiResponse> {
  const body: LoginApiRequest = {
    email: payload.email,
    password: payload.password,
  };
  if (payload.role && payload.role.trim() !== "") body.role = payload.role;
  return apiRequest<LoginApiResponse>("/auth/login", {
    method: "POST",
    body: JSON.stringify(body),
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
  membership_status?: "active" | "inactive" | string;
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
  module_keys?: string[];
};

export type TeamModuleCatalogItem = {
  key: string;
  label: string;
  order: number;
  scope: string;
  group_key?: string;
  group_label?: string;
  parent_key?: string | null;
  is_container?: boolean;
};

export type TeamModuleCatalogResponse = {
  items: TeamModuleCatalogItem[];
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

export async function getTeamModuleCatalog(scope: "agency" | "subaccount" = "subaccount"): Promise<TeamModuleCatalogResponse> {
  return apiRequest<TeamModuleCatalogResponse>(`/team/module-catalog?scope=${encodeURIComponent(scope)}`);
}



export type TeamGrantableModuleItem = {
  key: string;
  label: string;
  order: number;
  grantable: boolean;
};

export type TeamGrantableModulesResponse = {
  items: TeamGrantableModuleItem[];
};

export async function getSubaccountGrantableModules(subaccountId: number): Promise<TeamGrantableModulesResponse> {
  return apiRequest<TeamGrantableModulesResponse>(`/team/subaccounts/${encodeURIComponent(String(subaccountId))}/grantable-modules`);
}

export type TeamSubaccountMyAccessResponse = {
  subaccount_id: number;
  role: string;
  module_keys: string[];
  source_scope?: string;
  access_scope?: string;
  unrestricted_modules?: boolean;
};

export async function getSubaccountMyAccess(subaccountId: number): Promise<TeamSubaccountMyAccessResponse> {
  return apiRequest<TeamSubaccountMyAccessResponse>(`/team/subaccounts/${encodeURIComponent(String(subaccountId))}/my-access`);
}

export type SubGoogleAdsTableItem = {
  account_id: string;
  account_name: string;
  status: string;
  cost: number | null;
  rev_inf: number | null;
  roas_inf: number | null;
  mer_inf: number | null;
  truecac_inf: number | null;
  ecr_inf: number | null;
  ecpnv_inf: number | null;
  new_visits: number | null;
  visits: number | null;
  impressions?: number | null;
  clicks?: number | null;
};

export type SubGoogleAdsTableResponse = {
  client_id: number;
  currency: string;
  date_range: { start_date: string; end_date: string };
  items: SubGoogleAdsTableItem[];
};

export type SubAdsCampaignTableItem = {
  campaign_id: string;
  campaign_name: string;
  status: string;
  cost: number | null;
  rev_inf: number | null;
  roas_inf: number | null;
  mer_inf: number | null;
  truecac_inf: number | null;
  ecr_inf: number | null;
  ecpnv_inf: number | null;
  new_visits: number | null;
  visits: number | null;
  impressions?: number | null;
  clicks?: number | null;
};

export type SubAdsCampaignTableResponse = {
  client_id: number;
  platform: string;
  account_id: string;
  account_name: string;
  account_status?: string | null;
  currency: string;
  date_range: { start_date: string; end_date: string };
  items: SubAdsCampaignTableItem[];
};

export type SubAdsCampaignAdGroupTableItem = {
  ad_group_id: string;
  ad_group_name: string;
  status: string;
  cost: number | null;
  rev_inf: number | null;
  roas_inf: number | null;
  mer_inf: number | null;
  truecac_inf: number | null;
  ecr_inf: number | null;
  ecpnv_inf: number | null;
  new_visits: number | null;
  visits: number | null;
  impressions?: number | null;
  clicks?: number | null;
};

export type SubAdsCampaignAdGroupTableResponse = {
  client_id: number;
  platform: string;
  account_id: string;
  account_name: string;
  account_status?: string | null;
  campaign_id: string;
  campaign_name: string;
  currency: string;
  date_range: { start_date: string; end_date: string };
  items: SubAdsCampaignAdGroupTableItem[];
};

export async function getSubGoogleAdsTable(
  subaccountId: number,
  params: { start_date: string; end_date: string },
): Promise<SubGoogleAdsTableResponse> {
  const search = new URLSearchParams({
    start_date: params.start_date,
    end_date: params.end_date,
  });
  return apiRequest<SubGoogleAdsTableResponse>(`/dashboard/${encodeURIComponent(String(subaccountId))}/google-ads-table?${search.toString()}`);
}

export async function getSubMetaAdsTable(
  subaccountId: number,
  params: { start_date: string; end_date: string },
): Promise<SubGoogleAdsTableResponse> {
  const search = new URLSearchParams({
    start_date: params.start_date,
    end_date: params.end_date,
  });
  return apiRequest<SubGoogleAdsTableResponse>(`/dashboard/${encodeURIComponent(String(subaccountId))}/meta-ads-table?${search.toString()}`);
}

export async function getSubTikTokAdsTable(
  subaccountId: number,
  params: { start_date: string; end_date: string },
): Promise<SubGoogleAdsTableResponse> {
  const search = new URLSearchParams({
    start_date: params.start_date,
    end_date: params.end_date,
  });
  return apiRequest<SubGoogleAdsTableResponse>(`/dashboard/${encodeURIComponent(String(subaccountId))}/tiktok-ads-table?${search.toString()}`);
}

export async function getSubGoogleAdsCampaignsTable(
  subaccountId: number,
  accountId: string,
  params: { start_date: string; end_date: string },
): Promise<SubAdsCampaignTableResponse> {
  const search = new URLSearchParams({
    start_date: params.start_date,
    end_date: params.end_date,
  });
  return apiRequest<SubAdsCampaignTableResponse>(
    `/dashboard/${encodeURIComponent(String(subaccountId))}/google-ads/accounts/${encodeURIComponent(accountId)}/campaigns?${search.toString()}`,
  );
}

export async function getSubMetaAdsCampaignsTable(
  subaccountId: number,
  accountId: string,
  params: { start_date: string; end_date: string },
): Promise<SubAdsCampaignTableResponse> {
  const search = new URLSearchParams({
    start_date: params.start_date,
    end_date: params.end_date,
  });
  return apiRequest<SubAdsCampaignTableResponse>(
    `/dashboard/${encodeURIComponent(String(subaccountId))}/meta-ads/accounts/${encodeURIComponent(accountId)}/campaigns?${search.toString()}`,
  );
}

export async function getSubTikTokAdsCampaignsTable(
  subaccountId: number,
  accountId: string,
  params: { start_date: string; end_date: string },
): Promise<SubAdsCampaignTableResponse> {
  const search = new URLSearchParams({
    start_date: params.start_date,
    end_date: params.end_date,
  });
  return apiRequest<SubAdsCampaignTableResponse>(
    `/dashboard/${encodeURIComponent(String(subaccountId))}/tiktok-ads/accounts/${encodeURIComponent(accountId)}/campaigns?${search.toString()}`,
  );
}

export async function getSubGoogleAdsCampaignAdGroupsTable(
  subaccountId: number,
  accountId: string,
  campaignId: string,
  params: { start_date: string; end_date: string },
): Promise<SubAdsCampaignAdGroupTableResponse> {
  const search = new URLSearchParams({
    start_date: params.start_date,
    end_date: params.end_date,
  });
  return apiRequest<SubAdsCampaignAdGroupTableResponse>(
    `/dashboard/${encodeURIComponent(String(subaccountId))}/google-ads/accounts/${encodeURIComponent(accountId)}/campaigns/${encodeURIComponent(campaignId)}/adgroups?${search.toString()}`,
  );
}

export async function getSubMetaAdsCampaignAdGroupsTable(
  subaccountId: number,
  accountId: string,
  campaignId: string,
  params: { start_date: string; end_date: string },
): Promise<SubAdsCampaignAdGroupTableResponse> {
  const search = new URLSearchParams({
    start_date: params.start_date,
    end_date: params.end_date,
  });
  return apiRequest<SubAdsCampaignAdGroupTableResponse>(
    `/dashboard/${encodeURIComponent(String(subaccountId))}/meta-ads/accounts/${encodeURIComponent(accountId)}/campaigns/${encodeURIComponent(campaignId)}/adgroups?${search.toString()}`,
  );
}

export async function getSubTikTokAdsCampaignAdGroupsTable(
  subaccountId: number,
  accountId: string,
  campaignId: string,
  params: { start_date: string; end_date: string },
): Promise<SubAdsCampaignAdGroupTableResponse> {
  const search = new URLSearchParams({
    start_date: params.start_date,
    end_date: params.end_date,
  });
  return apiRequest<SubAdsCampaignAdGroupTableResponse>(
    `/dashboard/${encodeURIComponent(String(subaccountId))}/tiktok-ads/accounts/${encodeURIComponent(accountId)}/campaigns/${encodeURIComponent(campaignId)}/adgroups?${search.toString()}`,
  );
}

export type TeamAgencyMyAccessResponse = {
  role: string;
  module_keys: string[];
  source_scope?: string;
  access_scope?: string;
  unrestricted_modules?: boolean;
};

export async function getAgencyMyAccess(): Promise<TeamAgencyMyAccessResponse> {
  return apiRequest<TeamAgencyMyAccessResponse>("/team/agency/my-access");
}



export type TeamMembershipDetailItem = {
  membership_id: number;
  user_id: number;
  scope_type: "agency" | "subaccount" | string;
  subaccount_id: number | null;
  subaccount_name: string;
  role_key: string;
  role_label: string;
  module_keys: string[];
  allowed_subaccount_ids?: number[];
  allowed_subaccounts?: { id: number; name: string; label?: string }[];
  has_restricted_subaccount_access?: boolean;
  source_scope: string;
  is_inherited: boolean;
  membership_status?: "active" | "inactive" | string;
  first_name: string;
  last_name: string;
  email: string;
  phone: string;
  extension: string;
};

export type TeamMembershipDetailResponse = {
  item: TeamMembershipDetailItem;
};

export type UpdateTeamMembershipPayload = {
  user_role?: string;
  module_keys?: string[];
  allowed_subaccount_ids?: number[];
};

export async function getTeamMembershipDetail(membershipId: string | number): Promise<TeamMembershipDetailResponse> {
  return apiRequest<TeamMembershipDetailResponse>(`/team/members/${encodeURIComponent(String(membershipId))}`);
}

export async function updateTeamMembership(
  membershipId: string | number,
  payload: UpdateTeamMembershipPayload,
): Promise<TeamMembershipDetailResponse> {
  return apiRequest<TeamMembershipDetailResponse>(`/team/members/${encodeURIComponent(String(membershipId))}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}


export type TeamMembershipStatusResponse = {
  membership_id: number;
  status: "active" | "inactive" | string;
  message: string;
};

export async function deactivateTeamMember(membershipId: string | number): Promise<TeamMembershipStatusResponse> {
  return apiRequest<TeamMembershipStatusResponse>(`/team/members/${encodeURIComponent(String(membershipId))}/deactivate`, {
    method: "POST",
    body: JSON.stringify({}),
  });
}

export async function reactivateTeamMember(membershipId: string | number): Promise<TeamMembershipStatusResponse> {
  return apiRequest<TeamMembershipStatusResponse>(`/team/members/${encodeURIComponent(String(membershipId))}/reactivate`, {
    method: "POST",
    body: JSON.stringify({}),
  });
}


export type TeamMembershipRemoveResponse = {
  membership_id: number;
  removed: boolean;
  message: string;
};

export async function removeTeamMember(membershipId: string | number): Promise<TeamMembershipRemoveResponse> {
  return apiRequest<TeamMembershipRemoveResponse>(`/team/members/${encodeURIComponent(String(membershipId))}/remove`, {
    method: "POST",
    body: JSON.stringify({}),
  });
}

export type TeamUserDeleteResponse = {
  user_id: number;
  deleted: boolean;
  deleted_memberships_count: number;
  message: string;
};

export async function deleteTeamUser(userId: string | number): Promise<TeamUserDeleteResponse> {
  return apiRequest<TeamUserDeleteResponse>(`/team/users/${encodeURIComponent(String(userId))}/delete`, {
    method: "POST",
    body: JSON.stringify({}),
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


export type AgencyEmailTemplateListItem = {
  key: string;
  label: string;
  description: string;
  scope: string;
  enabled: boolean;
  is_overridden: boolean;
  updated_at: string | null;
};

export type AgencyEmailTemplateListResponse = {
  items: AgencyEmailTemplateListItem[];
};

export type AgencyEmailTemplateDetail = {
  key: string;
  label: string;
  description: string;
  subject: string;
  text_body: string;
  html_body: string;
  available_variables: string[];
  scope: string;
  enabled: boolean;
  is_overridden: boolean;
  updated_at: string | null;
};

export type SaveAgencyEmailTemplatePayload = {
  subject: string;
  text_body: string;
  html_body?: string;
  enabled?: boolean;
};

export async function getAgencyEmailTemplates(): Promise<AgencyEmailTemplateListResponse> {
  return apiRequest<AgencyEmailTemplateListResponse>("/agency/email-templates");
}

export async function getAgencyEmailTemplate(templateKey: string): Promise<AgencyEmailTemplateDetail> {
  return apiRequest<AgencyEmailTemplateDetail>(`/agency/email-templates/${encodeURIComponent(templateKey)}`);
}

export async function saveAgencyEmailTemplate(
  templateKey: string,
  payload: SaveAgencyEmailTemplatePayload,
): Promise<AgencyEmailTemplateDetail> {
  return apiRequest<AgencyEmailTemplateDetail>(`/agency/email-templates/${encodeURIComponent(templateKey)}`, {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}

export async function resetAgencyEmailTemplate(templateKey: string): Promise<AgencyEmailTemplateDetail> {
  return apiRequest<AgencyEmailTemplateDetail>(`/agency/email-templates/${encodeURIComponent(templateKey)}/reset`, {
    method: "POST",
    body: JSON.stringify({}),
  });
}

export type PreviewAgencyEmailTemplatePayload = {
  subject?: string;
  text_body?: string;
  html_body?: string;
};

export type PreviewAgencyEmailTemplateResponse = {
  key: string;
  rendered_subject: string;
  rendered_text_body: string;
  rendered_html_body: string;
  sample_variables: Record<string, string>;
  is_overridden: boolean;
};

export async function previewAgencyEmailTemplate(
  templateKey: string,
  payload?: PreviewAgencyEmailTemplatePayload,
): Promise<PreviewAgencyEmailTemplateResponse> {
  return apiRequest<PreviewAgencyEmailTemplateResponse>(`/agency/email-templates/${encodeURIComponent(templateKey)}/preview`, {
    method: "POST",
    body: JSON.stringify(payload ?? {}),
  });
}

export type SendAgencyEmailTemplateTestPayload = {
  to_email: string;
  subject?: string;
  text_body?: string;
  html_body?: string;
};

export type SendAgencyEmailTemplateTestResponse = {
  key: string;
  to_email: string;
  accepted: boolean;
  delivery_status: "accepted" | string;
  rendered_subject: string;
  provider_message: string;
  provider_id: string;
};

export async function sendAgencyEmailTemplateTest(
  templateKey: string,
  payload: SendAgencyEmailTemplateTestPayload,
): Promise<SendAgencyEmailTemplateTestResponse> {
  return apiRequest<SendAgencyEmailTemplateTestResponse>(`/agency/email-templates/${encodeURIComponent(templateKey)}/test-send`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export type AgencyEmailNotificationListItem = {
  key: string;
  label: string;
  description: string;
  channel: string;
  scope: string;
  template_key: string;
  enabled: boolean;
  is_overridden: boolean;
  updated_at: string | null;
};

export type AgencyEmailNotificationListResponse = {
  items: AgencyEmailNotificationListItem[];
};

export type AgencyEmailNotificationDetail = {
  key: string;
  label: string;
  description: string;
  channel: string;
  scope: string;
  template_key: string;
  enabled: boolean;
  default_enabled: boolean;
  is_overridden: boolean;
  updated_at: string | null;
};

export type SaveAgencyEmailNotificationPayload = {
  enabled: boolean;
};

export async function getAgencyEmailNotifications(): Promise<AgencyEmailNotificationListResponse> {
  return apiRequest<AgencyEmailNotificationListResponse>("/agency/email-notifications");
}

export async function getAgencyEmailNotification(notificationKey: string): Promise<AgencyEmailNotificationDetail> {
  return apiRequest<AgencyEmailNotificationDetail>(`/agency/email-notifications/${encodeURIComponent(notificationKey)}`);
}

export async function saveAgencyEmailNotification(
  notificationKey: string,
  payload: SaveAgencyEmailNotificationPayload,
): Promise<AgencyEmailNotificationDetail> {
  return apiRequest<AgencyEmailNotificationDetail>(`/agency/email-notifications/${encodeURIComponent(notificationKey)}`, {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}

export async function resetAgencyEmailNotification(notificationKey: string): Promise<AgencyEmailNotificationDetail> {
  return apiRequest<AgencyEmailNotificationDetail>(`/agency/email-notifications/${encodeURIComponent(notificationKey)}/reset`, {
    method: "POST",
    body: JSON.stringify({}),
  });
}

export type MailgunStatusResponse = {
  configured: boolean;
  enabled: boolean;
  config_source?: "db" | "env" | "none" | string;
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

export async function getMailgunStatus(): Promise<MailgunStatusResponse> {
  return apiRequest<MailgunStatusResponse>("/agency/integrations/mailgun/status");
}

export async function saveMailgunConfig(payload: MailgunConfigPayload): Promise<MailgunStatusResponse> {
  return apiRequest<MailgunStatusResponse>("/agency/integrations/mailgun/config", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}
