import { afterEach, describe, expect, it, vi } from "vitest";

import { repairSyncRun } from "./api";

describe("repairSyncRun", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("calls repair endpoint with POST and returns repaired payload", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        text: async () => JSON.stringify({ job_id: "j1", outcome: "repaired" }),
      }),
    );

    const result = await repairSyncRun("j1");

    expect(fetch).toHaveBeenCalledWith("/api/agency/sync-runs/j1/repair", expect.objectContaining({ method: "POST" }));
    expect(result).toEqual({ ok: true, payload: { job_id: "j1", outcome: "repaired" } });
  });

  it("maps not_found response as outcome not_found", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 404,
        text: async () => JSON.stringify({ detail: { outcome: "not_found" } }),
      }),
    );

    const result = await repairSyncRun("missing");
    expect(result).toEqual({ ok: false, outcome: "not_found", message: "Run-ul nu a fost găsit pentru repair.", status: 404 });
  });
});
