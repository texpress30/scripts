import { describe, expect, it } from "vitest";

import { getEffectiveAccountStatus, getTikTokErrorPresentation, isRunSupersededByLaterSuccess, shouldDisplayRunByDefault } from "./sync-runs";

describe("sync-runs helpers", () => {
  it("marks failed historical run superseded by later success on same scope", () => {
    const failed = {
      job_id: "f1",
      job_type: "historical_backfill",
      status: "error",
      grain: "account_daily",
      date_start: "2025-01-01",
      date_end: "2025-01-31",
      created_at: "2026-03-09T08:00:00Z",
    };
    const success = {
      job_id: "s1",
      job_type: "historical_backfill",
      status: "done",
      grain: "account_daily",
      date_start: "2025-01-01",
      date_end: "2025-01-31",
      created_at: "2026-03-09T10:00:00Z",
    };

    expect(isRunSupersededByLaterSuccess(failed, [failed, success])).toBe(true);
    expect(shouldDisplayRunByDefault(failed, [failed, success])).toBe(false);
  });

  it("does not supersede failed run when later success is on different grain", () => {
    const failed = {
      job_id: "f1",
      job_type: "historical_backfill",
      status: "failed",
      grain: "campaign_daily",
      date_start: "2025-01-01",
      date_end: "2025-01-31",
      created_at: "2026-03-09T08:00:00Z",
    };
    const success = {
      job_id: "s1",
      job_type: "historical_backfill",
      status: "done",
      grain: "ad_daily",
      date_start: "2025-01-01",
      date_end: "2025-01-31",
      created_at: "2026-03-09T10:00:00Z",
    };

    expect(isRunSupersededByLaterSuccess(failed, [failed, success])).toBe(false);
    expect(shouldDisplayRunByDefault(failed, [failed, success])).toBe(true);
  });

  it("keeps done when no row status/last_run_status but last_success_at is present", () => {
    expect(
      getEffectiveAccountStatus({
        rowStatus: null,
        lastRunStatus: null,
        hasActiveSync: false,
        lastSuccessAt: "2026-03-09T10:00:00Z",
      }),
    ).toBe("done");
  });

  it("maps TikTok error category to clear UX message", () => {
    const presentation = getTikTokErrorPresentation("provider_access_denied", "provider technical message");
    expect(presentation.title).toBe("Acces refuzat de TikTok la advertiser");
    expect(presentation.details).toBe("provider technical message");
  });

  it("falls back to legacy message when TikTok error category is missing", () => {
    const presentation = getTikTokErrorPresentation(undefined, "legacy fallback error");
    expect(presentation.title).toBe("legacy fallback error");
    expect(presentation.details).toBeNull();
  });
});
