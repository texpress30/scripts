import { beforeEach, describe, expect, it, vi } from "vitest";

import { ApiRequestError, apiRequest } from "./api";

describe("apiRequest auth hardening", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.stubGlobal("fetch", vi.fn());
    localStorage.clear();
  });

  it("does not send protected request when token is missing", async () => {
    await expect(apiRequest("/company/settings", { requireAuth: true })).rejects.toMatchObject<ApiRequestError>({
      status: 401,
    });
    expect(fetch).not.toHaveBeenCalled();
  });

  it("sends Authorization header when token exists for protected request", async () => {
    localStorage.setItem("mcc_token", "token-123");
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify({ ok: true }), { status: 200, headers: { "Content-Type": "application/json" } }),
    );

    await apiRequest<{ ok: boolean }>("/company/settings", { requireAuth: true });

    const call = vi.mocked(fetch).mock.calls[0];
    const options = call?.[1] as RequestInit;
    const headers = new Headers(options?.headers);
    expect(headers.get("Authorization")).toBe("Bearer token-123");
  });
});
