import React from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";

import SubMetaAdsAccountCampaignsPage from "./page";

const apiMock = vi.hoisted(() => ({ getSubMetaAdsCampaignsTable: vi.fn() }));

vi.mock("@/lib/api", () => ({ getSubMetaAdsCampaignsTable: apiMock.getSubMetaAdsCampaignsTable }));
vi.mock("next/navigation", () => ({ useParams: () => ({ id: "96", accountId: "meta-1" }) }));
vi.mock("@/components/ProtectedPage", () => ({ ProtectedPage: ({ children }: { children: React.ReactNode }) => <>{children}</> }));
vi.mock("@/components/AppShell", () => ({ AppShell: ({ children }: { children: React.ReactNode }) => <>{children}</> }));

describe("Meta account campaigns drilldown", () => {
  beforeEach(() => {
    apiMock.getSubMetaAdsCampaignsTable.mockReset();
    apiMock.getSubMetaAdsCampaignsTable.mockResolvedValue({
      client_id: 96,
      platform: "meta_ads",
      account_id: "meta-1",
      account_name: "Meta Main",
      account_status: "active",
      currency: "RON",
      date_range: { start_date: "2026-03-01", end_date: "2026-03-31" },
      items: [],
    });
  });

  it("renders controls and empty state", async () => {
    render(<SubMetaAdsAccountCampaignsPage />);

    expect(await screen.findByRole("heading", { name: "Meta Ads Campaigns - Meta Main" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Filter/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Columns/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Export/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Last 30 days/i })).toBeInTheDocument();
    const dot = screen.getByText("Account status").parentElement?.querySelector("span[aria-hidden='true']");
    expect(dot?.className).toContain("bg-emerald-500");
    expect(screen.getByText("Nu există campanii în perioada selectată.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Back to accounts/i })).toHaveAttribute("href", "/sub/96/meta-ads");
  });

  it("renders campaign name as link to campaign drilldown", async () => {
    apiMock.getSubMetaAdsCampaignsTable.mockResolvedValueOnce({
      client_id: 96,
      platform: "meta_ads",
      account_id: "meta-1",
      account_name: "Meta Main",
      account_status: "active",
      currency: "RON",
      date_range: { start_date: "2026-03-01", end_date: "2026-03-31" },
      items: [{
        campaign_id: "meta-cmp-1",
        campaign_name: "Meta Prospecting",
        status: "active",
        cost: null, rev_inf: null, roas_inf: null, mer_inf: null, truecac_inf: null, ecr_inf: null, ecpnv_inf: null, new_visits: null, visits: null,
      }],
    });

    render(<SubMetaAdsAccountCampaignsPage />);
    expect(await screen.findByRole("link", { name: "Meta Prospecting" })).toHaveAttribute(
      "href",
      "/sub/96/meta-ads/accounts/meta-1/campaigns/meta-cmp-1",
    );
  });
});
