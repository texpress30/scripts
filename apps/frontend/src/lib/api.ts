export const API_BASE_URL = "/api";


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
