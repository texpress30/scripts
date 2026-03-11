import React from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";

import SubGoogleAdsPage from "./google-ads/page";
import SubMediaTrackerPage from "./media-tracker/page";
import SubMetaAdsPage from "./meta-ads/page";
import SubPinterestAdsPage from "./pinterest-ads/page";
import SubSnapchatAdsPage from "./snapchat-ads/page";
import SubTikTokAdsPage from "./tiktok-ads/page";

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

describe("Sub routes placeholder pages", () => {
  beforeEach(() => {
    apiMock.apiRequest.mockReset();
    apiMock.apiRequest.mockResolvedValue({ items: [{ id: 96, name: "Active Life Therapy" }] });
  });

  it.each([
    ["Media Tracker - Active Life Therapy", SubMediaTrackerPage],
    ["Google Ads - Active Life Therapy", SubGoogleAdsPage],
    ["Meta Ads - Active Life Therapy", SubMetaAdsPage],
    ["TikTok Ads - Active Life Therapy", SubTikTokAdsPage],
    ["Pinterest Ads - Active Life Therapy", SubPinterestAdsPage],
    ["Snapchat Ads - Active Life Therapy", SubSnapchatAdsPage],
  ])("renders %s", async (expectedTitle, Component) => {
    render(<Component />);

    expect(screen.getByTestId("app-shell-title").textContent).toBe("");
    expect(await screen.findByRole("heading", { name: expectedTitle })).toBeInTheDocument();
    expect(screen.getByText("Coming Soon")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Media Buying" })).toHaveAttribute("href", "/sub/96/media-buying");
    expect(screen.getByRole("link", { name: "Media Tracker" })).toHaveAttribute("href", "/sub/96/media-tracker");
  });
});
