import { afterEach, describe, expect, it, vi } from "vitest";

import { repairSyncRun, retryFailedSyncRun } from "./api";

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

describe("retryFailedSyncRun", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("calls retry-failed endpoint with POST and returns created payload", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        text: async () => JSON.stringify({ outcome: "created", source_job_id: "src", retry_job_id: "retry-1", status: "queued" }),
      }),
    );

    const result = await retryFailedSyncRun("src");

    expect(fetch).toHaveBeenCalledWith("/api/agency/sync-runs/src/retry-failed", expect.objectContaining({ method: "POST" }));
    expect(result).toEqual({ ok: true, payload: { outcome: "created", source_job_id: "src", retry_job_id: "retry-1", status: "queued" } });
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

    const result = await retryFailedSyncRun("missing");
    expect(result).toEqual({ ok: false, outcome: "not_found", message: "Run-ul nu a fost găsit pentru retry-failed.", status: 404 });
  });
});
