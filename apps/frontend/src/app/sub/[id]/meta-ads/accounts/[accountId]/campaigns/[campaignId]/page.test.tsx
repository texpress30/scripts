import React from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";

import SubMetaAdsCampaignAdSetsPage from "./page";

const apiMock = vi.hoisted(() => ({ getSubMetaAdsCampaignAdGroupsTable: vi.fn() }));

vi.mock("@/lib/api", () => ({ getSubMetaAdsCampaignAdGroupsTable: apiMock.getSubMetaAdsCampaignAdGroupsTable }));
vi.mock("next/navigation", () => ({ useParams: () => ({ id: "96", accountId: "act_123", campaignId: "cmp-meta-1" }) }));
vi.mock("@/components/ProtectedPage", () => ({ ProtectedPage: ({ children }: { children: React.ReactNode }) => <>{children}</> }));
vi.mock("@/components/AppShell", () => ({ AppShell: ({ children }: { children: React.ReactNode }) => <>{children}</> }));

describe("Meta campaign ad sets drilldown", () => {
  beforeEach(() => {
    apiMock.getSubMetaAdsCampaignAdGroupsTable.mockReset();
    apiMock.getSubMetaAdsCampaignAdGroupsTable.mockResolvedValue({
      client_id: 96,
      platform: "meta_ads",
      account_id: "act_123",
      account_name: "Meta Main",
      account_status: "active",
      campaign_id: "cmp-meta-1",
      campaign_name: "Meta Prospecting",
      currency: "RON",
      date_range: { start_date: "2026-03-01", end_date: "2026-03-31" },
      items: [{ ad_group_id: "adset-1", ad_group_name: "Adset One", status: "active", cost: null, rev_inf: null, roas_inf: null, mer_inf: null, truecac_inf: null, ecr_inf: null, ecpnv_inf: null, new_visits: null, visits: null }],
    });
  });

  it("renders Meta ad sets page with controls and labels", async () => {
    render(<SubMetaAdsCampaignAdSetsPage />);

    expect(await screen.findByRole("heading", { name: "Meta Ads Ad sets - Meta Prospecting" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Filter/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Columns/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Export/i })).toBeInTheDocument();
    expect(screen.getByText("Ad set")).toBeInTheDocument();
    expect(screen.getByText("Adset One")).toBeInTheDocument();
  });

  it("falls back to ad_group_id only when ad_group_name missing", async () => {
    apiMock.getSubMetaAdsCampaignAdGroupsTable.mockResolvedValueOnce({
      client_id: 96,
      platform: "meta_ads",
      account_id: "act_123",
      account_name: "Meta Main",
      account_status: "active",
      campaign_id: "cmp-meta-1",
      campaign_name: "Meta Prospecting",
      currency: "RON",
      date_range: { start_date: "2026-03-01", end_date: "2026-03-31" },
      items: [{ ad_group_id: "adset-fallback", ad_group_name: "", status: "active", cost: null, rev_inf: null, roas_inf: null, mer_inf: null, truecac_inf: null, ecr_inf: null, ecpnv_inf: null, new_visits: null, visits: null }],
    });

    render(<SubMetaAdsCampaignAdSetsPage />);
    expect(await screen.findByText("adset-fallback")).toBeInTheDocument();
  });
});
