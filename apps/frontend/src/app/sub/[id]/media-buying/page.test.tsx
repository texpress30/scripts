import React from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";

import SubMediaBuyingPage from "./page";

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

describe("SubMediaBuyingPage", () => {
  beforeEach(() => {
    apiMock.apiRequest.mockReset();
  });

  it("renders lead table with monthly grouping, custom labels, and %^ fallback", async () => {
    apiMock.apiRequest.mockImplementation(async (path: string) => {
      if (path === "/clients") return { items: [{ id: 96, name: "Active Life Therapy" }] };
      if (path.startsWith("/clients/96/media-buying/lead/table")) {
        return {
          meta: {
            client_id: 96,
            template_type: "lead",
            display_currency: "RON",
            custom_label_1: "Appointments",
            custom_label_2: "Qualified",
            custom_label_3: "CV3",
            custom_label_4: "CV4",
            custom_label_5: "Refund",
            date_from: "2026-01-01",
            date_to: "2026-03-31",
            available_months: ["2026-03"],
          },
          days: [
            {
              date: "2026-03-11",
              cost_google: 100,
              cost_meta: 200,
              cost_tiktok: 50,
              cost_total: 350,
              percent_change: null,
              leads: 10,
              phones: 5,
              total_leads: 15,
              custom_value_1_count: 3,
              custom_value_2_count: 2,
              custom_value_3_amount_ron: 30,
              custom_value_4_amount_ron: 40,
              custom_value_5_amount_ron: -5,
              sales_count: 2,
              custom_value_rate_1: 0.5,
              custom_value_rate_2: null,
              cost_per_lead: 23.33,
              cost_custom_value_1: 100,
              cost_custom_value_2: null,
              cost_per_sale: 175,
            },
          ],
          months: [
            {
              month: "2026-03",
              date_from: "2026-03-01",
              date_to: "2026-03-31",
              totals: {
                date: "2026-03-31",
                cost_google: 100,
                cost_meta: 200,
                cost_tiktok: 50,
                cost_total: 350,
                percent_change: null,
                leads: 10,
                phones: 5,
                total_leads: 15,
                custom_value_1_count: 3,
                custom_value_2_count: 2,
                custom_value_3_amount_ron: 30,
                custom_value_4_amount_ron: 40,
                custom_value_5_amount_ron: -5,
                sales_count: 2,
                custom_value_rate_1: 0.5,
                custom_value_rate_2: null,
                cost_per_lead: 23.33,
                cost_custom_value_1: 100,
                cost_custom_value_2: null,
                cost_per_sale: 175,
              },
              days: [
                {
                  date: "2026-03-11",
                  cost_google: 100,
                  cost_meta: 200,
                  cost_tiktok: 50,
                  cost_total: 350,
                  percent_change: null,
                  leads: 10,
                  phones: 5,
                  total_leads: 15,
                  custom_value_1_count: 3,
                  custom_value_2_count: 2,
                  custom_value_3_amount_ron: 30,
                  custom_value_4_amount_ron: 40,
                  custom_value_5_amount_ron: -5,
                  sales_count: 2,
                  custom_value_rate_1: 0.5,
                  custom_value_rate_2: null,
                  cost_per_lead: 23.33,
                  cost_custom_value_1: 100,
                  cost_custom_value_2: null,
                  cost_per_sale: 175,
                },
              ],
            },
          ],
        };
      }
      throw new Error(`Unexpected path ${path}`);
    });

    render(<SubMediaBuyingPage />);

    expect(await screen.findByRole("heading", { name: "Media Buying - Active Life Therapy" })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "Appointments" })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "Qualified" })).toBeInTheDocument();
    expect(screen.getAllByText("—").length).toBeGreaterThan(0);

    expect(screen.getByRole("button", { name: /March 2026/i })).toBeInTheDocument();
    expect(screen.getByText("2026-03-11")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /March 2026/i }));
    expect(screen.queryByText("2026-03-11")).toBeNull();
  });

  it("renders non-lead fallback", async () => {
    apiMock.apiRequest.mockImplementation(async (path: string) => {
      if (path === "/clients") return { items: [{ id: 96, name: "Active Life Therapy" }] };
      if (path.startsWith("/clients/96/media-buying/lead/table")) {
        return {
          meta: { client_id: 96, template_type: "ecommerce", display_currency: "RON", date_from: "2026-01-01", date_to: "2026-03-31", available_months: [] },
          days: [],
          months: [],
        };
      }
      throw new Error(`Unexpected path ${path}`);
    });

    render(<SubMediaBuyingPage />);
    expect(await screen.findByText("Template not implemented yet for this sub-account.")).toBeInTheDocument();
  });

  it("renders loading and error state", async () => {
    apiMock.apiRequest.mockImplementation(async (path: string) => {
      if (path === "/clients") return { items: [{ id: 96, name: "Active Life Therapy" }] };
      throw new Error("boom");
    });

    render(<SubMediaBuyingPage />);
    expect(screen.getByText("Loading Media Buying table...")).toBeInTheDocument();
    expect(await screen.findByText("boom")).toBeInTheDocument();
  });

  it("renders empty state when lead payload has no months", async () => {
    apiMock.apiRequest.mockImplementation(async (path: string) => {
      if (path === "/clients") return { items: [{ id: 96, name: "Active Life Therapy" }] };
      if (path.startsWith("/clients/96/media-buying/lead/table")) {
        return {
          meta: { client_id: 96, template_type: "lead", display_currency: "RON", date_from: "2026-01-01", date_to: "2026-03-31", available_months: [] },
          days: [],
          months: [],
        };
      }
      throw new Error(`Unexpected path ${path}`);
    });

    render(<SubMediaBuyingPage />);
    expect(await screen.findByText("No data available for selected range.")).toBeInTheDocument();
  });
});
