import React from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import SubMetaAdsPage from "./page";

const apiMock = vi.hoisted(() => ({ apiRequest: vi.fn(), getSubMetaAdsTable: vi.fn() }));

vi.mock("@/lib/api", () => ({
  apiRequest: apiMock.apiRequest,
  getSubMetaAdsTable: apiMock.getSubMetaAdsTable,
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

describe("Sub Meta Ads details table", () => {
  beforeEach(() => {
    apiMock.apiRequest.mockReset();
    apiMock.getSubMetaAdsTable.mockReset();
    window.localStorage.clear();

    apiMock.apiRequest.mockImplementation((path: string) => {
      if (path === "/clients") return Promise.resolve({ items: [{ id: 96, name: "Active Life Therapy" }] });
      return Promise.reject(new Error(`Unexpected path: ${path}`));
    });

    apiMock.getSubMetaAdsTable.mockResolvedValue({
      client_id: 96,
      currency: "RON",
      date_range: { start_date: "2026-03-01", end_date: "2026-03-31" },
      items: [
        {
          account_id: "meta-1",
          account_name: "Meta Main",
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

  it("replaces Coming Soon and renders Meta multi-account table", async () => {
    render(<SubMetaAdsPage />);

    expect(screen.queryByText("Coming Soon")).not.toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "Meta Ads - Active Life Therapy" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Filter/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Columns/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Export/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Back to Dashboard/i })).toHaveAttribute("href", "/sub/96/dashboard");
    expect(screen.getByRole("link", { name: "Meta Main" })).toHaveAttribute("href", "/sub/96/meta-ads/accounts/meta-1");
    const metaLink = screen.getByRole("link", { name: "Meta Main" });
    const metaRow = metaLink.closest("tr");
    const statusDot = metaRow?.querySelector("span[aria-hidden='true']");
    expect(statusDot?.className).toContain("bg-emerald-500");
    expect(screen.queryByText("X")).not.toBeInTheDocument();
  });

  it("supports column order changes from columns menu", async () => {
    render(<SubMetaAdsPage />);
    await screen.findByText("Meta Main");

    fireEvent.click(screen.getByRole("button", { name: /Columns/i }));
    fireEvent.click(screen.getByLabelText(/Move Visits up/i));

    await waitFor(() => {
      const headers = screen.getAllByRole("columnheader").map((el) => el.textContent ?? "");
      expect(headers.at(-1)).not.toMatch(/^Visits$/i);
    });
  });
});
