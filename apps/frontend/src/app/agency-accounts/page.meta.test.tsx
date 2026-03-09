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

describe("AgencyAccountsPage Meta historical progress UX", () => {
  beforeEach(() => {
    window.sessionStorage.clear();
    apiMock.apiRequest.mockReset();
    apiMock.postAccountSyncProgressBatch.mockReset();
    apiMock.postAccountSyncProgressBatch.mockResolvedValue({
      platform: "meta_ads",
      requested_count: 1,
      results: [{ account_id: "act_attached", active_run: { job_id: "j1", status: "running", chunks_done: 2, chunks_total: 5 } }],
    });

    apiMock.apiRequest.mockImplementation((path: string) => {
      if (path === "/clients") return Promise.resolve({ items: [{ id: 11, name: "Client A", owner_email: "a@example.com", display_id: 1 }] });
      if (path === "/clients/accounts/summary") return Promise.resolve({ items: [{ platform: "google_ads", connected_count: 1, last_import_at: null }, { platform: "meta_ads", connected_count: 2, last_import_at: null }] });
      if (path === "/clients/accounts/google") return Promise.resolve({ count: 1, items: [{ id: "1001", name: "G1", attached_client_id: 11, attached_client_name: "Client A" }] });
      if (path === "/clients/accounts/meta_ads") {
        return Promise.resolve({ count: 2, items: [{ account_id: "act_attached", account_name: "Meta Attached", client_id: 11, client_name: "Client A" }, { account_id: "act_unattached", account_name: "Meta Free", client_id: null, client_name: null }] });
      }
      if (path === "/agency/sync-runs/batch") return Promise.resolve({ batch_id: "meta-batch-1" });
      if (path === "/agency/sync-runs/batch/meta-batch-1") {
        return Promise.resolve({
          batch_id: "meta-batch-1",
          progress: { total_runs: 1, queued: 0, running: 1, done: 0, error: 0, percent: 50 },
          runs: [{ account_id: "act_attached", status: "running" }],
        });
      }
      return Promise.resolve({});
    });
  });

  it("shows Meta batch banner and row live progress", async () => {
    render(<AgencyAccountsPage />);
    fireEvent.click(await screen.findByRole("button", { name: /Meta Ads/i }));
    fireEvent.click(await screen.findByTestId("row-select-act_attached"));
    fireEvent.click(await screen.findByRole("button", { name: "Download historical" }));

    expect(await screen.findByText(/Batch în progres/i)).toBeInTheDocument();
    expect(await screen.findByTestId("sync-progress-chunks-act_attached")).toHaveTextContent("2/5 chunks (40%)");
    expect(await screen.findByText(/Batch status: running/i)).toBeInTheDocument();
  });

  it("completion reloads meta rows after loadData", async () => {
    let pollCount = 0;
    let metaLoads = 0;
    apiMock.apiRequest.mockImplementation((path: string) => {
      if (path === "/clients") return Promise.resolve({ items: [{ id: 11, name: "Client A", owner_email: "a@example.com", display_id: 1 }] });
      if (path === "/clients/accounts/summary") return Promise.resolve({ items: [{ platform: "google_ads", connected_count: 1, last_import_at: null }, { platform: "meta_ads", connected_count: 1, last_import_at: null }] });
      if (path === "/clients/accounts/google") return Promise.resolve({ count: 1, items: [{ id: "1001", name: "G1", attached_client_id: 11, attached_client_name: "Client A" }] });
      if (path === "/clients/accounts/meta_ads") {
        metaLoads += 1;
        return Promise.resolve({ count: 1, items: [{ account_id: "act_attached", account_name: "Meta Attached", client_id: 11, client_name: "Client A" }] });
      }
      if (path === "/agency/sync-runs/batch") return Promise.resolve({ batch_id: "meta-batch-2" });
      if (path === "/agency/sync-runs/batch/meta-batch-2") {
        pollCount += 1;
        if (pollCount === 1) return Promise.resolve({ batch_id: "meta-batch-2", progress: { total_runs: 1, queued: 0, running: 1, done: 0, error: 0, percent: 50 }, runs: [{ account_id: "act_attached", status: "running" }] });
        return Promise.resolve({ batch_id: "meta-batch-2", progress: { total_runs: 1, queued: 0, running: 0, done: 1, error: 0, percent: 100 }, runs: [{ account_id: "act_attached", status: "done" }] });
      }
      return Promise.resolve({});
    });

    render(<AgencyAccountsPage />);
    fireEvent.click(await screen.findByRole("button", { name: /Meta Ads/i }));
    fireEvent.click(await screen.findByTestId("row-select-act_attached"));
    fireEvent.click(await screen.findByRole("button", { name: "Download historical" }));

    await waitFor(() => {
      expect(metaLoads).toBeGreaterThanOrEqual(2);
    }, { timeout: 5000 });
  });

  it("rehydrates persisted meta batch id and resumes polling", async () => {
    window.sessionStorage.setItem(
      "agency-accounts-batch:meta_ads",
      JSON.stringify({ batchId: "meta-batch-rehydrate", platform: "meta_ads", jobType: "historical_backfill", historicalStartDate: "2024-09-01" }),
    );
    apiMock.apiRequest.mockImplementation((path: string) => {
      if (path === "/clients") return Promise.resolve({ items: [{ id: 11, name: "Client A", owner_email: "a@example.com", display_id: 1 }] });
      if (path === "/clients/accounts/summary") return Promise.resolve({ items: [{ platform: "google_ads", connected_count: 1, last_import_at: null }, { platform: "meta_ads", connected_count: 1, last_import_at: null }] });
      if (path === "/clients/accounts/google") return Promise.resolve({ count: 1, items: [{ id: "1001", name: "G1", attached_client_id: 11, attached_client_name: "Client A" }] });
      if (path === "/clients/accounts/meta_ads") return Promise.resolve({ count: 1, items: [{ account_id: "act_attached", account_name: "Meta Attached", client_id: 11, client_name: "Client A" }] });
      if (path === "/agency/sync-runs/batch/meta-batch-rehydrate") {
        return Promise.resolve({ batch_id: "meta-batch-rehydrate", progress: { total_runs: 1, queued: 0, running: 1, done: 0, error: 0, percent: 33 }, runs: [{ account_id: "act_attached", status: "running" }] });
      }
      return Promise.resolve({});
    });

    render(<AgencyAccountsPage />);
    fireEvent.click(await screen.findByRole("button", { name: /Meta Ads/i }));

    await waitFor(() => {
      expect(apiMock.apiRequest).toHaveBeenCalledWith("/agency/sync-runs/batch/meta-batch-rehydrate");
    });
    expect(await screen.findByText(/Batch în progres/i)).toBeInTheDocument();
  });

  it("keeps Google historical payload unchanged", async () => {
    render(<AgencyAccountsPage />);
    fireEvent.click(await screen.findByTestId("row-select-1001"));
    fireEvent.click(await screen.findByRole("button", { name: "Download historical" }));

    await waitFor(() => {
      expect(apiMock.apiRequest).toHaveBeenCalledWith("/agency/sync-runs/batch", expect.objectContaining({ method: "POST", body: expect.any(String) }));
    });
    const batchCall = apiMock.apiRequest.mock.calls.find((call: unknown[]) => call[0] === "/agency/sync-runs/batch");
    const payload = JSON.parse(String(batchCall?.[1]?.body ?? "{}"));
    expect(payload.start_date).toBe("2024-01-09");
    expect(payload.grain).toBe("account_daily");
    expect(payload.grains).toBeUndefined();
  });

  it("renders clickable account name to detail route and keeps terminal error visible", async () => {
    apiMock.apiRequest.mockImplementation((path: string) => {
      if (path === "/clients") return Promise.resolve({ items: [{ id: 1, name: "Client A", owner_email: "a@x.com", display_id: 1 }] });
      if (path === "/clients/accounts/summary") return Promise.resolve({ items: [{ platform: "google_ads", connected_count: 1, last_import_at: null }, { platform: "meta_ads", connected_count: 1, last_import_at: null }] });
      if (path === "/clients/accounts/google") return Promise.resolve({ items: [{ id: "g_1", name: "G1", attached_client_id: 1, attached_client_name: "Client A" }], count: 1 });
      if (path === "/clients/accounts/meta_ads") return Promise.resolve({ items: [{ account_id: "act_attached", account_name: "Meta Attached", client_id: 1, client_name: "Client A", last_error: "meta terminal failure" }], count: 1 });
      return Promise.resolve({});
    });

    render(<AgencyAccountsPage />);
    fireEvent.click(await screen.findByRole("button", { name: /Meta Ads/i }));

    const link = await screen.findByRole("link", { name: "Meta Attached" });
    expect(link).toHaveAttribute("href", "/agency-accounts/meta_ads/act_attached");
    expect(await screen.findByText(/Eroare recentă:/i)).toBeInTheDocument();
  });

});
