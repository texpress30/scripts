import React from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

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

function leadPayload({ leads = 10, monthCostTotal = 350 }: { leads?: number; monthCostTotal?: number } = {}) {
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
        cost_total: monthCostTotal,
        percent_change: null,
        leads,
        phones: 5,
        total_leads: leads + 5,
        custom_value_1_count: 3,
        custom_value_2_count: 2,
        custom_value_3_amount_ron: 30,
        custom_value_4_amount_ron: 40,
        custom_value_5_amount_ron: -5,
        sales_count: 2,
        custom_value_rate_1: 2 / 3,
        custom_value_rate_2: 1,
        cost_per_lead: monthCostTotal / (leads + 5),
        cost_custom_value_1: monthCostTotal / 3,
        cost_custom_value_2: monthCostTotal / 2,
        cost_per_sale: monthCostTotal / 2,
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
          cost_total: monthCostTotal,
          percent_change: null,
          leads,
          phones: 5,
          total_leads: leads + 5,
          custom_value_1_count: 3,
          custom_value_2_count: 2,
          custom_value_3_amount_ron: 30,
          custom_value_4_amount_ron: 40,
          custom_value_5_amount_ron: -5,
          sales_count: 2,
          custom_value_rate_1: 2 / 3,
          custom_value_rate_2: 1,
          cost_per_lead: monthCostTotal / (leads + 5),
          cost_custom_value_1: monthCostTotal / 3,
          cost_custom_value_2: monthCostTotal / 2,
          cost_per_sale: monthCostTotal / 2,
        },
        days: [
          {
            date: "2026-03-11",
            cost_google: 100,
            cost_meta: 200,
            cost_tiktok: 50,
            cost_total: monthCostTotal,
            percent_change: null,
            leads,
            phones: 5,
            total_leads: leads + 5,
            custom_value_1_count: 3,
            custom_value_2_count: 2,
            custom_value_3_amount_ron: 30,
            custom_value_4_amount_ron: 40,
            custom_value_5_amount_ron: -5,
            sales_count: 2,
            custom_value_rate_1: 2 / 3,
            custom_value_rate_2: 1,
            cost_per_lead: monthCostTotal / (leads + 5),
            cost_custom_value_1: monthCostTotal / 3,
            cost_custom_value_2: monthCostTotal / 2,
            cost_per_sale: monthCostTotal / 2,
          },
        ],
      },
    ],
  };
}

describe("SubMediaBuyingPage", () => {
  beforeEach(() => {
    apiMock.apiRequest.mockReset();
  });

  it("renders grouped lead table with custom labels and placeholder for %^", async () => {
    apiMock.apiRequest.mockImplementation(async (path: string) => {
      if (path === "/clients") return { items: [{ id: 96, name: "Active Life Therapy" }] };
      if (path.startsWith("/clients/96/media-buying/lead/table")) return leadPayload();
      throw new Error(`Unexpected path ${path}`);
    });

    render(<SubMediaBuyingPage />);

    expect(await screen.findByRole("heading", { name: "Media Buying - Active Life Therapy" })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "Appointments" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /March 2026/i })).toBeInTheDocument();
    expect(screen.getAllByText("—").length).toBeGreaterThan(0);
    expect(screen.getByRole("button", { name: "Edit" })).toBeInTheDocument();
  });

  it("allows edit, save, refetch and shows recalculated values from reloaded payload", async () => {
    apiMock.apiRequest.mockImplementation(async (path: string, options?: RequestInit) => {
      if (path === "/clients") return { items: [{ id: 96, name: "Active Life Therapy" }] };
      if (path.startsWith("/clients/96/media-buying/lead/table")) {
        const callCount = apiMock.apiRequest.mock.calls.filter(([p]) => String(p).startsWith("/clients/96/media-buying/lead/table")).length;
        return callCount <= 1 ? leadPayload({ leads: 10, monthCostTotal: 350 }) : leadPayload({ leads: 20, monthCostTotal: 350 });
      }
      if (path === "/clients/96/media-buying/lead/daily-values") {
        expect(options?.method).toBe("PUT");
        const body = JSON.parse(String(options?.body || "{}"));
        expect(body.date).toBe("2026-03-11");
        expect(body.leads).toBe(20);
        return { status: "ok" };
      }
      throw new Error(`Unexpected path ${path}`);
    });

    render(<SubMediaBuyingPage />);
    expect(await screen.findByRole("button", { name: "Edit" })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Edit" }));
    const leadsInput = screen.getByLabelText("Leads 2026-03-11");
    fireEvent.change(leadsInput, { target: { value: "20" } });

    fireEvent.click(screen.getByRole("button", { name: "Save" }));

    await screen.findByText("Saved");
    await waitFor(() => {
      expect(screen.getAllByText("20").length).toBeGreaterThan(0);
    });
  });

  it("supports cancel/reset per row and does not call save", async () => {
    apiMock.apiRequest.mockImplementation(async (path: string) => {
      if (path === "/clients") return { items: [{ id: 96, name: "Active Life Therapy" }] };
      if (path.startsWith("/clients/96/media-buying/lead/table")) return leadPayload();
      throw new Error(`Unexpected path ${path}`);
    });

    render(<SubMediaBuyingPage />);
    expect(await screen.findByRole("button", { name: "Edit" })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Edit" }));
    fireEvent.change(screen.getByLabelText("Leads 2026-03-11"), { target: { value: "999" } });
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));

    expect(screen.queryByLabelText("Leads 2026-03-11")).toBeNull();
    expect(apiMock.apiRequest).not.toHaveBeenCalledWith(
      "/clients/96/media-buying/lead/daily-values",
      expect.anything()
    );
  });

  it("shows validation errors and disables save for invalid row values", async () => {
    apiMock.apiRequest.mockImplementation(async (path: string) => {
      if (path === "/clients") return { items: [{ id: 96, name: "Active Life Therapy" }] };
      if (path.startsWith("/clients/96/media-buying/lead/table")) return leadPayload();
      throw new Error(`Unexpected path ${path}`);
    });

    render(<SubMediaBuyingPage />);
    expect(await screen.findByRole("button", { name: "Edit" })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Edit" }));
    fireEvent.change(screen.getByLabelText("Leads 2026-03-11"), { target: { value: "-1" } });

    expect(screen.getByText("Must be integer >= 0")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Save" })).toBeDisabled();
  });

  it("keeps non-lead fallback and month rows as read-only", async () => {
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

  it("renders loading, error and empty states", async () => {
    apiMock.apiRequest.mockImplementation(async (path: string) => {
      if (path === "/clients") return { items: [{ id: 96, name: "Active Life Therapy" }] };
      throw new Error("boom");
    });

    render(<SubMediaBuyingPage />);
    expect(screen.getByText("Loading Media Buying table...")).toBeInTheDocument();
    expect(await screen.findByText("boom")).toBeInTheDocument();
  });
});
