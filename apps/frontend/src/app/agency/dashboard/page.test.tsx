import React from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";

import AgencyDashboardPage from "./page";

const apiMock = vi.hoisted(() => ({
  apiRequest: vi.fn(),
}));

vi.mock("@/lib/api", () => ({
  apiRequest: apiMock.apiRequest,
}));
vi.mock("@/components/ProtectedPage", () => ({ ProtectedPage: ({ children }: { children: React.ReactNode }) => <>{children}</> }));
vi.mock("@/components/AppShell", () => ({ AppShell: ({ children }: { children: React.ReactNode }) => <>{children}</> }));

describe("AgencyDashboardPage integration health from summary", () => {
  beforeEach(() => {
    apiMock.apiRequest.mockReset();
  });

  it("renders integration health exclusively from summary.integration_health", async () => {
    apiMock.apiRequest.mockImplementation((path: string) => {
      if (path.startsWith("/dashboard/agency/summary")) {
        return Promise.resolve({
          date_range: { start_date: "2026-03-01", end_date: "2026-03-07" },
          active_clients: 3,
          totals: { spend: 1200, impressions: 12000, clicks: 550, conversions: 90, revenue: 3600, roas: 3 },
          top_clients: [{ client_id: 11, name: "Client Alpha", spend: 500, currency: "RON" }],
          currency: "RON",
          integration_health: [
            { platform: "google_ads", label: "Google Ads", status: "connected", details: "accounts=4 · rows30=321", last_sync_at: "2026-03-08T10:00:00Z", last_error: null },
            { platform: "meta_ads", label: "Meta Ads", status: "connected", details: "Meta connected", last_sync_at: "2026-03-08T09:00:00Z", last_error: null },
            { platform: "tiktok_ads", label: "TikTok Ads", status: "disabled", details: null, last_sync_at: null, last_error: null },
            { platform: "pinterest_ads", label: "Pinterest Ads", status: "disabled", details: null, last_sync_at: null, last_error: null },
            { platform: "snapchat_ads", label: "Snapchat Ads", status: "disabled", details: null, last_sync_at: null, last_error: null },
          ],
        });
      }
      throw new Error(`Unexpected path: ${path}`);
    });

    render(<AgencyDashboardPage />);

    expect(await screen.findByText("Google Ads")).toBeInTheDocument();
    expect(screen.getByText("accounts=4 · rows30=321")).toBeInTheDocument();
    expect(screen.getByText("Meta Ads")).toBeInTheDocument();
    expect(screen.getByText("Meta connected")).toBeInTheDocument();
    expect(screen.getByText("TikTok Ads")).toBeInTheDocument();
    expect(screen.getByText("Pinterest Ads")).toBeInTheDocument();
    expect(screen.getByText("Snapchat Ads")).toBeInTheDocument();

    const calledPaths = apiMock.apiRequest.mock.calls.map((call: unknown[]) => String(call[0]));
    expect(calledPaths.some((path) => path.includes("/integrations/google-ads/status"))).toBe(false);
    expect(calledPaths.some((path) => path.includes("/integrations/meta-ads/status"))).toBe(false);
    expect(calledPaths.filter((path) => path.startsWith("/dashboard/agency/summary")).length).toBeGreaterThan(0);
  });

  it("shows fallback when integration_health is missing", async () => {
    apiMock.apiRequest.mockResolvedValue({
      date_range: { start_date: "2026-03-01", end_date: "2026-03-07" },
      active_clients: 0,
      totals: { spend: 0, impressions: 0, clicks: 0, conversions: 0, revenue: 0, roas: 0 },
      top_clients: [],
      currency: "RON",
    });

    render(<AgencyDashboardPage />);

    await waitFor(() => {
      expect(screen.getByText("Date indisponibile pentru integration health.")).toBeInTheDocument();
    });
  });
});
