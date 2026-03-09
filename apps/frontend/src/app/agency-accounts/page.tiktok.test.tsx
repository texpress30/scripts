import React from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";

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

describe("AgencyAccountsPage TikTok unified workspace", () => {
  beforeEach(() => {
    apiMock.apiRequest.mockReset();
    apiMock.postAccountSyncProgressBatch.mockReset();
    apiMock.postAccountSyncProgressBatch.mockResolvedValue({ platform: "google_ads", requested_count: 0, results: [] });

    apiMock.apiRequest.mockImplementation((path: string) => {
      if (path === "/clients") {
        return Promise.resolve({ items: [{ id: 1, name: "Client A", owner_email: "a@x.com", display_id: 1 }] });
      }
      if (path === "/clients/accounts/summary") {
        return Promise.resolve({
          items: [
            { platform: "google_ads", connected_count: 1, last_import_at: null },
            { platform: "tiktok_ads", connected_count: 2, last_import_at: null },
          ],
        });
      }
      if (path === "/clients/accounts/google") {
        return Promise.resolve({ items: [{ id: "g_1", name: "G1", attached_client_id: 1, attached_client_name: "Client A" }], count: 1 });
      }
      if (path === "/clients/accounts/tiktok_ads") {
        return Promise.resolve({
          items: [
            { id: "tt_attached", name: "TikTok One", client_id: 1, client_name: "Client A" },
            { id: "tt_unattached", name: "TikTok Two", attached_client_id: null },
          ],
          count: 2,
        });
      }
      if (path === "/agency/sync-runs/batch") {
        return Promise.resolve({ batch_id: "tt-batch-1" });
      }
      if (path === "/agency/sync-runs/batch/tt-batch-1") {
        return Promise.resolve({
          batch_id: "tt-batch-1",
          progress: { total_runs: 1, queued: 0, running: 0, done: 1, error: 0, percent: 100 },
          runs: [{ account_id: "tt_attached", status: "done" }],
        });
      }
      return Promise.resolve({});
    });
  });

  it("renders TikTok in same shell/table layout used by Google", async () => {
    render(<AgencyAccountsPage />);
    fireEvent.click(await screen.findByRole("button", { name: /TikTok Ads/i }));

    expect(await screen.findByTestId("platform-workspace-tiktok_ads")).toBeInTheDocument();
    expect(screen.getByTestId("provider-unified-table-shell")).toBeInTheDocument();
  });

  it("renders attached client when payload uses attached_client alias", async () => {
    apiMock.apiRequest.mockImplementation((path: string) => {
      if (path === "/clients") return Promise.resolve({ items: [{ id: 1, name: "Client A", owner_email: "a@x.com" }] });
      if (path === "/clients/accounts/summary") return Promise.resolve({ items: [{ platform: "google_ads", connected_count: 0, last_import_at: null }, { platform: "tiktok_ads", connected_count: 1, last_import_at: null }] });
      if (path === "/clients/accounts/google") return Promise.resolve({ items: [], count: 0 });
      if (path === "/clients/accounts/tiktok_ads") return Promise.resolve({ items: [{ id: "tt_1", name: "TikTok One", attached_client_id: 1, attached_client_name: "Client A" }], count: 1 });
      return Promise.resolve({});
    });

    render(<AgencyAccountsPage />);
    fireEvent.click(await screen.findByRole("button", { name: /TikTok Ads/i }));

    expect(await screen.findByText("Client A")).toBeInTheDocument();
  });

  it("enables attached row checkbox and keeps unattached row disabled", async () => {
    render(<AgencyAccountsPage />);
    fireEvent.click(await screen.findByRole("button", { name: /TikTok Ads/i }));

    const attached = await screen.findByTestId("row-select-tt_attached");
    const unattached = await screen.findByTestId("row-select-tt_unattached");
    expect(attached).not.toBeDisabled();
    expect(unattached).toBeDisabled();
  });

  it("enables TikTok historical button after selecting attached account and sends explicit payload", async () => {
    render(<AgencyAccountsPage />);
    fireEvent.click(await screen.findByRole("button", { name: /TikTok Ads/i }));

    const historicalBtn = await screen.findByRole("button", { name: "Download historical" });
    expect(historicalBtn).toBeDisabled();

    fireEvent.click(await screen.findByTestId("row-select-tt_attached"));
    expect(historicalBtn).not.toBeDisabled();
    fireEvent.click(historicalBtn);

    await waitFor(() => {
      expect(apiMock.apiRequest).toHaveBeenCalledWith(
        "/agency/sync-runs/batch",
        expect.objectContaining({ method: "POST", body: expect.any(String) }),
      );
    });

    const batchCall = apiMock.apiRequest.mock.calls.find((call: unknown[]) => call[0] === "/agency/sync-runs/batch");
    const payload = JSON.parse(String(batchCall?.[1]?.body ?? "{}"));
    expect(payload).toMatchObject({
      platform: "tiktok_ads",
      account_ids: ["tt_attached"],
      job_type: "historical_backfill",
      start_date: "2024-09-01",
      chunk_days: 30,
      grains: ["account_daily", "campaign_daily", "ad_group_daily", "ad_daily"],
    });
    expect(payload.end_date).toMatch(/^\d{4}-\d{2}-\d{2}$/);
  });

  it("attach success + reload renders attached client", async () => {
    let reloadCount = 0;
    apiMock.apiRequest.mockImplementation((path: string, options?: { method?: string; body?: string }) => {
      if (path === "/clients") {
        return Promise.resolve({ items: [{ id: 1, name: "Client A", owner_email: "a@x.com", display_id: 1 }] });
      }
      if (path === "/clients/accounts/summary") {
        return Promise.resolve({ items: [{ platform: "google_ads", connected_count: 0, last_import_at: null }, { platform: "tiktok_ads", connected_count: 1, last_import_at: null }] });
      }
      if (path === "/clients/accounts/google") {
        return Promise.resolve({ items: [], count: 0 });
      }
      if (path === "/clients/accounts/tiktok_ads") {
        reloadCount += 1;
        if (reloadCount === 1) {
          return Promise.resolve({ items: [{ id: "tt_1", name: "TikTok One", attached_client_id: null }], count: 1 });
        }
        return Promise.resolve({ items: [{ id: "tt_1", name: "TikTok One", client_id: 1, client_name: "Client A" }], count: 1 });
      }
      if (path === "/clients/1/attach-account") {
        expect(options?.method).toBe("POST");
        expect(options?.body).toContain('"platform":"tiktok_ads"');
        expect(options?.body).toContain('"account_id":"tt_1"');
        return Promise.resolve({ status: "ok" });
      }
      return Promise.resolve({});
    });

    render(<AgencyAccountsPage />);
    fireEvent.click(await screen.findByRole("button", { name: /TikTok Ads/i }));

    await screen.findByText("Neatașat la client");
    const selects = await screen.findAllByRole("combobox");
    const attachSelect = selects.find((element) => within(element).queryByText("Atașează la client..."));
    expect(attachSelect).toBeTruthy();
    fireEvent.change(attachSelect!, { target: { value: "1" } });
    fireEvent.click(screen.getByRole("button", { name: "Attach" }));

    expect(await screen.findByText("Client A")).toBeInTheDocument();
  });
});
