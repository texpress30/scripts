export type AppRole = "super_admin" | "agency_owner" | "agency_admin" | "account_manager" | "client_viewer" | "unknown";

function decodeBase64Url(value: string): string {
  const normalized = value.replace(/-/g, "+").replace(/_/g, "/");
  const padded = normalized + "=".repeat((4 - (normalized.length % 4)) % 4);

  if (typeof window !== "undefined") {
    return window.atob(padded);
  }

  return Buffer.from(padded, "base64").toString("utf-8");
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
    const role = (parsed.role ?? "").toLowerCase();

    if (["super_admin", "agency_owner", "agency_admin", "account_manager", "client_viewer"].includes(role)) {
      return role as AppRole;
    }
    return "unknown";
  } catch {
    return "unknown";
  }
}

export function isReadOnlyRole(role: AppRole): boolean {
  return role === "client_viewer";
}
