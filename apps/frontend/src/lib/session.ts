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

function decodeBase64Url(value: string): string {
  const normalized = value.replace(/-/g, "+").replace(/_/g, "/");
  const padded = normalized + "=".repeat((4 - (normalized.length % 4)) % 4);

  if (typeof window !== "undefined") {
    return window.atob(padded);
  }

  return Buffer.from(padded, "base64").toString("utf-8");
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

export function getCurrentRole(): AppRole {
  if (typeof window === "undefined") return "unknown";

  const token = localStorage.getItem("mcc_token");
  if (!token) return "unknown";

  const [payload] = token.split(".", 1);
  if (!payload) return "unknown";

  try {
    const raw = decodeBase64Url(payload);
    const parsed = JSON.parse(raw) as { role?: string };
    return normalizeAppRole(parsed.role ?? "");
  } catch {
    return "unknown";
  }
}

export function isReadOnlyRole(role: AppRole): boolean {
  return role === "agency_viewer" || role === "subaccount_viewer" || role === "client_viewer";
}

export type SessionInfo = { email: string; role: AppRole };

export function getSessionInfo(): SessionInfo {
  if (typeof window === "undefined") return { email: "", role: "unknown" };
  const token = localStorage.getItem("mcc_token");
  if (!token) return { email: "", role: "unknown" };
  const [payload] = token.split(".", 1);
  if (!payload) return { email: "", role: "unknown" };

  try {
    const raw = decodeBase64Url(payload);
    const parsed = JSON.parse(raw) as { role?: string; email?: string };
    const email = (parsed.email ?? "").toLowerCase();
    return { email, role: normalizeAppRole(parsed.role ?? "") };
  } catch {
    return { email: "", role: "unknown" };
  }
}
