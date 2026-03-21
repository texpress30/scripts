import React from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";

import SubTikTokAdsCampaignAdGroupsPage from "./page";

const apiMock = vi.hoisted(() => ({ getSubTikTokAdsCampaignAdGroupsTable: vi.fn() }));

vi.mock("@/lib/api", () => ({ getSubTikTokAdsCampaignAdGroupsTable: apiMock.getSubTikTokAdsCampaignAdGroupsTable }));
vi.mock("next/navigation", () => ({ useParams: () => ({ id: "96", accountId: "tt-1", campaignId: "cmp-tt-1" }) }));
vi.mock("@/components/ProtectedPage", () => ({ ProtectedPage: ({ children }: { children: React.ReactNode }) => <>{children}</> }));
vi.mock("@/components/AppShell", () => ({ AppShell: ({ children }: { children: React.ReactNode }) => <>{children}</> }));

describe("TikTok campaign ad groups drilldown", () => {
  beforeEach(() => {
    apiMock.getSubTikTokAdsCampaignAdGroupsTable.mockReset();
    apiMock.getSubTikTokAdsCampaignAdGroupsTable.mockResolvedValue({
      client_id: 96,
      platform: "tiktok_ads",
      account_id: "tt-1",
      account_name: "TikTok Main",
      account_status: "active",
      campaign_id: "cmp-tt-1",
      campaign_name: "TikTok Prospecting",
      currency: "USD",
      date_range: { start_date: "2026-03-01", end_date: "2026-03-31" },
      items: [],
    });
  });

  it("renders empty state and back link", async () => {
    render(<SubTikTokAdsCampaignAdGroupsPage />);

    expect(await screen.findByRole("heading", { name: "TikTok Ads Ad groups - TikTok Prospecting" })).toBeInTheDocument();
    expect(screen.getByText("Nu există ad groups în perioada selectată.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Back to campaigns/i })).toHaveAttribute("href", "/sub/96/tiktok-ads/accounts/tt-1");
  });

  it("renders ad_group_name when backend returns rows", async () => {
    apiMock.getSubTikTokAdsCampaignAdGroupsTable.mockResolvedValueOnce({
      client_id: 96,
      platform: "tiktok_ads",
      account_id: "tt-1",
      account_name: "TikTok Main",
      account_status: "active",
      campaign_id: "cmp-tt-1",
      campaign_name: "TikTok Prospecting",
      currency: "USD",
      date_range: { start_date: "2026-03-01", end_date: "2026-03-31" },
      items: [{ ad_group_id: "ag-1", ad_group_name: "Winners AG", status: "active", cost: null, rev_inf: null, roas_inf: null, mer_inf: null, truecac_inf: null, ecr_inf: null, ecpnv_inf: null, new_visits: null, visits: null }],
    });

    render(<SubTikTokAdsCampaignAdGroupsPage />);
    expect(await screen.findByText("Winners AG")).toBeInTheDocument();
    expect(screen.queryByText("Nu există ad groups în perioada selectată.")).not.toBeInTheDocument();
  });

  it("falls back to ad_group_id only when ad_group_name missing", async () => {
    apiMock.getSubTikTokAdsCampaignAdGroupsTable.mockResolvedValueOnce({
      client_id: 96,
      platform: "tiktok_ads",
      account_id: "tt-1",
      account_name: "TikTok Main",
      account_status: "active",
      campaign_id: "cmp-tt-1",
      campaign_name: "TikTok Prospecting",
      currency: "USD",
      date_range: { start_date: "2026-03-01", end_date: "2026-03-31" },
      items: [{ ad_group_id: "ag-fallback", ad_group_name: "", status: "active", cost: null, rev_inf: null, roas_inf: null, mer_inf: null, truecac_inf: null, ecr_inf: null, ecpnv_inf: null, new_visits: null, visits: null }],
    });

    render(<SubTikTokAdsCampaignAdGroupsPage />);
    expect(await screen.findByText("ag-fallback")).toBeInTheDocument();
  });
});
