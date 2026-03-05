import React from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import AgencyAccountsPage from "./page";

const apiMock = vi.hoisted(() => ({
  apiRequest: vi.fn(),
  listAccountSyncRuns: vi.fn(),
}));

vi.mock("@/lib/api", () => ({
  apiRequest: apiMock.apiRequest,
  listAccountSyncRuns: apiMock.listAccountSyncRuns,
}));
vi.mock("@/components/ProtectedPage", () => ({ ProtectedPage: ({ children }: { children: React.ReactNode }) => <>{children}</> }));
vi.mock("@/components/AppShell", () => ({ AppShell: ({ children }: { children: React.ReactNode }) => <>{children}</> }));
vi.mock("next/link", () => ({
  default: ({ href, children, className }: { href: string; children: React.ReactNode; className?: string }) => (
    <a href={href} className={className}>
      {children}
    </a>
  ),
}));

function mockBasePayloads() {
  apiMock.apiRequest.mockImplementation((path: string) => {
    if (path === "/clients") {
      return Promise.resolve({
        items: [
          { id: 11, name: "Client A", owner_email: "a@x.com", display_id: 1 },
          { id: 12, name: "Client B", owner_email: "b@x.com", display_id: 2 },
        ],
      });
    }
    if (path === "/clients/accounts/summary") {
      return Promise.resolve({ items: [{ platform: "google_ads", connected_count: 3, last_import_at: null }] });
    }
    if (path === "/clients/accounts/google") {
      return Promise.resolve({
        count: 3,
        items: [
          {
            id: "1001",
            name: "Account One",
            attached_client_id: 11,
            attached_client_name: "Client A",
            last_run_status: "running",
            has_active_sync: true,
            backfill_completed_through: "2026-01-10",
          },
          {
            id: "1002",
            name: "Account Two",
            attached_client_id: 11,
            attached_client_name: "Client A",
            last_run_status: "done",
            backfill_completed_through: "2026-01-11",
          },
          {
            id: "1003",
            name: "Account Three",
            attached_client_id: null,
            attached_client_name: null,
            last_run_status: "done",
            backfill_completed_through: null,
          },
        ],
      });
    }
    return Promise.resolve({});
  });
  apiMock.listAccountSyncRuns.mockResolvedValue([]);
}

