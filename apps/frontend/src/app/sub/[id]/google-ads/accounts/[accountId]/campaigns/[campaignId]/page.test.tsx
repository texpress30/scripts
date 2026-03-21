import React from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import SubGoogleAdsCampaignAdGroupsPage from "./page";

const apiMock = vi.hoisted(() => ({ getSubGoogleAdsCampaignAdGroupsTable: vi.fn() }));

vi.mock("@/lib/api", () => ({ getSubGoogleAdsCampaignAdGroupsTable: apiMock.getSubGoogleAdsCampaignAdGroupsTable }));
vi.mock("next/navigation", () => ({ useParams: () => ({ id: "96", accountId: "123-111-0001", campaignId: "cmp-1" }) }));
vi.mock("@/components/ProtectedPage", () => ({ ProtectedPage: ({ children }: { children: React.ReactNode }) => <>{children}</> }));
vi.mock("@/components/AppShell", () => ({ AppShell: ({ children }: { children: React.ReactNode }) => <>{children}</> }));

describe("Google campaign ad groups drilldown", () => {
  beforeEach(() => {
    apiMock.getSubGoogleAdsCampaignAdGroupsTable.mockReset();
    window.localStorage.clear();
    apiMock.getSubGoogleAdsCampaignAdGroupsTable.mockResolvedValue({
      client_id: 96,
      platform: "google_ads",
      account_id: "123-111-0001",
      account_name: "Google Main RO",
      account_status: "active",
      campaign_id: "cmp-1",
      campaign_name: "Search RO",
      currency: "RON",
      date_range: { start_date: "2026-03-01", end_date: "2026-03-31" },
      items: [{ ad_group_id: "ag-1", ad_group_name: "Brand AG", status: "paused", cost: null, rev_inf: null, roas_inf: null, mer_inf: null, truecac_inf: null, ecr_inf: null, ecpnv_inf: null, new_visits: null, visits: null }],
    });
  });

  it("renders controls, campaign title and ad group row", async () => {
    render(<SubGoogleAdsCampaignAdGroupsPage />);

    expect(await screen.findByRole("heading", { name: "Google Ads Ad groups - Search RO" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Filter/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Columns/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Export/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Last 30 days/i })).toBeInTheDocument();
    expect(screen.getByText("Brand AG")).toBeInTheDocument();
    expect(screen.getByText("II")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Back to campaigns/i })).toHaveAttribute("href", "/sub/96/google-ads/accounts/123-111-0001");
  });

  it("refetches on date preset change and shows empty state", async () => {
    apiMock.getSubGoogleAdsCampaignAdGroupsTable
      .mockResolvedValueOnce({
        client_id: 96, platform: "google_ads", account_id: "123-111-0001", account_name: "Google Main RO", account_status: "active", campaign_id: "cmp-1", campaign_name: "Search RO", currency: "RON", date_range: { start_date: "2026-03-01", end_date: "2026-03-31" }, items: [],
      })
      .mockResolvedValueOnce({
        client_id: 96, platform: "google_ads", account_id: "123-111-0001", account_name: "Google Main RO", account_status: "active", campaign_id: "cmp-1", campaign_name: "Search RO", currency: "RON", date_range: { start_date: "2026-03-20", end_date: "2026-03-20" }, items: [],
      });

    render(<SubGoogleAdsCampaignAdGroupsPage />);
    expect(await screen.findByText("Nu există ad groups în perioada selectată.")).toBeInTheDocument();

    const calls = apiMock.getSubGoogleAdsCampaignAdGroupsTable.mock.calls.length;
    fireEvent.click(screen.getByRole("button", { name: /Last 30 days/i }));
    fireEvent.click(screen.getByRole("button", { name: "Today" }));
    await waitFor(() => expect(apiMock.getSubGoogleAdsCampaignAdGroupsTable.mock.calls.length).toBeGreaterThan(calls));
  });
});
