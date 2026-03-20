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
    expect(screen.getByText("Nu există campanii în perioada selectată.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Back to accounts/i })).toHaveAttribute("href", "/sub/96/meta-ads");
  });
});
