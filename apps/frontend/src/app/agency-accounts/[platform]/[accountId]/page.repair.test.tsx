import React from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import AgencyAccountDetailPage from "./page";

const apiMock = vi.hoisted(() => ({
  apiRequest: vi.fn(),
  repairSyncRun: vi.fn(),
  retryFailedSyncRun: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useParams: () => ({ platform: "google_ads", accountId: "3986597205" }),
}));

vi.mock("next/link", () => ({
  default: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

vi.mock("@/components/ProtectedPage", () => ({
  ProtectedPage: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

vi.mock("@/components/AppShell", () => ({
  AppShell: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

vi.mock("@/lib/api", () => ({
  apiRequest: apiMock.apiRequest,
  repairSyncRun: apiMock.repairSyncRun,
  retryFailedSyncRun: apiMock.retryFailedSyncRun,
}));

function accountMeta() {
  return {
    items: [
      {
        id: "3986597205",
        name: "Anime Dating",
        platform: "google_ads",
        attached_client_name: "Anime Dating",
        has_active_sync: true,
      },
    ],
  };
}

describe("AgencyAccountDetailPage repair/retry actions", () => {
  beforeEach(() => {
    vi.useRealTimers();
    apiMock.apiRequest.mockReset();
    apiMock.repairSyncRun.mockReset();
    apiMock.retryFailedSyncRun.mockReset();
  });

  it("shows repair button for active historical_backfill run and sends repair request", async () => {
    apiMock.apiRequest.mockImplementation((path: string) => {
      if (path === "/clients/accounts/google") return Promise.resolve(accountMeta());
      if (path.includes("/accounts/google_ads/3986597205")) {
        return Promise.resolve({
          platform: "google_ads",
          account_id: "3986597205",
          limit: 100,
          runs: [{ job_id: "job-1", job_type: "historical_backfill", status: "running", created_at: "2026-03-04T10:00:00Z" }],
        });
      }
      return Promise.resolve({ chunks: [] });
    });

    let resolveRepair: ((value: unknown) => void) | null = null;
    apiMock.repairSyncRun.mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveRepair = resolve;
        }),
    );

    render(<AgencyAccountDetailPage />);

    const button = await screen.findByRole("button", { name: "Repară sync blocat" });
    fireEvent.click(button);

    expect(apiMock.repairSyncRun).toHaveBeenCalledWith("job-1");
    expect(await screen.findByRole("button", { name: "Se repară..." })).toBeDisabled();

    resolveRepair?.({ ok: true, payload: { job_id: "job-1", outcome: "noop_active_fresh" } });
    expect(await screen.findByText("Run-ul este încă activ și fresh. Repair-ul nu s-a aplicat încă.")).toBeInTheDocument();
  });

  it("does not show repair button for terminal run", async () => {
    apiMock.apiRequest.mockImplementation((path: string) => {
      if (path === "/clients/accounts/google") return Promise.resolve(accountMeta());
      if (path.includes("/accounts/google_ads/3986597205")) {
        return Promise.resolve({
          platform: "google_ads",
          account_id: "3986597205",
          limit: 100,
          runs: [{ job_id: "job-2", job_type: "historical_backfill", status: "done", created_at: "2026-03-04T10:00:00Z" }],
        });
      }
      return Promise.resolve({ chunks: [] });
    });

    render(<AgencyAccountDetailPage />);

    await screen.findByText("Auto-refresh oprit (nu există run activ).");
    expect(screen.queryByRole("button", { name: "Repară sync blocat" })).not.toBeInTheDocument();
  });

  it("shows retry button for retryable terminal historical run", async () => {
    apiMock.apiRequest.mockImplementation((path: string) => {
      if (path === "/clients/accounts/google") return Promise.resolve(accountMeta());
      if (path.includes("/accounts/google_ads/3986597205")) {
        return Promise.resolve({
          platform: "google_ads",
          account_id: "3986597205",
          limit: 100,
          runs: [{ job_id: "job-r1", job_type: "historical_backfill", status: "error", error_count: 2, created_at: "2026-03-04T10:00:00Z" }],
        });
      }
      return Promise.resolve({ chunks: [] });
    });

    render(<AgencyAccountDetailPage />);

    expect(await screen.findByRole("button", { name: "Reia chunk-urile eșuate" })).toBeInTheDocument();
  });

  it("hides retry button for active or non-historical runs", async () => {
    apiMock.apiRequest.mockImplementation((path: string) => {
      if (path === "/clients/accounts/google") return Promise.resolve(accountMeta());
      if (path.includes("/accounts/google_ads/3986597205")) {
        return Promise.resolve({
          platform: "google_ads",
          account_id: "3986597205",
          limit: 100,
          runs: [
            { job_id: "job-r2", job_type: "historical_backfill", status: "running", error_count: 2, created_at: "2026-03-04T10:00:00Z" },
            { job_id: "job-r3", job_type: "rolling_window", status: "error", error_count: 2, created_at: "2026-03-04T09:00:00Z" },
          ],
        });
      }
      return Promise.resolve({ chunks: [] });
    });

    render(<AgencyAccountDetailPage />);

    await screen.findByText("Auto-refresh activ (există run queued/running/pending).");
    expect(screen.queryByRole("button", { name: "Reia chunk-urile eșuate" })).not.toBeInTheDocument();
  });

  it("hides retry button when a retry historical run is already active", async () => {
    apiMock.apiRequest.mockImplementation((path: string) => {
      if (path === "/clients/accounts/google") return Promise.resolve(accountMeta());
      if (path.includes("/accounts/google_ads/3986597205")) {
        return Promise.resolve({
          platform: "google_ads",
          account_id: "3986597205",
          limit: 100,
          runs: [
            { job_id: "job-old-terminal", job_type: "historical_backfill", status: "error", error_count: 1, created_at: "2026-03-04T10:00:00Z" },
            { job_id: "job-retry-active", job_type: "historical_backfill", status: "running", created_at: "2026-03-04T10:30:00Z" },
          ],
        });
      }
      return Promise.resolve({ chunks: [] });
    });

    render(<AgencyAccountDetailPage />);

    await screen.findByText("Auto-refresh activ (există run queued/running/pending).");
    expect(screen.queryByRole("button", { name: "Reia chunk-urile eșuate" })).not.toBeInTheDocument();
  });

  it("hides active error banner and retry CTA when source run is fully recovered by retry", async () => {
    apiMock.apiRequest.mockImplementation((path: string) => {
      if (path === "/clients/accounts/google") {
        return Promise.resolve({
          items: [
            {
              ...accountMeta().items[0],
              sync_start_date: "2026-01-01",
              backfill_completed_through: "2026-01-10",
              last_run_status: "done",
              has_active_sync: false,
            },
          ],
        });
      }
      if (path.includes("/accounts/google_ads/3986597205")) {
        return Promise.resolve({
          platform: "google_ads",
          account_id: "3986597205",
          limit: 100,
          runs: [
            {
              job_id: "retry-done",
              job_type: "historical_backfill",
              status: "done",
              metadata: { retry_of_job_id: "source-error", retry_reason: "failed_chunks" },
              created_at: "2026-03-04T11:00:00Z",
            },
            {
              job_id: "source-error",
              job_type: "historical_backfill",
              status: "error",
              error: "chunk failed old",
              error_count: 1,
              date_start: "2026-01-01",
              date_end: "2026-01-10",
              created_at: "2026-03-04T10:00:00Z",
            },
          ],
        });
      }
      return Promise.resolve({ chunks: [] });
    });

    render(<AgencyAccountDetailPage />);

    await screen.findByText("Auto-refresh oprit (nu există run activ).");
    expect(screen.queryByText(/Ultimul run a eșuat:/)).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Reia chunk-urile eșuate" })).not.toBeInTheDocument();
  });

  it("keeps retry CTA and error banner for partially recovered source run", async () => {
    apiMock.apiRequest.mockImplementation((path: string) => {
      if (path === "/clients/accounts/google") {
        return Promise.resolve({
          items: [
            {
              ...accountMeta().items[0],
              sync_start_date: "2026-01-01",
              backfill_completed_through: "2026-01-05",
              last_run_status: "done",
              has_active_sync: false,
            },
          ],
        });
      }
      if (path.includes("/accounts/google_ads/3986597205")) {
        return Promise.resolve({
          platform: "google_ads",
          account_id: "3986597205",
          limit: 100,
          runs: [
            {
              job_id: "retry-done-partial",
              job_type: "historical_backfill",
              status: "done",
              metadata: { retry_of_job_id: "source-partial", retry_reason: "failed_chunks" },
              created_at: "2026-03-04T11:00:00Z",
            },
            {
              job_id: "source-partial",
              job_type: "historical_backfill",
              status: "error",
              error: "still has failed chunks",
              error_count: 1,
              date_start: "2026-01-01",
              date_end: "2026-01-10",
              created_at: "2026-03-04T10:00:00Z",
            },
          ],
        });
      }
      return Promise.resolve({ chunks: [] });
    });

    render(<AgencyAccountDetailPage />);

    expect(await screen.findByRole("button", { name: "Reia chunk-urile eșuate" })).toBeInTheDocument();
    expect(screen.getByText(/Ultimul run a eșuat: still has failed chunks/)).toBeInTheDocument();
  });

  it("sends retry request and keeps button disabled in-flight", async () => {
    apiMock.apiRequest.mockImplementation((path: string) => {
      if (path === "/clients/accounts/google") return Promise.resolve(accountMeta());
      if (path.includes("/accounts/google_ads/3986597205")) {
        return Promise.resolve({
          platform: "google_ads",
          account_id: "3986597205",
          limit: 100,
          runs: [{ job_id: "job-r4", job_type: "historical_backfill", status: "error", error_count: 1, created_at: "2026-03-04T10:00:00Z" }],
        });
      }
      return Promise.resolve({ chunks: [] });
    });

    let resolveRetry: ((value: unknown) => void) | null = null;
    apiMock.retryFailedSyncRun.mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveRetry = resolve;
        }),
    );

    render(<AgencyAccountDetailPage />);

    const retryButton = await screen.findByRole("button", { name: "Reia chunk-urile eșuate" });
    fireEvent.click(retryButton);

    expect(apiMock.retryFailedSyncRun).toHaveBeenCalledWith("job-r4");
    expect(await screen.findByRole("button", { name: "Se pornește retry..." })).toBeDisabled();

    resolveRetry?.({ ok: true, payload: { outcome: "no_failed_chunks", source_job_id: "job-r4" } });
    expect(await screen.findByText("Run-ul nu are chunk-uri eșuate de reluat.")).toBeInTheDocument();
  });

  it("on created refetches and keeps polling active when retry run is active", async () => {
    const setIntervalSpy = vi.spyOn(window, "setInterval");
    let runsCallCount = 0;

    apiMock.apiRequest.mockImplementation((path: string) => {
      if (path === "/clients/accounts/google") return Promise.resolve(accountMeta());
      if (path.includes("/accounts/google_ads/3986597205")) {
        runsCallCount += 1;
        if (runsCallCount <= 1) {
          return Promise.resolve({
            platform: "google_ads",
            account_id: "3986597205",
            limit: 100,
            runs: [{ job_id: "job-r5", job_type: "historical_backfill", status: "error", error_count: 2, created_at: "2026-03-04T10:00:00Z" }],
          });
        }
        return Promise.resolve({
          platform: "google_ads",
          account_id: "3986597205",
          limit: 100,
          runs: [{ job_id: "job-retry", job_type: "historical_backfill", status: "queued", created_at: "2026-03-04T11:00:00Z" }],
        });
      }
      return Promise.resolve({ chunks: [] });
    });

    apiMock.retryFailedSyncRun.mockResolvedValue({ ok: true, payload: { outcome: "created", source_job_id: "job-r5", retry_job_id: "job-retry" } });

    render(<AgencyAccountDetailPage />);

    const retryButton = await screen.findByRole("button", { name: "Reia chunk-urile eșuate" });
    fireEvent.click(retryButton);

    await waitFor(() => {
      expect(screen.getByText("Retry pornit pentru chunk-urile eșuate. Am reîncărcat statusul run-urilor.")).toBeInTheDocument();
    });
    await waitFor(() => {
      expect(screen.getByText("Auto-refresh activ (există run queued/running/pending).")).toBeInTheDocument();
    });
    expect(setIntervalSpy).toHaveBeenCalled();
  });

  it("keeps header synced with runs when runs are newer than account meta", async () => {
    apiMock.apiRequest.mockImplementation((path: string) => {
      if (path === "/clients/accounts/google") {
        return Promise.resolve({
          items: [
            {
              ...accountMeta().items[0],
              has_active_sync: true,
              last_run_status: "queued",
              last_run_type: "historical_backfill",
              last_run_started_at: "2026-03-04T09:00:00Z",
              last_run_finished_at: null,
            },
          ],
        });
      }
      if (path.includes("/accounts/google_ads/3986597205")) {
        return Promise.resolve({
          platform: "google_ads",
          account_id: "3986597205",
          limit: 100,
          runs: [
            {
              job_id: "job-finished",
              job_type: "historical_backfill",
              status: "done",
              created_at: "2026-03-04T10:00:00Z",
              started_at: "2026-03-04T10:00:00Z",
              finished_at: "2026-03-04T10:10:00Z",
            },
          ],
        });
      }
      return Promise.resolve({ chunks: [] });
    });

    render(<AgencyAccountDetailPage />);

    expect(await screen.findByText("Auto-refresh oprit (nu există run activ).")).toBeInTheDocument();
    expect(screen.getByText("Fără sync activ")).toBeInTheDocument();
    expect(screen.getByText("Ultimul status: done")).toBeInTheDocument();
  });

  it("polling reloads account metadata and ends in coherent stopped state", async () => {
    vi.useRealTimers();
    let metaCallCount = 0;
    let runsCallCount = 0;

    apiMock.apiRequest.mockImplementation((path: string) => {
      if (path === "/clients/accounts/google") {
        metaCallCount += 1;
        if (metaCallCount <= 2) {
          return Promise.resolve({
            items: [
              {
                ...accountMeta().items[0],
                has_active_sync: true,
                last_run_status: "queued",
              },
            ],
          });
        }
        return Promise.resolve({
          items: [
            {
              ...accountMeta().items[0],
              has_active_sync: false,
              last_run_status: "done",
            },
          ],
        });
      }

      if (path.includes("/accounts/google_ads/3986597205")) {
        runsCallCount += 1;
        if (runsCallCount <= 2) {
          return Promise.resolve({
            platform: "google_ads",
            account_id: "3986597205",
            limit: 100,
            runs: [{ job_id: "job-live", job_type: "historical_backfill", status: "running", created_at: "2026-03-04T10:00:00Z" }],
          });
        }
        return Promise.resolve({
          platform: "google_ads",
          account_id: "3986597205",
          limit: 100,
          runs: [{ job_id: "job-live", job_type: "historical_backfill", status: "done", created_at: "2026-03-04T10:00:00Z", finished_at: "2026-03-04T10:10:00Z" }],
        });
      }
      return Promise.resolve({ chunks: [] });
    });

    render(<AgencyAccountDetailPage />);
    await screen.findByText("Auto-refresh activ (există run queued/running/pending).");

    await waitFor(() => {
      expect(screen.getByText("Auto-refresh oprit (nu există run activ).")).toBeInTheDocument();
    }, { timeout: 10000 });
    await waitFor(() => {
      expect(screen.getByText("Fără sync activ")).toBeInTheDocument();
    }, { timeout: 10000 });
    expect(metaCallCount).toBeGreaterThan(1);
    expect(runsCallCount).toBeGreaterThan(1);
  }, 12000);

  it("shows info on already_exists and refetches", async () => {
    let runsCallCount = 0;
    apiMock.apiRequest.mockImplementation((path: string) => {
      if (path === "/clients/accounts/google") return Promise.resolve(accountMeta());
      if (path.includes("/accounts/google_ads/3986597205")) {
        runsCallCount += 1;
        if (runsCallCount === 1) {
          return Promise.resolve({
            platform: "google_ads",
            account_id: "3986597205",
            limit: 100,
            runs: [{ job_id: "job-r6", job_type: "historical_backfill", status: "error", error_count: 1, created_at: "2026-03-04T10:00:00Z" }],
          });
        }
        return Promise.resolve({
          platform: "google_ads",
          account_id: "3986597205",
          limit: 100,
          runs: [{ job_id: "job-retry-existing", job_type: "historical_backfill", status: "running", created_at: "2026-03-04T10:30:00Z" }],
        });
      }
      return Promise.resolve({ chunks: [] });
    });

    apiMock.retryFailedSyncRun.mockResolvedValue({ ok: true, payload: { outcome: "already_exists", source_job_id: "job-r6", retry_job_id: "job-retry-existing" } });

    render(<AgencyAccountDetailPage />);

    const retryButton = await screen.findByRole("button", { name: "Reia chunk-urile eșuate" });
    fireEvent.click(retryButton);

    await waitFor(() => {
      expect(screen.getByText("Există deja un retry activ pentru acest run. Am reîncărcat statusul.")).toBeInTheDocument();
    });
    expect(runsCallCount).toBeGreaterThan(1);
  });

  it("shows messages for not_retryable and HTTP/network errors", async () => {
    apiMock.apiRequest.mockImplementation((path: string) => {
      if (path === "/clients/accounts/google") return Promise.resolve(accountMeta());
      if (path.includes("/accounts/google_ads/3986597205")) {
        return Promise.resolve({
          platform: "google_ads",
          account_id: "3986597205",
          limit: 100,
          runs: [{ job_id: "job-r7", job_type: "historical_backfill", status: "error", error_count: 1, created_at: "2026-03-04T10:00:00Z" }],
        });
      }
      return Promise.resolve({ chunks: [] });
    });

    apiMock.retryFailedSyncRun.mockResolvedValueOnce({ ok: true, payload: { outcome: "not_retryable", source_job_id: "job-r7" } });
    apiMock.retryFailedSyncRun.mockResolvedValueOnce({ ok: false, outcome: "error", status: 500, message: "Server timeout retry" });

    render(<AgencyAccountDetailPage />);

    const retryButton = await screen.findByRole("button", { name: "Reia chunk-urile eșuate" });
    fireEvent.click(retryButton);
    expect(await screen.findByText("Run-ul nu este eligibil pentru retry-failed.")).toBeInTheDocument();

    fireEvent.click(await screen.findByRole("button", { name: "Reia chunk-urile eșuate" }));
    expect(await screen.findByText("Server timeout retry")).toBeInTheDocument();
  });

  it("on repaired refetches and stops polling when no active runs remain", async () => {
    const setIntervalSpy = vi.spyOn(window, "setInterval");
    const clearIntervalSpy = vi.spyOn(window, "clearInterval");
    let runsCallCount = 0;

    apiMock.apiRequest.mockImplementation((path: string) => {
      if (path === "/clients/accounts/google") return Promise.resolve(accountMeta());
      if (path.includes("/accounts/google_ads/3986597205")) {
        runsCallCount += 1;
        if (runsCallCount <= 1) {
          return Promise.resolve({
            platform: "google_ads",
            account_id: "3986597205",
            limit: 100,
            runs: [{ job_id: "job-3", job_type: "historical_backfill", status: "running", created_at: "2026-03-04T10:00:00Z" }],
          });
        }
        return Promise.resolve({
          platform: "google_ads",
          account_id: "3986597205",
          limit: 100,
          runs: [{ job_id: "job-3", job_type: "historical_backfill", status: "done", created_at: "2026-03-04T10:00:00Z" }],
        });
      }
      return Promise.resolve({ chunks: [] });
    });

    apiMock.repairSyncRun.mockResolvedValue({ ok: true, payload: { job_id: "job-3", outcome: "repaired" } });

    render(<AgencyAccountDetailPage />);

    const button = await screen.findByRole("button", { name: "Repară sync blocat" });
    fireEvent.click(button);

    await waitFor(() => {
      expect(screen.getByText("Repair aplicat. Am reîncărcat statusul run-urilor.")).toBeInTheDocument();
    });
    await waitFor(() => {
      expect(screen.getByText("Auto-refresh oprit (nu există run activ).")).toBeInTheDocument();
    });
    expect(setIntervalSpy).toHaveBeenCalled();
    expect(clearIntervalSpy).toHaveBeenCalled();
  });

  it("shows useful error message when repair fails", async () => {
    apiMock.apiRequest.mockImplementation((path: string) => {
      if (path === "/clients/accounts/google") return Promise.resolve(accountMeta());
      if (path.includes("/accounts/google_ads/3986597205")) {
        return Promise.resolve({
          platform: "google_ads",
          account_id: "3986597205",
          limit: 100,
          runs: [{ job_id: "job-4", job_type: "historical_backfill", status: "running", created_at: "2026-03-04T10:00:00Z" }],
        });
      }
      return Promise.resolve({ chunks: [] });
    });

    apiMock.repairSyncRun.mockResolvedValue({ ok: false, outcome: "error", status: 500, message: "Server timeout" });

    render(<AgencyAccountDetailPage />);

    const button = await screen.findByRole("button", { name: "Repară sync blocat" });
    fireEvent.click(button);

    expect(await screen.findByText("Server timeout")).toBeInTheDocument();
  });
});
