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
            sync_start_date: "2025-12-01",
          },
          {
            id: "1002",
            name: "Account Two",
            attached_client_id: 11,
            attached_client_name: "Client A",
            last_run_status: "error",
            backfill_completed_through: "2026-01-11",
            rolling_synced_through: "2026-01-14",
            sync_start_date: "2025-12-01",
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
  apiMock.postAccountSyncProgressBatch.mockResolvedValue({ platform: "google_ads", requested_count: 0, results: [] });
}

describe("AgencyAccountsPage list redesign + same-client quick view", () => {
  beforeEach(() => {
    vi.useRealTimers();
    apiMock.apiRequest.mockReset();
    apiMock.postAccountSyncProgressBatch.mockReset();
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


  it("filters Active to show only active rows", async () => {
    render(<AgencyAccountsPage />);
    await screen.findByText("Account One");

    fireEvent.change(screen.getByLabelText("Filtru rapid"), { target: { value: "active" } });

    expect(screen.getByText("Account One")).toBeInTheDocument();
    expect(screen.queryByText("Account Two")).not.toBeInTheDocument();
    expect(screen.queryByText("Account Three")).not.toBeInTheDocument();
  });

  it("filters Errors to show only error/failed rows", async () => {
    render(<AgencyAccountsPage />);
    await screen.findByText("Account One");

    fireEvent.change(screen.getByLabelText("Filtru rapid"), { target: { value: "errors" } });

    expect(screen.getByText("Account Two")).toBeInTheDocument();
    expect(screen.queryByText("Account One")).not.toBeInTheDocument();
    expect(screen.queryByText("Account Three")).not.toBeInTheDocument();
  });

  it("filters Neinițializate to show only rows without sync_start_date", async () => {
    render(<AgencyAccountsPage />);
    await screen.findByText("Account One");

    fireEvent.change(screen.getByLabelText("Filtru rapid"), { target: { value: "uninitialized" } });

    expect(screen.getByText("Account Three")).toBeInTheDocument();
    expect(screen.queryByText("Account One")).not.toBeInTheDocument();
    expect(screen.queryByText("Account Two")).not.toBeInTheDocument();
  });

  it("select all on current page respects active quick filter", async () => {
    render(<AgencyAccountsPage />);
    await screen.findByText("Account One");

    fireEvent.change(screen.getByLabelText("Filtru rapid"), { target: { value: "active" } });
    fireEvent.click(screen.getByLabelText("Select all pe pagina curentă"));

    expect(screen.getByText(/Selectate:/)).toHaveTextContent("Selectate: 1 conturi");
  });

  it("select all filtered selects across pages and persists when paging", async () => {
    apiMock.apiRequest.mockImplementation((path: string) => {
      if (path === "/clients") {
        return Promise.resolve({ items: [{ id: 11, name: "Client A", owner_email: "a@x.com", display_id: 1 }] });
      }
      if (path === "/clients/accounts/summary") {
        return Promise.resolve({ items: [{ platform: "google_ads", connected_count: 55, last_import_at: null }] });
      }
      if (path === "/clients/accounts/google") {
        return Promise.resolve({
          count: 55,
          items: Array.from({ length: 55 }).map((_, index) => ({
            id: String(2000 + index),
            name: `Account ${index + 1}`,
            attached_client_id: 11,
            attached_client_name: "Client A",
            last_run_status: "idle",
            sync_start_date: "2025-12-01",
          })),
        });
      }
      return Promise.resolve({});
    });

    render(<AgencyAccountsPage />);
    await screen.findByText("Account 1");

    fireEvent.change(screen.getByDisplayValue("50"), { target: { value: "25" } });
    fireEvent.click(screen.getByLabelText("Selectează toate filtrate (55)"));

    expect(screen.getByText(/Selectate:/)).toHaveTextContent("Selectate: 55 conturi");

    fireEvent.click(screen.getByRole("button", { name: "Următor" }));
    await screen.findByText("Account 26");

    expect(screen.getByTestId("row-select-2025")).toBeChecked();

    fireEvent.click(screen.getByRole("button", { name: "Anterior" }));
    await screen.findByText("Account 1");
    expect(screen.getByTestId("row-select-2000")).toBeChecked();
  });

  it("clear selection resets selection set and row checkboxes", async () => {
    render(<AgencyAccountsPage />);
    await screen.findByText("Account One");

    fireEvent.click(screen.getByLabelText("Select all pe pagina curentă"));
    expect(screen.getByText(/Selectate:/)).toHaveTextContent("Selectate: 2 conturi");

    fireEvent.click(screen.getByRole("button", { name: "Clear selection" }));
    expect(screen.getByText(/Selectate:/)).toHaveTextContent("Selectate: 0 conturi");

    expect(screen.getByTestId("row-select-1001")).not.toBeChecked();
    expect(screen.getByTestId("row-select-1002")).not.toBeChecked();
  });

  it("select all page selects only current page rows", async () => {
    apiMock.apiRequest.mockImplementation((path: string) => {
      if (path === "/clients") {
        return Promise.resolve({ items: [{ id: 11, name: "Client A", owner_email: "a@x.com", display_id: 1 }] });
      }
      if (path === "/clients/accounts/summary") {
        return Promise.resolve({ items: [{ platform: "google_ads", connected_count: 60, last_import_at: null }] });
      }
      if (path === "/clients/accounts/google") {
        return Promise.resolve({
          count: 60,
          items: Array.from({ length: 60 }).map((_, index) => ({
            id: String(3000 + index),
            name: `Account ${index + 1}`,
            attached_client_id: 11,
            attached_client_name: "Client A",
            last_run_status: "idle",
            sync_start_date: "2025-12-01",
          })),
        });
      }
      return Promise.resolve({});
    });

    render(<AgencyAccountsPage />);
    await screen.findByText("Account 1");

    fireEvent.change(screen.getByDisplayValue("50"), { target: { value: "25" } });
    fireEvent.click(screen.getByLabelText("Select all pe pagina curentă"));

    expect(screen.getByText(/Selectate:/)).toHaveTextContent("Selectate: 25 conturi");

    fireEvent.click(screen.getByRole("button", { name: "Următor" }));
    await screen.findByText("Account 26");
    expect(screen.getByTestId("row-select-3025")).not.toBeChecked();
  });

  it("Neinițializate + select all filtered selects only rows without sync_start_date", async () => {
    apiMock.apiRequest.mockImplementation((path: string) => {
      if (path === "/clients") {
        return Promise.resolve({ items: [{ id: 11, name: "Client A", owner_email: "a@x.com", display_id: 1 }] });
      }
      if (path === "/clients/accounts/summary") {
        return Promise.resolve({ items: [{ platform: "google_ads", connected_count: 4, last_import_at: null }] });
      }
      if (path === "/clients/accounts/google") {
        return Promise.resolve({
          count: 4,
          items: [
            { id: "4001", name: "Ready A", attached_client_id: 11, attached_client_name: "Client A", last_run_status: "idle", sync_start_date: "2025-12-01" },
            { id: "4002", name: "No Start A", attached_client_id: 11, attached_client_name: "Client A", last_run_status: "idle", sync_start_date: null },
            { id: "4003", name: "No Start B", attached_client_id: 11, attached_client_name: "Client A", last_run_status: "idle", sync_start_date: "" },
            { id: "4004", name: "Ready B", attached_client_id: 11, attached_client_name: "Client A", last_run_status: "idle", sync_start_date: "2025-12-03" },
          ],
        });
      }
      return Promise.resolve({});
    });

    render(<AgencyAccountsPage />);
    await screen.findByText("Ready A");

    fireEvent.change(screen.getByLabelText("Filtru rapid"), { target: { value: "uninitialized" } });
    fireEvent.click(screen.getByLabelText("Selectează toate filtrate (2)"));

    expect(screen.getByText(/Selectate:/)).toHaveTextContent("Selectate: 2 conturi");
    expect(screen.getByText("No Start A")).toBeInTheDocument();
    expect(screen.getByText("No Start B")).toBeInTheDocument();
    expect(screen.queryByText("Ready A")).not.toBeInTheDocument();
  });

  it("active first sorts active rows before error and idle", async () => {
    apiMock.apiRequest.mockImplementation((path: string) => {
      if (path === "/clients") {
        return Promise.resolve({
          items: [
            { id: 11, name: "Client A", owner_email: "a@x.com", display_id: 1 },
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
            { id: "1002", name: "Account Two", attached_client_id: 11, attached_client_name: "Client A", last_run_status: "error", sync_start_date: "2025-12-01" },
            { id: "1003", name: "Account Three", attached_client_id: 11, attached_client_name: "Client A", last_run_status: "idle" },
            { id: "1001", name: "Account One", attached_client_id: 11, attached_client_name: "Client A", last_run_status: "running", has_active_sync: true, sync_start_date: "2025-12-01" },
          ],
        });
      }
      return Promise.resolve({});
    });

    render(<AgencyAccountsPage />);
    await screen.findByText("Account One");

    fireEvent.click(screen.getByRole("checkbox", { name: /Active first/i }));

    const links = screen.getAllByRole("link");
    const names = links
      .map((node) => node.textContent || "")
      .filter((name) => name === "Account One" || name === "Account Two" || name === "Account Three");

    expect(names.slice(0, 3)).toEqual(["Account One", "Account Two", "Account Three"]);
  });

  it("shows rolling in-progress window for active rolling_refresh and not 'neinițiat'", async () => {
    apiMock.postAccountSyncProgressBatch.mockImplementation((platform: string, accountIds: string[]) => {
      if (platform === "google_ads" && accountIds.includes("1001")) {
        return Promise.resolve({
          platform: "google_ads",
          requested_count: accountIds.length,
          results: [
            {
              account_id: "1001",
              active_run: {
                job_id: "rolling-1",
                status: "running",
                job_type: "rolling_refresh",
                chunks_done: 4,
                chunks_total: 10,
                date_start: "2026-01-10",
                date_end: "2026-01-14",
              },
            },
          ],
        });
      }
      return Promise.resolve({ platform: "google_ads", requested_count: accountIds.length, results: [] });
    });

    render(<AgencyAccountsPage />);
    await screen.findByText("Account One");

    await waitFor(() => {
      expect(screen.getByText("Rolling până la: Rolling în curs: 2026-01-10 → 2026-01-14")).toBeInTheDocument();
    });
  });

  it("keeps 'Rolling sync neinițiat' when no active rolling run and no synced-through date", async () => {
    render(<AgencyAccountsPage />);
    await screen.findByText("Account Three");
    expect(screen.getAllByText("Rolling până la: Rolling sync neinițiat").length).toBeGreaterThan(0);
  });

  it("shows rolling synced-through date for done rows", async () => {
    render(<AgencyAccountsPage />);
    await screen.findByText("Account Two");
    expect(screen.getByText("Rolling până la: 2026-01-14")).toBeInTheDocument();
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

    apiMock.postAccountSyncProgressBatch.mockResolvedValue({
      platform: "google_ads",
      requested_count: 2,
      results: [
        { account_id: "1001", active_run: { job_id: "run-1", status: "running", chunks_done: 12, chunks_total: 113 } },
        { account_id: "1002", active_run: { job_id: "run-2", status: "queued", chunks_done: 3, chunks_total: 20 } },
      ],
    });

    render(<AgencyAccountsPage />);
    await screen.findByText("Account One");

    fireEvent.click(screen.getByLabelText("Select all pe pagina curentă"));
    fireEvent.click(screen.getByRole("button", { name: /Download/i }));

    await waitFor(() => {
      expect(screen.getByTestId("sync-progress-fill-1001")).toBeInTheDocument();
      expect(screen.getByTestId("sync-progress-fill-1002")).toBeInTheDocument();
      expect(screen.getByTestId("sync-progress-chunks-1001")).toHaveTextContent("12/113 chunks (11%)");
      expect(screen.getByTestId("sync-progress-chunks-1002")).toHaveTextContent("3/20 chunks (15%)");
    });
    expect(apiMock.postAccountSyncProgressBatch).toHaveBeenCalledTimes(1);
    expect(apiMock.postAccountSyncProgressBatch).toHaveBeenCalledWith("google_ads", ["1001", "1002"], true);
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

    apiMock.postAccountSyncProgressBatch.mockResolvedValue({
      platform: "google_ads",
      requested_count: 1,
      results: [{ account_id: "1001", active_run: { job_id: "run-1", status: "running", chunks_done: 1, chunks_total: 10 } }],
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
    fireEvent.click(screen.getByRole("button", { name: /Download/i }));

    await waitFor(() => {
      expect(apiMock.postAccountSyncProgressBatch).toHaveBeenCalledWith("google_ads", ["1001"], true);
    });
    expect(apiMock.postAccountSyncProgressBatch).not.toHaveBeenCalledWith("google_ads", ["1002"], true);

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

  it("splits active account ids in batches of 200 for progress polling", async () => {
    apiMock.apiRequest.mockImplementation((path: string) => {
      if (path === "/clients") {
        return Promise.resolve({ items: [{ id: 11, name: "Client A", owner_email: "a@x.com", display_id: 1 }] });
      }
      if (path === "/clients/accounts/summary") {
        return Promise.resolve({ items: [{ platform: "google_ads", connected_count: 205, last_import_at: null }] });
      }
      if (path === "/clients/accounts/google") {
        return Promise.resolve({
          count: 205,
          items: Array.from({ length: 205 }).map((_, index) => ({
            id: `acc-${index + 1}`,
            name: `Account ${index + 1}`,
            attached_client_id: 11,
            attached_client_name: "Client A",
            has_active_sync: true,
            last_run_status: "running",
          })),
        });
      }
      return Promise.resolve({});
    });

    apiMock.postAccountSyncProgressBatch.mockImplementation((_platform: string, accountIds: string[]) =>
      Promise.resolve({
        platform: "google_ads",
        requested_count: accountIds.length,
        results: accountIds.map((accountId) => ({
          account_id: accountId,
          active_run: { job_id: `job-${accountId}`, status: "running", chunks_done: 1, chunks_total: 10 },
        })),
      }),
    );

    render(<AgencyAccountsPage />);
    await screen.findByText("Account 1");

    await waitFor(() => {
      expect(apiMock.postAccountSyncProgressBatch).toHaveBeenCalledTimes(2);
    });
    expect(apiMock.postAccountSyncProgressBatch.mock.calls[0][1]).toHaveLength(200);
    expect(apiMock.postAccountSyncProgressBatch.mock.calls[1][1]).toHaveLength(5);
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

  it("keeps done status when last_success_at exists and active/batch status is absent", async () => {
    apiMock.apiRequest.mockImplementation((path: string) => {
      if (path === "/clients") return Promise.resolve({ items: [{ id: 11, name: "Client A", owner_email: "a@x.com", display_id: 1 }] });
      if (path === "/clients/accounts/summary") return Promise.resolve({ items: [{ platform: "google_ads", connected_count: 1, last_import_at: null }] });
      if (path === "/clients/accounts/google") {
        return Promise.resolve({
          count: 1,
          items: [
            {
              id: "1001",
              name: "Account One",
              attached_client_id: 11,
              attached_client_name: "Client A",
              last_run_status: null,
              has_active_sync: false,
              last_success_at: "2026-03-09T10:00:00Z",
            },
          ],
        });
      }
      return Promise.resolve({});
    });

    render(<AgencyAccountsPage />);

    expect(await screen.findByText(/Status: done/i)).toBeInTheDocument();
    expect(screen.queryByText(/Status: idle/i)).not.toBeInTheDocument();
  });

});
