import React from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";

import SubDashboardPage from "./page";

const apiMock = vi.hoisted(() => ({ apiRequest: vi.fn(), getSubaccountMyAccess: vi.fn() }));
const routerMock = vi.hoisted(() => ({ replace: vi.fn() }));

vi.mock("@/lib/api", () => ({ apiRequest: apiMock.apiRequest, getSubaccountMyAccess: apiMock.getSubaccountMyAccess }));
vi.mock("next/navigation", () => ({ useParams: () => ({ id: "96" }), useRouter: () => routerMock }));
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
vi.mock("recharts", () => ({
  ResponsiveContainer: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  AreaChart: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  Area: () => null,
  LineChart: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  Line: () => null,
  CartesianGrid: () => null,
  XAxis: () => null,
  YAxis: () => null,
  Tooltip: () => null,
}));

describe("SubDashboardPage header and platform links", () => {
  beforeEach(() => {
    apiMock.apiRequest.mockReset();
    apiMock.getSubaccountMyAccess.mockReset();
    routerMock.replace.mockReset();
    apiMock.getSubaccountMyAccess.mockResolvedValue({
      subaccount_id: 96,
      role: "subaccount_user",
      module_keys: ["dashboard", "creative"],
      source_scope: "subaccount",
      access_scope: "subaccount",
      unrestricted_modules: false,
    });
    apiMock.apiRequest.mockResolvedValue({
      client_id: 96,
      currency: "RON",
      totals: { spend: 10, impressions: 100, clicks: 10, conversions: 1, revenue: 20, roas: 2 },
      spend_by_day: [
        { date: "2026-03-01", spend: 4, platform_spend: { google_ads: 1, meta_ads: 2, tiktok_ads: 1 } },
        { date: "2026-03-02", spend: 6, platform_spend: { google_ads: 2, meta_ads: 2, tiktok_ads: 2 } },
      ],
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
      spend_by_day: [
        { date: "2026-03-01", spend: 4, platform_spend: { google_ads: 1, meta_ads: 2, tiktok_ads: 1 } },
        { date: "2026-03-02", spend: 6, platform_spend: { google_ads: 2, meta_ads: 2, tiktok_ads: 2 } },
      ],
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

  it("renders both spend charts between KPI and platform table", async () => {
    render(<SubDashboardPage />);

    expect(await screen.findByText("Spend total pe zile")).toBeInTheDocument();
    expect(screen.getByText("Spend pe platforme")).toBeInTheDocument();
  });

  it("shows loading and empty states for charts", async () => {
    apiMock.apiRequest.mockResolvedValueOnce({
      client_id: 96,
      currency: "RON",
      totals: { spend: 0, impressions: 0, clicks: 0, conversions: 0, revenue: 0, roas: 0 },
      spend_by_day: [],
      platforms: {
        google_ads: { spend: 0, impressions: 0, clicks: 0, conversions: 0, revenue: 0 },
        meta_ads: { spend: 0, impressions: 0, clicks: 0, conversions: 0, revenue: 0 },
        tiktok_ads: { spend: 0, impressions: 0, clicks: 0, conversions: 0, revenue: 0 },
        pinterest_ads: { spend: 0, impressions: 0, clicks: 0, conversions: 0, revenue: 0 },
        snapchat_ads: { spend: 0, impressions: 0, clicks: 0, conversions: 0, revenue: 0 },
      },
      platform_sync_summary: { meta_ads: { accounts: [] }, tiktok_ads: { accounts: [] } },
    });

    render(<SubDashboardPage />);

    expect(screen.getAllByText("Se încarcă datele pentru grafic…").length).toBeGreaterThan(0);
    expect(await screen.findByText("Nu există spend în perioada selectată.")).toBeInTheDocument();
    expect(screen.getByText("Nu există spend pe platforme în perioada selectată.")).toBeInTheDocument();
  });

  it("reloads dashboard for selected calendar range", async () => {
    render(<SubDashboardPage />);
    await screen.findByRole("link", { name: "Google Ads" });

    fireEvent.click(screen.getByRole("button", { name: /Last 30 days/i }));
    fireEvent.click(screen.getByRole("button", { name: "Today" }));

    expect(apiMock.apiRequest).toHaveBeenLastCalledWith(expect.stringMatching(/start_date=\d{4}-\d{2}-\d{2}&end_date=\d{4}-\d{2}-\d{2}/));
    const requestPath = String(apiMock.apiRequest.mock.calls.at(-1)?.[0] ?? "");
    const params = new URLSearchParams(requestPath.split("?")[1] ?? "");
    expect(params.get("start_date")).toBe(params.get("end_date"));
  });

  it("redirects to first allowed module when dashboard permission is missing", async () => {
    apiMock.getSubaccountMyAccess.mockResolvedValueOnce({
      subaccount_id: 96,
      role: "subaccount_user",
      module_keys: ["creative"],
      source_scope: "subaccount",
      access_scope: "subaccount",
      unrestricted_modules: false,
    });

    render(<SubDashboardPage />);

    await screen.findByRole("link", { name: "Media Buying" });
    expect(routerMock.replace).toHaveBeenCalledWith("/sub/96/creative");
    expect(apiMock.apiRequest).not.toHaveBeenCalled();
  });
});
