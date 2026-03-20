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
      currency: "RON",
      date_range: { start_date: "2026-03-01", end_date: "2026-03-31" },
      items: [],
    });
  });

  it("renders controls and empty state", async () => {
    render(<SubTikTokAdsAccountCampaignsPage />);

    expect(await screen.findByRole("heading", { name: "TikTok Ads Campaigns - TikTok Main" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Filter/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Columns/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Export/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Last 30 days/i })).toBeInTheDocument();
    expect(screen.getByText("Nu există campanii în perioada selectată.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Back to accounts/i })).toHaveAttribute("href", "/sub/96/tiktok-ads");
  });
});
