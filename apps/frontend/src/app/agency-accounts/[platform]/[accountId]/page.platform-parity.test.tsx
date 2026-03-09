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
});
