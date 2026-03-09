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
    vi.stubEnv("NEXT_PUBLIC_FF_TIKTOK_INTEGRATION", "1");
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

  it("renders clickable account name to detail route and keeps terminal error visible", async () => {
    apiMock.apiRequest.mockImplementation((path: string) => {
      if (path === "/clients") return Promise.resolve({ items: [{ id: 1, name: "Client A", owner_email: "a@x.com", display_id: 1 }] });
      if (path === "/clients/accounts/summary") return Promise.resolve({ items: [{ platform: "google_ads", connected_count: 1, last_import_at: null }, { platform: "tiktok_ads", connected_count: 1, last_import_at: null }] });
      if (path === "/clients/accounts/google") return Promise.resolve({ items: [{ id: "g_1", name: "G1", attached_client_id: 1, attached_client_name: "Client A" }], count: 1 });
      if (path === "/clients/accounts/tiktok_ads") return Promise.resolve({ items: [{ id: "tt_attached", name: "TikTok One", client_id: 1, client_name: "Client A", last_error: "tiktok terminal failure" }], count: 1 });
      return Promise.resolve({});
    });

    render(<AgencyAccountsPage />);
    fireEvent.click(await screen.findByRole("button", { name: /TikTok Ads/i }));

    const link = await screen.findByRole("link", { name: "TikTok One" });
    expect(link).toHaveAttribute("href", "/agency-accounts/tiktok_ads/tt_attached");
    expect(await screen.findByText(/Eroare recentă:/i)).toBeInTheDocument();
  });

  it("shows TikTok categorized error in list row when error_category is present", async () => {
    apiMock.postAccountSyncProgressBatch.mockResolvedValue({
      platform: "tiktok_ads",
      requested_count: 1,
      results: [
        {
          account_id: "tt_attached",
          active_run: {
            job_id: "j-err",
            status: "running",
            chunks_done: 0,
            chunks_total: 1,
            last_error_summary: "provider said no",
            last_error_category: "provider_access_denied",
          },
        },
      ],
    });
    apiMock.apiRequest.mockImplementation((path: string) => {
      if (path === "/clients") return Promise.resolve({ items: [{ id: 1, name: "Client A", owner_email: "a@x.com", display_id: 1 }] });
      if (path === "/clients/accounts/summary") return Promise.resolve({ items: [{ platform: "google_ads", connected_count: 1, last_import_at: null }, { platform: "tiktok_ads", connected_count: 1, last_import_at: null }] });
      if (path === "/clients/accounts/google") return Promise.resolve({ items: [{ id: "g_1", name: "G1", attached_client_id: 1, attached_client_name: "Client A" }], count: 1 });
      if (path === "/clients/accounts/tiktok_ads") return Promise.resolve({ items: [{ id: "tt_attached", name: "TikTok One", client_id: 1, client_name: "Client A", last_error: "provider said no", last_error_category: "provider_access_denied" }], count: 1 });
      return Promise.resolve({});
    });

    render(<AgencyAccountsPage />);
    fireEvent.click(await screen.findByRole("button", { name: /TikTok Ads/i }));

    expect(await screen.findByText(/Eroare recentă: Acces refuzat de TikTok la advertiser/i)).toBeInTheDocument();
  });

  it("keeps fallback error text when TikTok error category is missing", async () => {
    apiMock.postAccountSyncProgressBatch.mockResolvedValue({ platform: "tiktok_ads", requested_count: 0, results: [] });
    apiMock.apiRequest.mockImplementation((path: string) => {
      if (path === "/clients") return Promise.resolve({ items: [{ id: 1, name: "Client A", owner_email: "a@x.com", display_id: 1 }] });
      if (path === "/clients/accounts/summary") return Promise.resolve({ items: [{ platform: "google_ads", connected_count: 1, last_import_at: null }, { platform: "tiktok_ads", connected_count: 1, last_import_at: null }] });
      if (path === "/clients/accounts/google") return Promise.resolve({ items: [{ id: "g_1", name: "G1", attached_client_id: 1, attached_client_name: "Client A" }], count: 1 });
      if (path === "/clients/accounts/tiktok_ads") return Promise.resolve({ items: [{ id: "tt_attached", name: "TikTok One", client_id: 1, client_name: "Client A", last_error: "legacy tiktok error" }], count: 1 });
      return Promise.resolve({});
    });

    render(<AgencyAccountsPage />);
    fireEvent.click(await screen.findByRole("button", { name: /TikTok Ads/i }));
    expect(await screen.findByText(/Eroare recentă: legacy tiktok error/i)).toBeInTheDocument();
  });

  it("disables Download historical when TikTok feature flag is off", async () => {
    vi.stubEnv("NEXT_PUBLIC_FF_TIKTOK_INTEGRATION", "0");
    render(<AgencyAccountsPage />);
    fireEvent.click(await screen.findByRole("button", { name: /TikTok Ads/i }));

    expect(await screen.findByText(/TikTok sync este dezactivat în acest environment/i)).toBeInTheDocument();
    const button = await screen.findByRole("button", { name: "Download historical" });
    expect(button).toBeDisabled();
  });

  it("keeps Download historical enabled when backend summary reports TikTok enabled", async () => {
    vi.stubEnv("NEXT_PUBLIC_FF_TIKTOK_INTEGRATION", "0");
    apiMock.apiRequest.mockImplementation((path: string) => {
      if (path === "/clients") return Promise.resolve({ items: [{ id: 1, name: "Client A", owner_email: "a@x.com", display_id: 1 }] });
      if (path === "/clients/accounts/summary") return Promise.resolve({ items: [{ platform: "google_ads", connected_count: 1, last_import_at: null }, { platform: "tiktok_ads", connected_count: 1, last_import_at: null, sync_enabled: true }] });
      if (path === "/clients/accounts/google") return Promise.resolve({ items: [{ id: "g_1", name: "G1", attached_client_id: 1, attached_client_name: "Client A" }], count: 1 });
      if (path === "/clients/accounts/tiktok_ads") return Promise.resolve({ items: [{ id: "tt_attached", name: "TikTok One", client_id: 1, client_name: "Client A" }], count: 1, sync_enabled: true });
      return Promise.resolve({});
    });

    render(<AgencyAccountsPage />);
    fireEvent.click(await screen.findByRole("button", { name: /TikTok Ads/i }));
    fireEvent.click(await screen.findByTestId("row-select-tt_attached"));
    expect(screen.queryByText(/TikTok sync este dezactivat în acest environment/i)).not.toBeInTheDocument();
    const button = await screen.findByRole("button", { name: "Download historical" });
    expect(button).not.toBeDisabled();
  });

  it("hides stale feature-flag recent error when TikTok sync is currently enabled", async () => {
    apiMock.apiRequest.mockImplementation((path: string) => {
      if (path === "/clients") return Promise.resolve({ items: [{ id: 1, name: "Client A", owner_email: "a@x.com", display_id: 1 }] });
      if (path === "/clients/accounts/summary") return Promise.resolve({ items: [{ platform: "google_ads", connected_count: 1, last_import_at: null }, { platform: "tiktok_ads", connected_count: 1, last_import_at: null, sync_enabled: true }] });
      if (path === "/clients/accounts/google") return Promise.resolve({ items: [{ id: "g_1", name: "G1", attached_client_id: 1, attached_client_name: "Client A" }], count: 1 });
      if (path === "/clients/accounts/tiktok_ads") {
        return Promise.resolve({
          sync_enabled: true,
          items: [{ id: "tt_attached", name: "TikTok One", client_id: 1, client_name: "Client A", last_error: "TikTok integration is disabled by feature flag." }],
          count: 1,
        });
      }
      return Promise.resolve({});
    });

    render(<AgencyAccountsPage />);
    fireEvent.click(await screen.findByRole("button", { name: /TikTok Ads/i }));

    expect(await screen.findByText(/Eroare recentă: -/i)).toBeInTheDocument();
    expect(screen.queryByText(/TikTok integration is disabled by feature flag/i)).not.toBeInTheDocument();
  });

  it("keeps feature-flag recent error visible when TikTok sync is disabled", async () => {
    apiMock.apiRequest.mockImplementation((path: string) => {
      if (path === "/clients") return Promise.resolve({ items: [{ id: 1, name: "Client A", owner_email: "a@x.com", display_id: 1 }] });
      if (path === "/clients/accounts/summary") return Promise.resolve({ items: [{ platform: "google_ads", connected_count: 1, last_import_at: null }, { platform: "tiktok_ads", connected_count: 1, last_import_at: null, sync_enabled: false }] });
      if (path === "/clients/accounts/google") return Promise.resolve({ items: [{ id: "g_1", name: "G1", attached_client_id: 1, attached_client_name: "Client A" }], count: 1 });
      if (path === "/clients/accounts/tiktok_ads") {
        return Promise.resolve({
          sync_enabled: false,
          items: [{ id: "tt_attached", name: "TikTok One", client_id: 1, client_name: "Client A", last_error: "TikTok integration is disabled by feature flag." }],
          count: 1,
        });
      }
      return Promise.resolve({});
    });

    render(<AgencyAccountsPage />);
    fireEvent.click(await screen.findByRole("button", { name: /TikTok Ads/i }));

    expect(await screen.findByText(/Eroare recentă: TikTok integration is disabled by feature flag/i)).toBeInTheDocument();
  });

});
