import React from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import SubGoogleAdsAccountCampaignsPage from "./page";

const apiMock = vi.hoisted(() => ({ getSubGoogleAdsCampaignsTable: vi.fn() }));

vi.mock("@/lib/api", () => ({ getSubGoogleAdsCampaignsTable: apiMock.getSubGoogleAdsCampaignsTable }));
vi.mock("next/navigation", () => ({ useParams: () => ({ id: "96", accountId: "123-111-0001" }) }));
vi.mock("@/components/ProtectedPage", () => ({ ProtectedPage: ({ children }: { children: React.ReactNode }) => <>{children}</> }));
vi.mock("@/components/AppShell", () => ({
  AppShell: ({ children, title }: { children: React.ReactNode; title: React.ReactNode }) => (
    <div>
      <div data-testid="app-shell-title">{title === null ? "" : String(title ?? "")}</div>
      {children}
    </div>
  ),
}));

describe("Google account campaigns drilldown", () => {
  beforeEach(() => {
    apiMock.getSubGoogleAdsCampaignsTable.mockReset();
    window.localStorage.clear();
    apiMock.getSubGoogleAdsCampaignsTable.mockResolvedValue({
      client_id: 96,
      platform: "google_ads",
      account_id: "123-111-0001",
      account_name: "Google Main RO",
      currency: "RON",
      date_range: { start_date: "2026-03-01", end_date: "2026-03-31" },
      items: [
        {
          campaign_id: "cmp-1",
          campaign_name: "Search RO",
          status: "paused",
          cost: 1000,
          rev_inf: 2500,
          roas_inf: 2.5,
          mer_inf: 0.4,
          truecac_inf: null,
          ecr_inf: null,
          ecpnv_inf: null,
          new_visits: null,
          visits: null,
        },
      ],
    });
  });

  it("renders campaigns page with controls and campaign rows", async () => {
    render(<SubGoogleAdsAccountCampaignsPage />);

    expect(await screen.findByRole("heading", { name: "Google Ads Campaigns - Google Main RO" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Filter/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Columns/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Export/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Last 30 days/i })).toBeInTheDocument();
    expect(screen.getByText("Search RO")).toBeInTheDocument();
    expect(screen.getByText("II")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Back to accounts/i })).toHaveAttribute("href", "/sub/96/google-ads");
  });

  it("refetches when date preset changes and supports empty state", async () => {
    apiMock.getSubGoogleAdsCampaignsTable
      .mockResolvedValueOnce({
        client_id: 96,
        platform: "google_ads",
        account_id: "123-111-0001",
        account_name: "Google Main RO",
        currency: "RON",
        date_range: { start_date: "2026-03-01", end_date: "2026-03-31" },
        items: [],
      })
      .mockResolvedValueOnce({
        client_id: 96,
        platform: "google_ads",
        account_id: "123-111-0001",
        account_name: "Google Main RO",
        currency: "RON",
        date_range: { start_date: "2026-03-20", end_date: "2026-03-20" },
        items: [],
      });

    render(<SubGoogleAdsAccountCampaignsPage />);
    expect(await screen.findByText("Nu există campanii în perioada selectată.")).toBeInTheDocument();

    const initialCalls = apiMock.getSubGoogleAdsCampaignsTable.mock.calls.length;
    fireEvent.click(screen.getByRole("button", { name: /Last 30 days/i }));
    fireEvent.click(screen.getByRole("button", { name: "Today" }));

    await waitFor(() => expect(apiMock.getSubGoogleAdsCampaignsTable.mock.calls.length).toBeGreaterThan(initialCalls));
  });
});