describe("AgencyAccountsPage list redesign + same-client quick view", () => {
  beforeEach(() => {
    vi.useRealTimers();
    apiMock.apiRequest.mockReset();
    apiMock.listAccountSyncRuns.mockReset();
    mockBasePayloads();
  });

  it("renders column headers and preserves account detail link + core actions", async () => {
    render(<AgencyAccountsPage />);

    expect((await screen.findAllByText("Selecție")).length).toBeGreaterThan(0);
    expect((screen.getAllByText("Cont")).length).toBeGreaterThan(0);
    expect((screen.getAllByText("Sync progress")).length).toBeGreaterThan(0);
    expect((screen.getAllByText("Client atașat")).length).toBeGreaterThan(0);
    expect((screen.getAllByText("Acțiuni")).length).toBeGreaterThan(0);
    expect((screen.getAllByText("Detach")).length).toBeGreaterThan(0);

    const accountLink = screen.getByRole("link", { name: "Account One" });
    expect(accountLink).toHaveAttribute("href", "/agency-accounts/google_ads/1001");

    expect(screen.getByRole("button", { name: /Refresh names/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Download historical/i })).toBeInTheDocument();
  });

  it("shows per-client count badge and quick view only for attached rows", async () => {
    render(<AgencyAccountsPage />);
    await screen.findByText("Account One");

    expect(screen.getAllByText("2 conturi atribuite").length).toBeGreaterThanOrEqual(2);
    expect(screen.getAllByRole("button", { name: "Vezi conturile" }).length).toBeGreaterThanOrEqual(2);

    const rowThree = screen.getByText("Account Three").closest("div");
    expect(rowThree?.textContent).not.toContain("Vezi conturile");
    expect(rowThree?.textContent).not.toContain("conturi atribuite");
  });

  it("expands and collapses same-client quick view with detail links", async () => {
    render(<AgencyAccountsPage />);
    await screen.findByText("Account One");

    fireEvent.click(screen.getAllByRole("button", { name: "Vezi conturile" })[0]);

    expect(await screen.findByText("Conturi atribuite aceluiași client")).toBeInTheDocument();
    expect(screen.getByText("curent")).toBeInTheDocument();

    const accountOneLinks = screen.getAllByRole("link", { name: "Account One" });
    const accountTwoLinks = screen.getAllByRole("link", { name: "Account Two" });
    expect(accountOneLinks.some((node) => node.getAttribute("href") === "/agency-accounts/google_ads/1001")).toBe(true);
    expect(accountTwoLinks.some((node) => node.getAttribute("href") === "/agency-accounts/google_ads/1002")).toBe(true);

    fireEvent.click(screen.getByRole("button", { name: "Ascunde conturile" }));
    await waitFor(() => {
      expect(screen.queryByText("Conturi atribuite aceluiași client")).not.toBeInTheDocument();
    });
  });

  it("does not render filled progress for idle/done rows without active sync", async () => {
    render(<AgencyAccountsPage />);
    await screen.findByText("Account One");

    expect(screen.queryByTestId("sync-progress-fill-1002")).not.toBeInTheDocument();
    expect(screen.queryByTestId("sync-progress-fill-1003")).not.toBeInTheDocument();
    expect(screen.getAllByText(/Status: done/i).length).toBeGreaterThan(0);
  });

  it("renders real chunk progress for active rows when backend progress is available", async () => {
    let batchStatusCalls = 0;
    apiMock.apiRequest.mockImplementation((path: string, options?: { method?: string }) => {
      if (path === "/clients") {
        return Promise.resolve({
          items: [
            { id: 11, name: "Client A", owner_email: "a@x.com", display_id: 1 },
            { id: 12, name: "Client B", owner_email: "b@x.com", display_id: 2 },
          ],
        });
      }
      if (path === "/clients/accounts/summary") {
        return Promise.resolve({ items: [{ platform: "google_ads", connected_count: 3, last_import_at: null }] });
      }
      if (path === "/clients/accounts/google") {
        return Promise.resolve({
          count: 3,
          items: [
            { id: "1001", name: "Account One", attached_client_id: 11, attached_client_name: "Client A", last_run_status: "idle" },
            { id: "1002", name: "Account Two", attached_client_id: 11, attached_client_name: "Client A", last_run_status: "done" },
            { id: "1003", name: "Account Three", attached_client_id: null, attached_client_name: null, last_run_status: "done" },
          ],
        });
      }
      if (path === "/agency/sync-runs/batch" && options?.method === "POST") {
        return Promise.resolve({ batch_id: "batch-1", invalid_account_ids: [] });
      }
      if (path === "/agency/sync-runs/batch/batch-1") {
        batchStatusCalls += 1;
        if (batchStatusCalls === 1) {
          return Promise.resolve({
            batch_id: "batch-1",
            progress: { total_runs: 2, queued: 1, running: 1, done: 0, error: 0, percent: 15 },
            runs: [
              { account_id: "1001", status: "running" },
              { account_id: "1002", status: "queued" },
            ],
          });
        }
        return Promise.resolve({
          batch_id: "batch-1",
          progress: { total_runs: 2, queued: 0, running: 0, done: 2, error: 0, percent: 100 },
          runs: [
            { account_id: "1001", status: "done" },
            { account_id: "1002", status: "done" },
          ],
        });
      }
      return Promise.resolve({});
    });

    apiMock.listAccountSyncRuns.mockImplementation((platform: string, accountId: string) => {
      if (platform === "google_ads" && accountId === "1001") {
        return Promise.resolve([{ job_id: "run-1", status: "running", chunks_done: 12, chunks_total: 113 }]);
      }
      if (platform === "google_ads" && accountId === "1002") {
        return Promise.resolve([{ job_id: "run-2", status: "queued", chunks_done: 3, chunks_total: 20 }]);
      }
      return Promise.resolve([]);
    });

    render(<AgencyAccountsPage />);
    await screen.findByText("Account One");

    fireEvent.click(screen.getByLabelText("Select all pe pagina curentă"));
    fireEvent.click(screen.getByRole("button", { name: /Download historical/i }));

    await waitFor(() => {
      expect(screen.getByTestId("sync-progress-fill-1001")).toBeInTheDocument();
      expect(screen.getByTestId("sync-progress-fill-1002")).toBeInTheDocument();
      expect(screen.getByTestId("sync-progress-chunks-1001")).toHaveTextContent("12/113 chunks (11%)");
      expect(screen.getByTestId("sync-progress-chunks-1002")).toHaveTextContent("3/20 chunks (15%)");
    });
  });

  it("starts chunk polling only for active accounts and stops after no active rows", async () => {
    let batchStatusCalls = 0;

    apiMock.apiRequest.mockImplementation((path: string, options?: { method?: string }) => {
      if (path === "/clients") {
        return Promise.resolve({ items: [{ id: 11, name: "Client A", owner_email: "a@x.com", display_id: 1 }] });
      }
      if (path === "/clients/accounts/summary") {
        return Promise.resolve({ items: [{ platform: "google_ads", connected_count: 2, last_import_at: null }] });
      }
      if (path === "/clients/accounts/google") {
        return Promise.resolve({
          count: 2,
          items: [
            { id: "1001", name: "Account One", attached_client_id: 11, attached_client_name: "Client A", last_run_status: "idle", has_active_sync: false },
            { id: "1002", name: "Account Two", attached_client_id: 11, attached_client_name: "Client A", last_run_status: "idle", has_active_sync: false },
          ],
        });
      }
      if (path === "/agency/sync-runs/batch" && options?.method === "POST") {
        return Promise.resolve({ batch_id: "batch-1", invalid_account_ids: [] });
      }
      if (path === "/agency/sync-runs/batch/batch-1") {
        batchStatusCalls += 1;
        if (batchStatusCalls === 1) {
          return Promise.resolve({
            batch_id: "batch-1",
            progress: { total_runs: 2, queued: 0, running: 1, done: 1, error: 0, percent: 55 },
            runs: [
              { account_id: "1001", status: "running" },
              { account_id: "1002", status: "done" },
            ],
          });
        }
        return Promise.resolve({
          batch_id: "batch-1",
          progress: { total_runs: 2, queued: 0, running: 0, done: 2, error: 0, percent: 100 },
          runs: [
            { account_id: "1001", status: "done" },
            { account_id: "1002", status: "done" },
          ],
        });
      }
      return Promise.resolve({});
    });

    apiMock.listAccountSyncRuns.mockImplementation((platform: string, accountId: string) => {
      if (platform === "google_ads" && accountId === "1001") {
        return Promise.resolve([{ job_id: "run-1", status: "running", chunks_done: 1, chunks_total: 10 }]);
      }
      return Promise.resolve([]);
    });

    const intervalRegistry: Array<{ id: number; ms: number; cb: () => void }> = [];
    let intervalId = 1;
    const setIntervalSpy = vi.spyOn(window, "setInterval").mockImplementation((cb: TimerHandler, ms?: number) => {
      const id = intervalId++;
      intervalRegistry.push({ id, ms: Number(ms ?? 0), cb: cb as () => void });
      return id as unknown as number;
    });
    const clearIntervalSpy = vi.spyOn(window, "clearInterval").mockImplementation(() => {});

    render(<AgencyAccountsPage />);
    await screen.findByText("Account One");

    fireEvent.click(screen.getByLabelText("Select all pe pagina curentă"));
    fireEvent.click(screen.getByRole("button", { name: /Download historical/i }));

    await waitFor(() => {
      expect(apiMock.listAccountSyncRuns).toHaveBeenCalledWith("google_ads", "1001", 25);
    });
    expect(apiMock.listAccountSyncRuns).not.toHaveBeenCalledWith("google_ads", "1002", 25);

    const batchInterval = intervalRegistry.find((entry) => entry.ms === 2000);
    expect(batchInterval).toBeDefined();
    batchInterval?.cb();
    await Promise.resolve();
    await Promise.resolve();

    const progressInterval = intervalRegistry.find((entry) => entry.ms === 5000);
    expect(progressInterval).toBeDefined();
    expect(clearIntervalSpy).toHaveBeenCalledWith(progressInterval?.id);

    setIntervalSpy.mockRestore();
    clearIntervalSpy.mockRestore();
  });

  it("keeps client filter behavior with quick-view layout", async () => {
    render(<AgencyAccountsPage />);
    await screen.findByText("Account One");

    fireEvent.change(screen.getByLabelText("Filtru client"), { target: { value: "client a" } });
    expect(screen.getByText("Account One")).toBeInTheDocument();
    expect(screen.getByText("Account Two")).toBeInTheDocument();
    expect(screen.queryByText("Account Three")).not.toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Filtru client"), { target: { value: "none" } });
    await waitFor(() => {
      expect(screen.getByText("Nu există conturi care să corespundă filtrului de client.")).toBeInTheDocument();
    });
  });
});
