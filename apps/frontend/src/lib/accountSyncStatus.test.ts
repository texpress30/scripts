import { describe, expect, it } from "vitest";

import { deriveAccountSyncStatus } from "@/lib/accountSyncStatus";

describe("deriveAccountSyncStatus", () => {
  it("maps failed_request_coverage to Error", () => {
    const result = deriveAccountSyncStatus("meta_ads", { coverage_status: "failed_request_coverage" });
    expect(result.uiStatus).toBe("error");
  });

  it("maps partial_request_coverage to Warning", () => {
    const result = deriveAccountSyncStatus("meta_ads", { coverage_status: "partial_request_coverage" });
    expect(result.uiStatus).toBe("warning");
  });

  it("maps full_request_coverage to Healthy", () => {
    const result = deriveAccountSyncStatus("meta_ads", { coverage_status: "full_request_coverage" });
    expect(result.uiStatus).toBe("healthy");
  });

  it("maps empty_success to Healthy", () => {
    const result = deriveAccountSyncStatus("meta_ads", { coverage_status: "empty_success" });
    expect(result.uiStatus).toBe("healthy");
  });

  it("maps TikTok with last_error_summary to warning/error and not healthy", () => {
    const result = deriveAccountSyncStatus("tiktok_ads", { last_error_summary: "token refresh failed", last_run_status: "error" });
    expect(["warning", "error"]).toContain(result.uiStatus);
  });

  it("maps no metadata to Unknown", () => {
    const result = deriveAccountSyncStatus("meta_ads", {});
    expect(result.uiStatus).toBe("unknown");
  });
});
