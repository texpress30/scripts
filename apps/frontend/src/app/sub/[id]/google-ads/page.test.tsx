import React from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import SubGoogleAdsPage from "./page";

const apiMock = vi.hoisted(() => ({ apiRequest: vi.fn(), getSubGoogleAdsTable: vi.fn() }));

vi.mock("@/lib/api", () => ({
  apiRequest: apiMock.apiRequest,
  getSubGoogleAdsTable: apiMock.getSubGoogleAdsTable,
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

describe("Sub Google Ads details table", () => {
  beforeEach(() => {
    apiMock.apiRequest.mockReset();
    apiMock.getSubGoogleAdsTable.mockReset();
    window.localStorage.clear();

    apiMock.apiRequest.mockImplementation((path: string) => {
      if (path === "/clients") return Promise.resolve({ items: [{ id: 96, display_id: 1096, name: "Active Life Therapy" }] });
      return Promise.reject(new Error(`Unexpected path: ${path}`));
    });

    apiMock.getSubGoogleAdsTable.mockResolvedValue({
      client_id: 96,
      currency: "RON",
      date_range: { start_date: "2026-03-01", end_date: "2026-03-31" },
      items: [
        {
          account_id: "123-111-0001",
          account_name: "Google Main RO",
          status: "active",
          cost: 2916.52,
          rev_inf: 6400.25,
          roas_inf: 2.19,
          mer_inf: 0.46,
          truecac_inf: null,
          ecr_inf: null,
          ecpnv_inf: null,
          new_visits: null,
          visits: null,
        },
      ],
    });
  });

  it("renders Google Ads performance table with real payload values and fallbacks", async () => {
    render(<SubGoogleAdsPage />);

    expect(screen.queryByText("Coming Soon")).not.toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "Google Ads - Active Life Therapy" })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "Cost" })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "Rev (∞d)" })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "ROAS (∞d)" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Google Main RO" })).toHaveAttribute("href", "/sub/96/google-ads/accounts/123-111-0001");
    expect(screen.getByText(/RON\s*2,916\.52/)).toBeInTheDocument();
    expect(screen.getAllByText("—").length).toBeGreaterThan(0);
  });

  it("supports dynamic columns selector with persistence", async () => {
    render(<SubGoogleAdsPage />);
    await screen.findByText("Google Main RO");

    fireEvent.click(screen.getByRole("button", { name: /Columns/i }));
    fireEvent.click(screen.getByLabelText("Visits"));
    fireEvent.click(screen.getByRole("button", { name: /Columns/i }));

    await waitFor(() => expect(screen.queryByRole("columnheader", { name: /^Visits$/i })).not.toBeInTheDocument());

    const stored = window.localStorage.getItem("sub-google-ads-visible-columns-v1");
    expect(stored).toBeTruthy();
    const storedColumns = JSON.parse(String(stored)) as string[];
    expect(storedColumns.includes("visits")).toBe(false);
  });

  it("renders calendar button after Export and refetches on preset change", async () => {
    apiMock.getSubGoogleAdsTable.mockResolvedValue({
      client_id: 96,
      currency: "RON",
      date_range: { start_date: "2026-03-01", end_date: "2026-03-31" },
      items: [],
    });
    render(<SubGoogleAdsPage />);
    await screen.findByRole("heading", { name: "Google Ads - Active Life Therapy" });
    expect(screen.queryByText("Google Main RO")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Last 30 days/i })).toBeInTheDocument();

    const initialCalls = apiMock.getSubGoogleAdsTable.mock.calls.length;
    fireEvent.click(screen.getByRole("button", { name: /Last 30 days/i }));
    fireEvent.click(screen.getByRole("button", { name: "Today" }));

    await waitFor(() => expect(apiMock.getSubGoogleAdsTable.mock.calls.length).toBeGreaterThan(initialCalls));
    const lastCall = apiMock.getSubGoogleAdsTable.mock.calls.at(-1);
    expect(lastCall?.[0]).toBe(96);
    expect(lastCall?.[1]?.start_date).toBe(lastCall?.[1]?.end_date);
  });
});
