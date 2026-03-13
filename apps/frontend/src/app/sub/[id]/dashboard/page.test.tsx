import React from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";

import SubDashboardPage from "./page";

const apiMock = vi.hoisted(() => ({ apiRequest: vi.fn() }));

vi.mock("@/lib/api", () => ({ apiRequest: apiMock.apiRequest }));
vi.mock("next/navigation", () => ({ useParams: () => ({ id: "96" }) }));
vi.mock("@/components/ProtectedPage", () => ({ ProtectedPage: ({ children }: { children: React.ReactNode }) => <>{children}</> }));
vi.mock("@/components/AppShell", () => ({
  AppShell: ({ children, title }: { children: React.ReactNode; title: React.ReactNode }) => (
    <div>
      <div data-testid="app-shell-title">{title === null ? "" : String(title ?? "")}</div>
      {children}
    </div>
  ),
}));

vi.mock("@/components/ui/card", () => ({
  Card: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  CardHeader: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  CardTitle: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  CardContent: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}));

describe("SubDashboardPage header and platform links", () => {
  beforeEach(() => {
    apiMock.apiRequest.mockReset();
    apiMock.apiRequest.mockResolvedValue({
      client_id: 96,
      currency: "RON",
      totals: { spend: 10, impressions: 100, clicks: 10, conversions: 1, revenue: 20, roas: 2 },
      platforms: {
        google_ads: { spend: 1, impressions: 10, clicks: 1, conversions: 1, revenue: 2 },
        meta_ads: { spend: 2, impressions: 20, clicks: 2, conversions: 1, revenue: 3 },
        tiktok_ads: { spend: 3, impressions: 30, clicks: 3, conversions: 1, revenue: 4 },
        pinterest_ads: { spend: 4, impressions: 40, clicks: 4, conversions: 1, revenue: 5 },
        snapchat_ads: { spend: 5, impressions: 50, clicks: 5, conversions: 1, revenue: 6 },
      },
      platform_sync_summary: {
        meta_ads: {
          accounts: [
            { id: "act_1", name: "Meta One", coverage_status: "failed_request_coverage", last_error_summary: "chunk failed", failed_chunk_count: 2 },
            { id: "act_2", name: "Meta Two", coverage_status: "full_request_coverage" },
          ],
        },
        tiktok_ads: {
          accounts: [
            { id: "tt_1", name: "TikTok One", last_error_summary: "partial data" },
            { id: "tt_2", name: "TikTok Two", coverage_status: "full_request_coverage" },
          ],
        },
      },
    });
  });

  it("removes old header title/nav and adds Media Buying + Media Tracker", async () => {
    render(<SubDashboardPage />);

    expect(screen.getByTestId("app-shell-title").textContent).toBe("");
    expect(await screen.findByRole("link", { name: "Media Buying" })).toHaveAttribute("href", "/sub/96/media-buying");
    expect(screen.getByRole("link", { name: "Media Tracker" })).toHaveAttribute("href", "/sub/96/media-tracker");

    expect(screen.queryByRole("link", { name: "Campaigns" })).toBeNull();
    expect(screen.queryByRole("link", { name: "Rules" })).toBeNull();
    expect(screen.queryByRole("link", { name: "Creative" })).toBeNull();
    expect(screen.queryByRole("link", { name: "Recommendations" })).toBeNull();
  });

  it("renders platform names as links to dedicated sub routes", async () => {
    render(<SubDashboardPage />);

    expect(await screen.findByRole("link", { name: "Google Ads" })).toHaveAttribute("href", "/sub/96/google-ads");
    expect(screen.getByRole("link", { name: "Meta Ads" })).toHaveAttribute("href", "/sub/96/meta-ads");
    expect(screen.getByRole("link", { name: "TikTok Ads" })).toHaveAttribute("href", "/sub/96/tiktok-ads");
    expect(screen.getByRole("link", { name: "Pinterest Ads" })).toHaveAttribute("href", "/sub/96/pinterest-ads");
    expect(screen.getByRole("link", { name: "Snapchat Ads" })).toHaveAttribute("href", "/sub/96/snapchat-ads");
  });

  it("shows sync warning banner, platform chips, and concise account details", async () => {
    render(<SubDashboardPage />);

    expect(await screen.findByText("Some platform totals may be incomplete due to sync issues.")).toBeInTheDocument();
    expect(screen.getByText("2 platform warnings • 2 affected accounts")).toBeInTheDocument();

    expect(screen.getByRole("button", { name: /Error \(1\)/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Warning \(1\)/ })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /Some platform totals may be incomplete due to sync issues\./ }));

    expect(screen.getByText("Meta One (act_1)")).toBeInTheDocument();
    expect(screen.getByText("TikTok One (tt_1)")).toBeInTheDocument();
    expect(screen.getByText(/Sync failed coverage/)).toBeInTheDocument();
  });

  it("does not show sync warning banner when all statuses are healthy", async () => {
    apiMock.apiRequest.mockResolvedValueOnce({
      client_id: 96,
      currency: "RON",
      totals: { spend: 10, impressions: 100, clicks: 10, conversions: 1, revenue: 20, roas: 2 },
      platforms: {
        google_ads: { spend: 1, impressions: 10, clicks: 1, conversions: 1, revenue: 2 },
        meta_ads: { spend: 2, impressions: 20, clicks: 2, conversions: 1, revenue: 3 },
        tiktok_ads: { spend: 3, impressions: 30, clicks: 3, conversions: 1, revenue: 4 },
        pinterest_ads: { spend: 4, impressions: 40, clicks: 4, conversions: 1, revenue: 5 },
        snapchat_ads: { spend: 5, impressions: 50, clicks: 5, conversions: 1, revenue: 6 },
      },
      platform_sync_summary: {
        meta_ads: { accounts: [{ id: "act_1", name: "Meta One", coverage_status: "full_request_coverage" }] },
        tiktok_ads: { accounts: [{ id: "tt_1", name: "TikTok One", coverage_status: "full_request_coverage" }] },
      },
    });

    render(<SubDashboardPage />);

    await screen.findByRole("link", { name: "Meta Ads" });
    expect(screen.queryByText("Some platform totals may be incomplete due to sync issues.")).toBeNull();
  });
});
