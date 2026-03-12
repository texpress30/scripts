import React from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";

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
});
