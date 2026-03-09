import React from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import AgencyAccountsPage from "./page";

const apiMock = vi.hoisted(() => ({
  apiRequest: vi.fn(),
  postAccountSyncProgressBatch: vi.fn(),
}));

vi.mock("@/lib/api", () => ({
  apiRequest: apiMock.apiRequest,
  postAccountSyncProgressBatch: apiMock.postAccountSyncProgressBatch,
}));
vi.mock("@/components/ProtectedPage", () => ({ ProtectedPage: ({ children }: { children: React.ReactNode }) => <>{children}</> }));
vi.mock("@/components/AppShell", () => ({ AppShell: ({ children }: { children: React.ReactNode }) => <>{children}</> }));
vi.mock("next/link", () => ({
  default: ({ href, children }: { href: string; children: React.ReactNode }) => <a href={href}>{children}</a>,
}));

describe("AgencyAccountsPage TikTok historical progress UX", () => {
  beforeEach(() => {
    window.sessionStorage.clear();
    apiMock.apiRequest.mockReset();
    apiMock.postAccountSyncProgressBatch.mockReset();
    apiMock.postAccountSyncProgressBatch.mockResolvedValue({
      platform: "tiktok_ads",
      requested_count: 1,
      results: [{ account_id: "tt_attached", active_run: { job_id: "j1", status: "running", chunks_done: 1, chunks_total: 4 } }],
    });

    apiMock.apiRequest.mockImplementation((path: string) => {
      if (path === "/clients") return Promise.resolve({ items: [{ id: 1, name: "Client A", owner_email: "a@x.com", display_id: 1 }] });
      if (path === "/clients/accounts/summary") return Promise.resolve({ items: [{ platform: "google_ads", connected_count: 1, last_import_at: null }, { platform: "tiktok_ads", connected_count: 2, last_import_at: null }] });
      if (path === "/clients/accounts/google") return Promise.resolve({ items: [{ id: "g_1", name: "G1", attached_client_id: 1, attached_client_name: "Client A" }], count: 1 });
      if (path === "/clients/accounts/tiktok_ads") {
        return Promise.resolve({ items: [{ id: "tt_attached", name: "TikTok One", client_id: 1, client_name: "Client A" }, { id: "tt_unattached", name: "TikTok Two", attached_client_id: null }], count: 2 });
      }
      if (path === "/agency/sync-runs/batch") return Promise.resolve({ batch_id: "tt-batch-1" });
      if (path === "/agency/sync-runs/batch/tt-batch-1") {
        return Promise.resolve({ batch_id: "tt-batch-1", progress: { total_runs: 1, queued: 0, running: 1, done: 0, error: 0, percent: 25 }, runs: [{ account_id: "tt_attached", status: "running" }] });
      }
      return Promise.resolve({});
    });
  });

  it("shows TikTok batch banner and row live progress", async () => {
    render(<AgencyAccountsPage />);
    fireEvent.click(await screen.findByRole("button", { name: /TikTok Ads/i }));
    fireEvent.click(await screen.findByTestId("row-select-tt_attached"));
    fireEvent.click(await screen.findByRole("button", { name: "Download historical" }));

    expect(await screen.findByText(/Batch în progres/i)).toBeInTheDocument();
    expect(await screen.findByTestId("sync-progress-chunks-tt_attached")).toHaveTextContent("1/4 chunks (25%)");
    expect(await screen.findByText(/Batch status: running/i)).toBeInTheDocument();
  });

  it("completion reloads tiktok rows after loadData", async () => {
    let pollCount = 0;
    let tiktokLoads = 0;
    apiMock.apiRequest.mockImplementation((path: string) => {
      if (path === "/clients") return Promise.resolve({ items: [{ id: 1, name: "Client A", owner_email: "a@x.com", display_id: 1 }] });
      if (path === "/clients/accounts/summary") return Promise.resolve({ items: [{ platform: "google_ads", connected_count: 1, last_import_at: null }, { platform: "tiktok_ads", connected_count: 1, last_import_at: null }] });
      if (path === "/clients/accounts/google") return Promise.resolve({ items: [{ id: "g_1", name: "G1", attached_client_id: 1, attached_client_name: "Client A" }], count: 1 });
      if (path === "/clients/accounts/tiktok_ads") {
        tiktokLoads += 1;
        return Promise.resolve({ items: [{ id: "tt_attached", name: "TikTok One", client_id: 1, client_name: "Client A" }], count: 1 });
      }
      if (path === "/agency/sync-runs/batch") return Promise.resolve({ batch_id: "tt-batch-2" });
      if (path === "/agency/sync-runs/batch/tt-batch-2") {
        pollCount += 1;
        if (pollCount === 1) return Promise.resolve({ batch_id: "tt-batch-2", progress: { total_runs: 1, queued: 0, running: 1, done: 0, error: 0, percent: 50 }, runs: [{ account_id: "tt_attached", status: "running" }] });
        return Promise.resolve({ batch_id: "tt-batch-2", progress: { total_runs: 1, queued: 0, running: 0, done: 1, error: 0, percent: 100 }, runs: [{ account_id: "tt_attached", status: "done" }] });
      }
      return Promise.resolve({});
    });

    render(<AgencyAccountsPage />);
    fireEvent.click(await screen.findByRole("button", { name: /TikTok Ads/i }));
    fireEvent.click(await screen.findByTestId("row-select-tt_attached"));
    fireEvent.click(await screen.findByRole("button", { name: "Download historical" }));

    await waitFor(() => {
      expect(tiktokLoads).toBeGreaterThanOrEqual(2);
    }, { timeout: 5000 });
  });

  it("rehydrates persisted tiktok batch id and resumes polling", async () => {
    window.sessionStorage.setItem(
      "agency-accounts-batch:tiktok_ads",
      JSON.stringify({ batchId: "tt-batch-rehydrate", platform: "tiktok_ads", jobType: "historical_backfill", historicalStartDate: "2024-09-01" }),
    );

    apiMock.apiRequest.mockImplementation((path: string) => {
      if (path === "/clients") return Promise.resolve({ items: [{ id: 1, name: "Client A", owner_email: "a@x.com", display_id: 1 }] });
      if (path === "/clients/accounts/summary") return Promise.resolve({ items: [{ platform: "google_ads", connected_count: 1, last_import_at: null }, { platform: "tiktok_ads", connected_count: 1, last_import_at: null }] });
      if (path === "/clients/accounts/google") return Promise.resolve({ items: [{ id: "g_1", name: "G1", attached_client_id: 1, attached_client_name: "Client A" }], count: 1 });
      if (path === "/clients/accounts/tiktok_ads") return Promise.resolve({ items: [{ id: "tt_attached", name: "TikTok One", client_id: 1, client_name: "Client A" }], count: 1 });
      if (path === "/agency/sync-runs/batch/tt-batch-rehydrate") return Promise.resolve({ batch_id: "tt-batch-rehydrate", progress: { total_runs: 1, queued: 0, running: 1, done: 0, error: 0, percent: 20 }, runs: [{ account_id: "tt_attached", status: "running" }] });
      return Promise.resolve({});
    });

    render(<AgencyAccountsPage />);
    fireEvent.click(await screen.findByRole("button", { name: /TikTok Ads/i }));

    await waitFor(() => {
      expect(apiMock.apiRequest).toHaveBeenCalledWith("/agency/sync-runs/batch/tt-batch-rehydrate");
    });
    expect(await screen.findByText(/Batch în progres/i)).toBeInTheDocument();
  });
});
