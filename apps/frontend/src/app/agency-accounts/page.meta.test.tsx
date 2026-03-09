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

describe("AgencyAccountsPage Meta unified workspace", () => {
  beforeEach(() => {
    apiMock.apiRequest.mockReset();
    apiMock.postAccountSyncProgressBatch.mockReset();
    apiMock.postAccountSyncProgressBatch.mockResolvedValue({ platform: "google_ads", requested_count: 0, results: [] });

    apiMock.apiRequest.mockImplementation((path: string) => {
      if (path === "/clients") {
        return Promise.resolve({ items: [{ id: 11, name: "Client A", owner_email: "a@example.com", display_id: 1 }] });
      }
      if (path === "/clients/accounts/summary") {
        return Promise.resolve({
          items: [
            { platform: "google_ads", connected_count: 1, last_import_at: null },
            { platform: "meta_ads", connected_count: 2, last_import_at: null },
          ],
        });
      }
      if (path === "/clients/accounts/google") {
        return Promise.resolve({ count: 1, items: [{ id: "1001", name: "G1", attached_client_id: 11, attached_client_name: "Client A" }] });
      }
      if (path === "/clients/accounts/meta_ads") {
        return Promise.resolve({
          count: 2,
          items: [
            { account_id: "act_attached", account_name: "Meta Attached", client_id: 11, client_name: "Client A" },
            { account_id: "act_unattached", account_name: "Meta Free", client_id: null, client_name: null },
          ],
        });
      }
      if (path === "/agency/sync-runs/batch") {
        return Promise.resolve({ batch_id: "meta-batch-1" });
      }
      if (path === "/agency/sync-runs/batch/meta-batch-1") {
        return Promise.resolve({
          batch_id: "meta-batch-1",
          progress: { total_runs: 1, queued: 0, running: 0, done: 1, error: 0, percent: 100 },
          runs: [{ account_id: "act_attached", status: "done" }],
        });
      }
      return Promise.resolve({});
    });
  });

  it("renders Meta in same shell/table layout used by Google", async () => {
    render(<AgencyAccountsPage />);

    fireEvent.click(await screen.findByRole("button", { name: /Meta Ads/i }));

    expect(await screen.findByTestId("platform-workspace-meta_ads")).toBeInTheDocument();
    expect(screen.getByTestId("provider-unified-table-shell")).toBeInTheDocument();
  });

  it("enables attached row checkbox and keeps unattached row disabled", async () => {
    render(<AgencyAccountsPage />);
    fireEvent.click(await screen.findByRole("button", { name: /Meta Ads/i }));

    const attached = await screen.findByTestId("row-select-act_attached");
    const unattached = await screen.findByTestId("row-select-act_unattached");
    expect(attached).not.toBeDisabled();
    expect(unattached).toBeDisabled();
  });

  it("enables Meta historical button after selecting attached account and sends explicit payload", async () => {
    render(<AgencyAccountsPage />);
    fireEvent.click(await screen.findByRole("button", { name: /Meta Ads/i }));

    const historicalBtn = await screen.findByRole("button", { name: "Download historical" });
    expect(historicalBtn).toBeDisabled();

    fireEvent.click(await screen.findByTestId("row-select-act_attached"));
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
      platform: "meta_ads",
      account_ids: ["act_attached"],
      job_type: "historical_backfill",
      start_date: "2024-09-01",
      chunk_days: 30,
      grains: ["account_daily", "campaign_daily", "ad_group_daily", "ad_daily"],
    });
    expect(payload.end_date).toMatch(/^\d{4}-\d{2}-\d{2}$/);
  });

  it("keeps Google historical payload unchanged", async () => {
    render(<AgencyAccountsPage />);

    const historicalBtn = await screen.findByRole("button", { name: "Download historical" });
    fireEvent.click(await screen.findByTestId("row-select-1001"));
    fireEvent.click(historicalBtn);

    await waitFor(() => {
      expect(apiMock.apiRequest).toHaveBeenCalledWith(
        "/agency/sync-runs/batch",
        expect.objectContaining({ method: "POST", body: expect.any(String) }),
      );
    });
    const batchCall = apiMock.apiRequest.mock.calls.find((call: unknown[]) => call[0] === "/agency/sync-runs/batch");
    const payload = JSON.parse(String(batchCall?.[1]?.body ?? "{}"));
    expect(payload.start_date).toBe("2024-01-09");
    expect(payload.grain).toBe("account_daily");
    expect(payload.grains).toBeUndefined();
  });
});
