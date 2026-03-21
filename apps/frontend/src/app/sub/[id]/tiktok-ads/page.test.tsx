import React from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import SubTikTokAdsPage from "./page";

const apiMock = vi.hoisted(() => ({ apiRequest: vi.fn(), getSubTikTokAdsTable: vi.fn() }));

vi.mock("@/lib/api", () => ({
  apiRequest: apiMock.apiRequest,
  getSubTikTokAdsTable: apiMock.getSubTikTokAdsTable,
}));
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

describe("Sub TikTok Ads details table", () => {
  beforeEach(() => {
    apiMock.apiRequest.mockReset();
    apiMock.getSubTikTokAdsTable.mockReset();
    window.localStorage.clear();

    apiMock.apiRequest.mockImplementation((path: string) => {
      if (path === "/clients") return Promise.resolve({ items: [{ id: 96, name: "Active Life Therapy" }] });
      return Promise.reject(new Error(`Unexpected path: ${path}`));
    });

    apiMock.getSubTikTokAdsTable.mockResolvedValue({
      client_id: 96,
      currency: "RON",
      date_range: { start_date: "2026-03-01", end_date: "2026-03-31" },
      items: [
        {
          account_id: "tiktok-1",
          account_name: "TikTok Main",
          status: "active",
          cost: 1200,
          rev_inf: 2200,
          roas_inf: 1.83,
          mer_inf: 0.54,
          truecac_inf: null,
          ecr_inf: null,
          ecpnv_inf: null,
          new_visits: null,
          visits: null,
        },
      ],
    });
  });

  it("replaces Coming Soon and renders TikTok multi-account table", async () => {
    render(<SubTikTokAdsPage />);

    expect(screen.queryByText("Coming Soon")).not.toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "TikTok Ads - Active Life Therapy" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Filter/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Columns/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Export/i })).toBeInTheDocument();
    const link = screen.getByRole("link", { name: "TikTok Main" });
    expect(link).toHaveAttribute("href", "/sub/96/tiktok-ads/accounts/tiktok-1");
    const row = link.closest("tr");
    const dot = row?.querySelector("span[aria-hidden='true']");
    expect(dot?.className).toContain("bg-emerald-500");
  });

  it("refetches payload when choosing Today preset", async () => {
    render(<SubTikTokAdsPage />);
    await screen.findByText("TikTok Main");

    const initialCalls = apiMock.getSubTikTokAdsTable.mock.calls.length;
    fireEvent.click(screen.getByRole("button", { name: /Last 30 days/i }));
    fireEvent.click(screen.getByRole("button", { name: "Today" }));

    await waitFor(() => expect(apiMock.getSubTikTokAdsTable.mock.calls.length).toBeGreaterThan(initialCalls));
    const lastCall = apiMock.getSubTikTokAdsTable.mock.calls.at(-1);
    expect(lastCall?.[0]).toBe(96);
    expect(lastCall?.[1]?.start_date).toBe(lastCall?.[1]?.end_date);
  });
});
