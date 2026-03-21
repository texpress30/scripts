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
});
