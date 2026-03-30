export type AppRole =
  | "super_admin"
  | "agency_owner"
  | "agency_admin"
  | "agency_member"
  | "agency_viewer"
  | "subaccount_admin"
  | "subaccount_user"
  | "subaccount_viewer"
  | "account_manager"
  | "client_viewer"
  | "unknown";

const ROLE_ALIASES: Record<string, AppRole> = {
  account_manager: "subaccount_user",
  client_viewer: "subaccount_viewer",
};

export type SessionAccessSubaccount = { id: number; name: string };

export type SessionAccessContext = {
  email: string;
  role: AppRole;
  access_scope: "agency" | "subaccount" | "unknown";
  allowed_subaccount_ids: number[];
  allowed_subaccounts: SessionAccessSubaccount[];
  primary_subaccount_id: number | null;
};

function decodeBase64Url(value: string): string {
  const normalized = value.replace(/-/g, "+").replace(/_/g, "/");
  const padded = normalized + "=".repeat((4 - (normalized.length % 4)) % 4);

  if (typeof window !== "undefined") {
    return window.atob(padded);
  }

  return Buffer.from(padded, "base64").toString("utf-8");
}

function parseTokenPayload(token: string | null): Record<string, unknown> | null {
  if (!token) return null;
  const [payload] = token.split(".", 1);
  if (!payload) return null;

  try {
    const raw = decodeBase64Url(payload);
    const parsed = JSON.parse(raw) as Record<string, unknown>;
    return parsed;
  } catch {
    return null;
  }
}

function normalizeInt(value: unknown): number | null {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return null;
  return Math.trunc(numeric);
}

function normalizeIntList(value: unknown): number[] {
  if (!Array.isArray(value)) return [];
  const out: number[] = [];
  for (const item of value) {
    const numeric = normalizeInt(item);
    if (numeric === null) continue;
    if (!out.includes(numeric)) out.push(numeric);
  }
  return out;
}

function normalizeAllowedSubaccounts(value: unknown): SessionAccessSubaccount[] {
  if (!Array.isArray(value)) return [];
  const out: SessionAccessSubaccount[] = [];
  for (const item of value) {
    if (!item || typeof item !== "object") continue;
    const candidate = item as { id?: unknown; name?: unknown };
    const id = normalizeInt(candidate.id);
    if (id === null) continue;
    const name = String(candidate.name ?? "");
    if (!out.some((entry) => entry.id === id)) out.push({ id, name });
  }
  return out;
}

function deriveAccessContext(parsed: Record<string, unknown> | null): SessionAccessContext {
  if (!parsed) {
    return {
      email: "",
      role: "unknown",
      access_scope: "unknown",
      allowed_subaccount_ids: [],
      allowed_subaccounts: [],
      primary_subaccount_id: null,
    };
  }

  const role = normalizeAppRole(String(parsed.role ?? ""));
  const email = String(parsed.email ?? "").toLowerCase();

  const legacySubaccountId = normalizeInt(parsed.subaccount_id);
  let allowedIds = normalizeIntList(parsed.allowed_subaccount_ids);
  if (allowedIds.length === 0 && legacySubaccountId !== null) allowedIds = [legacySubaccountId];

  let allowedSubaccounts = normalizeAllowedSubaccounts(parsed.allowed_subaccounts);
  if (allowedSubaccounts.length === 0 && legacySubaccountId !== null) {
    allowedSubaccounts = [{ id: legacySubaccountId, name: String(parsed.subaccount_name ?? "") }];
  }

  let primarySubaccountId = normalizeInt(parsed.primary_subaccount_id);
  if (primarySubaccountId === null && allowedIds.length === 1) {
    primarySubaccountId = allowedIds[0];
  }

  const rawScope = String(parsed.access_scope ?? "").trim().toLowerCase();
  let accessScope: SessionAccessContext["access_scope"] = "unknown";
  if (rawScope === "agency" || rawScope === "subaccount") {
    accessScope = rawScope;
  } else {
    const legacyScope = String(parsed.scope_type ?? "").trim().toLowerCase();
    if (legacyScope === "agency" || legacyScope === "subaccount") {
      accessScope = legacyScope;
    } else if (allowedIds.length > 0) {
      accessScope = "subaccount";
    }
  }

  return {
    email,
    role,
    access_scope: accessScope,
    allowed_subaccount_ids: allowedIds,
    allowed_subaccounts: allowedSubaccounts,
    primary_subaccount_id: primarySubaccountId,
  };
}

export function normalizeAppRole(role: string): AppRole {
  const candidate = role.trim().toLowerCase();
  if (
    [
      "super_admin",
      "agency_owner",
      "agency_admin",
      "agency_member",
      "agency_viewer",
      "subaccount_admin",
      "subaccount_user",
      "subaccount_viewer",
    ].includes(candidate)
  ) {
    return candidate as AppRole;
  }
  return ROLE_ALIASES[candidate] ?? "unknown";
}

export function getSessionAccessContext(): SessionAccessContext {
  if (typeof window === "undefined") {
    return deriveAccessContext(null);
  }
  const token = localStorage.getItem("mcc_token");
  return deriveAccessContext(parseTokenPayload(token));
}

export function getSessionAccessContextFromToken(token: string): SessionAccessContext {
  return deriveAccessContext(parseTokenPayload(token));
}

export function getAllowedSubaccountIds(): number[] {
  return getSessionAccessContext().allowed_subaccount_ids;
}

export function getPrimarySubaccountId(): number | null {
  return getSessionAccessContext().primary_subaccount_id;
}

export function getCurrentRole(): AppRole {
  return getSessionAccessContext().role;
}

export function isReadOnlyRole(role: AppRole): boolean {
  return role === "agency_viewer" || role === "subaccount_viewer" || role === "client_viewer";
}

export function isSubaccountScopedContext(context: SessionAccessContext): boolean {
  if (context.access_scope === "subaccount") return true;
  return context.role === "subaccount_admin" || context.role === "subaccount_user" || context.role === "subaccount_viewer";
}

export type SessionInfo = { email: string; role: AppRole };

export function getSessionInfo(): SessionInfo {
  const context = getSessionAccessContext();
  return { email: context.email, role: context.role };
}
