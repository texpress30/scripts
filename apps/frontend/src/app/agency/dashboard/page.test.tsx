import React from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";

import AgencyDashboardPage from "./page";

const apiMock = vi.hoisted(() => ({
  apiRequest: vi.fn(),
}));

vi.mock("@/lib/api", () => ({
  apiRequest: apiMock.apiRequest,
}));

vi.mock("@/components/ProtectedPage", () => ({ ProtectedPage: ({ children }: { children: React.ReactNode }) => <>{children}</> }));
vi.mock("@/components/AppShell", () => ({ AppShell: ({ children }: { children: React.ReactNode }) => <>{children}</> }));
vi.mock("react-day-picker", () => ({
  DayPicker: () => <div data-testid="day-picker" />,
}));

describe("AgencyDashboardPage integration health", () => {
  beforeEach(() => {
    apiMock.apiRequest.mockReset();
  });

  it("shows real Meta status as connected instead of hardcoded disabled", async () => {
    apiMock.apiRequest.mockImplementation((path: string) => {
      if (path === "/integrations/google-ads/status") {
        return Promise.resolve({
          platform: "google_ads",
          status: "connected",
          accounts_found: 3,
          rows_in_db_last_30_days: 120,
          last_sync_at: "2026-03-07T10:00:00Z",
          last_error: null,
        });
      }
      if (path === "/integrations/meta-ads/status") {
        return Promise.resolve({
          provider: "meta_ads",
          status: "connected",
          message: "Meta connected",
          token_updated_at: "2026-03-07T09:00:00Z",
          token_source: "database",
          oauth_configured: true,
          has_usable_token: true,
        });
      }
      if (path.startsWith("/dashboard/agency/summary")) {
        return Promise.resolve({
          date_range: { start_date: "2026-02-06", end_date: "2026-03-07" },
          active_clients: 2,
          totals: { spend: 100, impressions: 1000, clicks: 100, conversions: 10, revenue: 200, roas: 2 },
          top_clients: [],
          currency: "RON",
        });
      }
      return Promise.resolve({});
    });

    render(<AgencyDashboardPage />);

    const metaLabel = await screen.findByText("Meta Ads");
    const metaRow = metaLabel.closest("li");
    expect(metaRow).toBeTruthy();
    const rowScope = within(metaRow!);
    expect(rowScope.getByText("connected")).toBeInTheDocument();
    expect(rowScope.queryByText("disabled")).not.toBeInTheDocument();
    expect(rowScope.getByText("Meta connected")).toBeInTheDocument();
  });
});
