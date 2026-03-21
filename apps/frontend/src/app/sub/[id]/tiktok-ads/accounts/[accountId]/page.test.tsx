import React from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";

import SubTikTokAdsAccountCampaignsPage from "./page";

const apiMock = vi.hoisted(() => ({ getSubTikTokAdsCampaignsTable: vi.fn() }));

vi.mock("@/lib/api", () => ({ getSubTikTokAdsCampaignsTable: apiMock.getSubTikTokAdsCampaignsTable }));
vi.mock("next/navigation", () => ({ useParams: () => ({ id: "96", accountId: "tiktok-1" }) }));
vi.mock("@/components/ProtectedPage", () => ({ ProtectedPage: ({ children }: { children: React.ReactNode }) => <>{children}</> }));
vi.mock("@/components/AppShell", () => ({ AppShell: ({ children }: { children: React.ReactNode }) => <>{children}</> }));

describe("TikTok account campaigns drilldown", () => {
  beforeEach(() => {
    apiMock.getSubTikTokAdsCampaignsTable.mockReset();
    apiMock.getSubTikTokAdsCampaignsTable.mockResolvedValue({
      client_id: 96,
      platform: "tiktok_ads",
      account_id: "tiktok-1",
      account_name: "TikTok Main",
      account_status: "active",
      currency: "RON",
      date_range: { start_date: "2026-03-01", end_date: "2026-03-31" },
      items: [{
        campaign_id: "tt-cmp-1",
        campaign_name: "TikTok Prospecting",
        status: "active",
        cost: null,
        rev_inf: null,
        roas_inf: null,
        mer_inf: null,
        truecac_inf: null,
        ecr_inf: null,
        ecpnv_inf: null,
        new_visits: null,
        visits: null,
      }],
    });
  });

  it("renders controls and empty state", async () => {
    render(<SubTikTokAdsAccountCampaignsPage />);

    expect(await screen.findByRole("heading", { name: "TikTok Ads Campaigns - TikTok Main" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Filter/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Columns/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Export/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Last 30 days/i })).toBeInTheDocument();
    expect(screen.getByText("TikTok Prospecting")).toBeInTheDocument();
    const row = screen.getByText("TikTok Prospecting").closest("tr");
    const dot = row?.querySelector("span[aria-hidden='true']");
    expect(dot?.className).toContain("bg-emerald-500");
    expect(screen.queryByText("Nu există campanii în perioada selectată.")).not.toBeInTheDocument();
    expect(screen.queryByText("II")).not.toBeInTheDocument();
    expect(screen.queryByText("tt-cmp-1")).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Back to accounts/i })).toHaveAttribute("href", "/sub/96/tiktok-ads");
  });

  it("falls back to campaign_id only when campaign_name is missing", async () => {
    apiMock.getSubTikTokAdsCampaignsTable.mockResolvedValueOnce({
      client_id: 96,
      platform: "tiktok_ads",
      account_id: "tiktok-1",
      account_name: "TikTok Main",
      account_status: "active",
      currency: "RON",
      date_range: { start_date: "2026-03-01", end_date: "2026-03-31" },
      items: [{
        campaign_id: "tt-cmp-fallback",
        campaign_name: "",
        status: "active",
        cost: null,
        rev_inf: null,
        roas_inf: null,
        mer_inf: null,
        truecac_inf: null,
        ecr_inf: null,
        ecpnv_inf: null,
        new_visits: null,
        visits: null,
      }],
    });

    render(<SubTikTokAdsAccountCampaignsPage />);

    expect(await screen.findByText("tt-cmp-fallback")).toBeInTheDocument();
  });
});
