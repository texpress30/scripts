import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import React from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import AgencyAccountDetailPage from "./page";

const apiMock = vi.hoisted(() => ({
  apiRequest: vi.fn(),
  repairSyncRun: vi.fn(),
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

describe("AgencyAccountDetailPage repair action", () => {
  beforeEach(() => {
    vi.useRealTimers();
    apiMock.apiRequest.mockReset();
    apiMock.repairSyncRun.mockReset();
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
