import React from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import AgencyAccountDetailPage from "./page";

const paramsState = vi.hoisted(() => ({ platform: "meta_ads", accountId: "act_1" }));
const apiMock = vi.hoisted(() => ({
  apiRequest: vi.fn(),
  listAccountSyncRuns: vi.fn(),
  repairSyncRun: vi.fn(),
  retryFailedSyncRun: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useParams: () => paramsState,
}));

vi.mock("next/link", () => ({
  default: ({ href, children }: { href: string; children: React.ReactNode }) => <a href={href}>{children}</a>,
}));

vi.mock("@/components/ProtectedPage", () => ({ ProtectedPage: ({ children }: { children: React.ReactNode }) => <>{children}</> }));
vi.mock("@/components/AppShell", () => ({ AppShell: ({ children }: { children: React.ReactNode }) => <>{children}</> }));

vi.mock("@/lib/api", () => ({
  apiRequest: apiMock.apiRequest,
  listAccountSyncRuns: apiMock.listAccountSyncRuns,
  repairSyncRun: apiMock.repairSyncRun,
  retryFailedSyncRun: apiMock.retryFailedSyncRun,
}));

describe("Agency Account detail Meta/TikTok parity", () => {
  beforeEach(() => {
    apiMock.apiRequest.mockReset();
    apiMock.listAccountSyncRuns.mockReset();
    apiMock.repairSyncRun.mockReset();
    apiMock.retryFailedSyncRun.mockReset();
    apiMock.listAccountSyncRuns.mockImplementation((platform: string, accountId: string) =>
      apiMock.apiRequest(`/agency/sync-runs/accounts/${encodeURIComponent(platform)}/${encodeURIComponent(accountId)}?limit=100`).then((payload: { runs?: unknown[] }) => payload.runs ?? []),
    );
  });

  it("loads Meta account metadata and shows terminal error banner + logs", async () => {
    paramsState.platform = "meta_ads";
    paramsState.accountId = "act_1";

    apiMock.apiRequest.mockImplementation((path: string) => {
      if (path === "/clients/accounts/meta_ads") return Promise.resolve({ items: [{ account_id: "act_1", account_name: "Meta One", platform: "meta_ads", client_name: "Client A" }] });
      if (path.includes("/accounts/meta_ads/act_1")) {
        return Promise.resolve({
          runs: [{
            job_id: "m-run-1",
            job_type: "historical_backfill",
            status: "error",
            error: "meta provider failed",
            last_error_summary: "Meta API 400 Invalid parameter",
            last_error_details: { provider_error_message: "Invalid parameter", provider_error_code: "100" },
            chunks_total: 2,
            chunks_done: 1,
            created_at: "2026-03-09T10:00:00Z",
          }],
        });
      }
      if (path.includes("/agency/sync-runs/m-run-1/chunks")) {
        return Promise.resolve({ chunks: [{ chunk_index: 0, status: "error", error: "Meta API 400 Invalid parameter" }] });
      }
      return Promise.resolve({});
    });

    render(<AgencyAccountDetailPage />);

    expect(await screen.findByText(/Account: Meta One/)).toBeInTheDocument();
    expect(await screen.findByText(/Ultimul run a eșuat: Meta API 400 Invalid parameter/)).toBeInTheDocument();
    fireEvent.click(await screen.findByText("Show logs"));
    expect(await screen.findByText(/Chunk #0/)).toBeInTheDocument();
  });

  it("loads TikTok account metadata through platform list endpoint", async () => {
    paramsState.platform = "tiktok_ads";
    paramsState.accountId = "tt_1";

    apiMock.apiRequest.mockImplementation((path: string) => {
      if (path === "/clients/accounts/tiktok_ads") return Promise.resolve({ items: [{ id: "tt_1", name: "TikTok One", platform: "tiktok_ads", client_name: "Client B" }] });
      if (path.includes("/accounts/tiktok_ads/tt_1")) {
        return Promise.resolve({ runs: [{ job_id: "tt-run-1", job_type: "historical_backfill", status: "done", chunks_total: 1, chunks_done: 1, created_at: "2026-03-09T09:00:00Z" }] });
      }
      return Promise.resolve({});
    });

    render(<AgencyAccountDetailPage />);

    expect(await screen.findByText(/Account: TikTok One/)).toBeInTheDocument();
    await waitFor(() => {
      expect(apiMock.apiRequest).toHaveBeenCalledWith("/clients/accounts/tiktok_ads");
    });
    expect(screen.getByText(/Sync runs/)).toBeInTheDocument();
  });

  it("renders TikTok error category title and safe details in detail banner and run card", async () => {
    paramsState.platform = "tiktok_ads";
    paramsState.accountId = "tt_1";

    apiMock.apiRequest.mockImplementation((path: string) => {
      if (path === "/clients/accounts/tiktok_ads") {
        return Promise.resolve({ items: [{ id: "tt_1", name: "TikTok One", platform: "tiktok_ads", client_name: "Client B" }] });
      }
      if (path.includes("/accounts/tiktok_ads/tt_1")) {
        return Promise.resolve({
          runs: [
            {
              job_id: "tt-run-err",
              job_type: "historical_backfill",
              status: "error",
              last_error_summary: "provider denied",
              last_error_category: "provider_access_denied",
              last_error_details: { provider_error_message: "Advertiser access denied", provider_error_code: "40300" },
              chunks_total: 1,
              chunks_done: 0,
              created_at: "2026-03-09T09:00:00Z",
            },
          ],
        });
      }
      if (path.includes("/agency/sync-runs/tt-run-err/chunks")) {
        return Promise.resolve({ chunks: [] });
      }
      return Promise.resolve({});
    });

    render(<AgencyAccountDetailPage />);

    expect(await screen.findByText(/Ultimul run a eșuat: Acces refuzat de TikTok la advertiser/i)).toBeInTheDocument();
    fireEvent.click(await screen.findByText("Show logs"));
    expect(await screen.findByText(/Category: Acces refuzat de TikTok la advertiser/i)).toBeInTheDocument();
    expect(await screen.findByText(/Details: Advertiser access denied/i)).toBeInTheDocument();
  });

  it("hides superseded failed historical runs and clears false terminal banner", async () => {
    paramsState.platform = "meta_ads";
    paramsState.accountId = "act_1";

    apiMock.apiRequest.mockImplementation((path: string) => {
      if (path === "/clients/accounts/meta_ads") {
        return Promise.resolve({
          items: [{ account_id: "act_1", account_name: "Meta One", platform: "meta_ads", client_name: "Client A", last_run_status: "done" }],
        });
      }
      if (path.includes("/accounts/meta_ads/act_1")) {
        return Promise.resolve({
          runs: [
            {
              job_id: "m-old-failed",
              job_type: "historical_backfill",
              grain: "account_daily",
              date_start: "2025-01-01",
              date_end: "2025-01-31",
              status: "error",
              last_error_summary: "old historical failure",
              created_at: "2026-03-09T08:00:00Z",
            },
            {
              job_id: "m-new-success",
              job_type: "historical_backfill",
              grain: "account_daily",
              date_start: "2025-01-01",
              date_end: "2025-01-31",
              status: "done",
              created_at: "2026-03-09T10:00:00Z",
            },
          ],
        });
      }
      return Promise.resolve({});
    });

    render(<AgencyAccountDetailPage />);

    await screen.findByText(/Account: Meta One/);
    expect(screen.queryByText(/Ultimul run a eșuat/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/old historical failure/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/old historical failure/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/^failed$/i)).not.toBeInTheDocument();
    expect((await screen.findAllByText(/done/i)).length).toBeGreaterThan(0);
  });

  it("keeps unresolved failed runs visible and keeps banner", async () => {
    paramsState.platform = "meta_ads";
    paramsState.accountId = "act_1";

    apiMock.apiRequest.mockImplementation((path: string) => {
      if (path === "/clients/accounts/meta_ads") {
        return Promise.resolve({ items: [{ account_id: "act_1", account_name: "Meta One", platform: "meta_ads", client_name: "Client A" }] });
      }
      if (path.includes("/accounts/meta_ads/act_1")) {
        return Promise.resolve({
          runs: [
            {
              job_id: "m-failed-unresolved",
              job_type: "historical_backfill",
              grain: "campaign_daily",
              date_start: "2025-02-01",
              date_end: "2025-02-28",
              status: "failed",
              last_error_summary: "still failing",
              created_at: "2026-03-09T09:00:00Z",
            },
            {
              job_id: "m-success-different-scope",
              job_type: "historical_backfill",
              grain: "ad_daily",
              date_start: "2025-02-01",
              date_end: "2025-02-28",
              status: "done",
              created_at: "2026-03-09T10:00:00Z",
            },
          ],
        });
      }
      return Promise.resolve({});
    });

    render(<AgencyAccountDetailPage />);

    expect(await screen.findByText(/Ultimul run a eșuat: still failing/)).toBeInTheDocument();
    expect(screen.getAllByText(/still failing/i).length).toBeGreaterThanOrEqual(1);
  });


  it("renders grain in run title when grain exists", async () => {
    paramsState.platform = "meta_ads";
    paramsState.accountId = "act_1";

    apiMock.apiRequest.mockImplementation((path: string) => {
      if (path === "/clients/accounts/meta_ads") {
        return Promise.resolve({ items: [{ account_id: "act_1", account_name: "Meta One", platform: "meta_ads", client_name: "Client A" }] });
      }
      if (path.includes("/accounts/meta_ads/act_1")) {
        return Promise.resolve({
          runs: [
            {
              job_id: "m-run-grain",
              job_type: "historical_backfill",
              grain: "campaign_daily",
              status: "done",
              created_at: "2026-03-09T10:00:00Z",
            },
          ],
        });
      }
      return Promise.resolve({});
    });

    render(<AgencyAccountDetailPage />);

    expect(await screen.findByText(/historical_backfill · campaign_daily ·/i)).toBeInTheDocument();
  });

  it("keeps title fallback format when grain is missing", async () => {
    paramsState.platform = "meta_ads";
    paramsState.accountId = "act_1";

    apiMock.apiRequest.mockImplementation((path: string) => {
      if (path === "/clients/accounts/meta_ads") {
        return Promise.resolve({ items: [{ account_id: "act_1", account_name: "Meta One", platform: "meta_ads", client_name: "Client A" }] });
      }
      if (path.includes("/accounts/meta_ads/act_1")) {
        return Promise.resolve({
          runs: [
            {
              job_id: "m-run-no-grain",
              job_type: "historical_backfill",
              status: "done",
              created_at: "2026-03-09T10:00:00Z",
            },
          ],
        });
      }
      return Promise.resolve({});
    });

    render(<AgencyAccountDetailPage />);

    expect(await screen.findByText(/historical_backfill ·/i)).toBeInTheDocument();
    expect(screen.queryByText(/historical_backfill ·\s*·/i)).not.toBeInTheDocument();
  });

});
