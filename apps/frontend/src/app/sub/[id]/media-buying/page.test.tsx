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

function leadPayload() {
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
      custom_rate_label_1: "Rate A",
      custom_rate_label_2: "Rate B",
      custom_cost_label_1: "Cost A",
      custom_cost_label_2: "Cost B",
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
        custom_value_rate_1: 2 / 3,
        custom_value_rate_2: 1,
        cost_per_lead: 20,
        cost_custom_value_1: 116.67,
        cost_custom_value_2: 175,
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
          custom_value_rate_1: 2 / 3,
          custom_value_rate_2: 1,
          cost_per_lead: 20,
          cost_custom_value_1: 116.67,
          cost_custom_value_2: 175,
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
            custom_value_rate_1: 2 / 3,
            custom_value_rate_2: 1,
            cost_per_lead: 20,
            cost_custom_value_1: 116.67,
            cost_custom_value_2: 175,
            cost_per_sale: 175,
          },
        ],
      },
    ],
  };
}


function leadPayloadWithMonths() {
  const base = leadPayload();
  return {
    ...base,
    months: [
      {
        ...base.months[0],
        month: "2026-01",
        totals: { ...base.months[0].totals, date: "2026-01-31" },
        days: [{ ...base.months[0].days[0], date: "2026-01-01" }],
      },
      {
        ...base.months[0],
        month: "2026-02",
        totals: { ...base.months[0].totals, date: "2026-02-28" },
        days: [{ ...base.months[0].days[0], date: "2026-02-01" }],
      },
      {
        ...base.months[0],
        month: "2026-03",
        totals: { ...base.months[0].totals, date: "2026-03-31" },
        days: [{ ...base.months[0].days[0], date: "2026-03-01" }],
      },
    ],
  };
}

describe("SubMediaBuyingPage", () => {
  beforeEach(() => {
    apiMock.apiRequest.mockReset();
  });

  it("reads client_type from Agency Clients and renders lead table only for lead", async () => {
    apiMock.apiRequest.mockImplementation(async (path: string) => {
      if (path === "/clients") return { items: [{ id: 96, name: "Active Life Therapy", client_type: "lead" }] };
      if (path.startsWith("/clients/96/media-buying/lead/table")) return leadPayload();
      throw new Error(`Unexpected path ${path}`);
    });

    render(<SubMediaBuyingPage />);
    expect(await screen.findByRole("heading", { name: "Media Buying - Active Life Therapy" })).toBeInTheDocument();
    expect(await screen.findByRole("button", { name: /Mar 2026/i })).toBeInTheDocument();
  });

  it("ecommerce/programmatic from Agency Clients shows not-implemented fallback and no lead table", async () => {
    apiMock.apiRequest.mockImplementation(async (path: string) => {
      if (path === "/clients") return { items: [{ id: 96, name: "Active Life Therapy", client_type: "programmatic" }] };
      throw new Error(`Unexpected path ${path}`);
    });

    render(<SubMediaBuyingPage />);
    expect(await screen.findByText("Template not implemented yet for this client type (programmatic)."))
      .toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Mar 2026/i })).toBeNull();
  });

  it("supports inline header edit for custom/rate/cost labels and persists through config endpoint", async () => {
    apiMock.apiRequest.mockImplementation(async (path: string, options?: RequestInit) => {
      if (path === "/clients") return { items: [{ id: 96, name: "Active Life Therapy", client_type: "lead" }] };
      if (path.startsWith("/clients/96/media-buying/lead/table")) return leadPayload();
      if (path === "/clients/96/media-buying/config") {
        expect(options?.method).toBe("PUT");
        const payload = JSON.parse(String(options?.body || "{}"));
        return { ...leadPayload().meta, ...payload };
      }
      throw new Error(`Unexpected path ${path}`);
    });

    render(<SubMediaBuyingPage />);
    expect(await screen.findByRole("columnheader", { name: /Appointments/ })).toBeInTheDocument();

    fireEvent.click(screen.getByLabelText("Edit label custom_label_1"));
    const editInput = screen.getByLabelText("Edit custom_label_1");
    fireEvent.change(editInput, { target: { value: "New CV1" } });
    fireEvent.keyDown(editInput, { key: "Enter" });

    expect(await screen.findByText("Label saved")).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: /New CV1/ })).toBeInTheDocument();

    fireEvent.click(screen.getByLabelText("Edit label custom_rate_label_1"));
    const rateInput = screen.getByLabelText("Edit custom_rate_label_1");
    fireEvent.change(rateInput, { target: { value: "Rate Edited" } });
    fireEvent.keyDown(rateInput, { key: "Enter" });
    expect(await screen.findByRole("columnheader", { name: /Rate Edited/ })).toBeInTheDocument();

    fireEvent.click(screen.getByLabelText("Edit label custom_cost_label_1"));
    const costInput = screen.getByLabelText("Edit custom_cost_label_1");
    fireEvent.change(costInput, { target: { value: "Cost Edited" } });
    fireEvent.keyDown(costInput, { key: "Enter" });
    expect(await screen.findByRole("columnheader", { name: /Cost Edited/ })).toBeInTheDocument();
  });

  it("cancel inline label edit with Escape does not persist", async () => {
    apiMock.apiRequest.mockImplementation(async (path: string) => {
      if (path === "/clients") return { items: [{ id: 96, name: "Active Life Therapy", client_type: "lead" }] };
      if (path.startsWith("/clients/96/media-buying/lead/table")) return leadPayload();
      throw new Error(`Unexpected path ${path}`);
    });

    render(<SubMediaBuyingPage />);
    expect(await screen.findByRole("columnheader", { name: /Appointments/ })).toBeInTheDocument();

    fireEvent.click(screen.getByLabelText("Edit label custom_label_1"));
    const editInput = screen.getByLabelText("Edit custom_label_1");
    fireEvent.change(editInput, { target: { value: "Will cancel" } });
    fireEvent.keyDown(editInput, { key: "Escape" });

    expect(screen.getByRole("columnheader", { name: /Appointments/ })).toBeInTheDocument();
    expect(apiMock.apiRequest).not.toHaveBeenCalledWith("/clients/96/media-buying/config", expect.anything());
  });

  it("daily row edit/save keeps month rows read-only and refreshes via table refetch", async () => {
    apiMock.apiRequest.mockImplementation(async (path: string, options?: RequestInit) => {
      if (path === "/clients") return { items: [{ id: 96, name: "Active Life Therapy", client_type: "lead" }] };
      if (path.startsWith("/clients/96/media-buying/lead/table")) {
        const callCount = apiMock.apiRequest.mock.calls.filter(([p]) => String(p).startsWith("/clients/96/media-buying/lead/table")).length;
        if (callCount <= 1) return leadPayload();
        const payload = leadPayload();
        payload.months[0].totals.leads = 20;
        payload.months[0].days[0].leads = 20;
        return payload;
      }
      if (path === "/clients/96/media-buying/lead/daily-values") {
        expect(options?.method).toBe("PUT");
        return { status: "ok" };
      }
      throw new Error(`Unexpected path ${path}`);
    });

    render(<SubMediaBuyingPage />);
    expect(await screen.findByRole("button", { name: "Edit" })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Edit" }));
    fireEvent.change(screen.getByLabelText("Leads 2026-03-11"), { target: { value: "20" } });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));

    await screen.findByText("Saved");
    await waitFor(() => expect(screen.getAllByText("20").length).toBeGreaterThan(0));
    expect(await screen.findByRole("button", { name: /Mar 2026/i })).toBeInTheDocument();
  });

  it("shows validation errors and disables save for invalid row values", async () => {
    apiMock.apiRequest.mockImplementation(async (path: string) => {
      if (path === "/clients") return { items: [{ id: 96, name: "Active Life Therapy", client_type: "lead" }] };
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

  it("fallback labels remain coherent when optional fields are missing", async () => {
    apiMock.apiRequest.mockImplementation(async (path: string) => {
      if (path === "/clients") return { items: [{ id: 96, name: "Active Life Therapy", client_type: "lead" }] };
      if (path.startsWith("/clients/96/media-buying/lead/table")) {
        const payload = leadPayload();
        delete payload.meta.custom_label_1;
        delete payload.meta.custom_rate_label_1;
        delete payload.meta.custom_cost_label_1;
        return payload;
      }
      throw new Error(`Unexpected path ${path}`);
    });

    render(<SubMediaBuyingPage />);
    expect(await screen.findByText("Custom Value 1")).toBeInTheDocument();
    expect(screen.getByText("Custom Value Rate 1")).toBeInTheDocument();
    expect(screen.getByText("Cost Custom Value 1")).toBeInTheDocument();
  });

  it("formats daily dates, applies semantic column styles, dashed separators, and reverse month order", async () => {
    apiMock.apiRequest.mockImplementation(async (path: string) => {
      if (path === "/clients") return { items: [{ id: 96, name: "Active Life Therapy", client_type: "lead" }] };
      if (path.startsWith("/clients/96/media-buying/lead/table")) return leadPayloadWithMonths();
      throw new Error(`Unexpected path ${path}`);
    });

    render(<SubMediaBuyingPage />);

    const monthButtons = await screen.findAllByRole("button", { name: /(Ian|Feb|Mar) 2026/i });
    expect(monthButtons.map((item) => item.textContent || "")[0]).toContain("Mar 2026");

    expect(screen.getByText("1 Mar")).toBeInTheDocument();

    expect(screen.getByRole("columnheader", { name: /Cost Google/i }).className).toContain("text-[#bfbfbf]");
    expect(screen.getByRole("columnheader", { name: /Cost Total/i }).className).toContain("border-dashed");
    expect(screen.getByRole("columnheader", { name: /Total Lead-uri/i }).className).toContain("border-dashed");

    const unrealizedCells = screen.getAllByText(/\(RON\s?40\.00\)|\(.*40.*RON.*\)/i);
    expect(unrealizedCells.length).toBeGreaterThan(0);
    expect(unrealizedCells[0].closest("td")?.className || "").toContain("text-red-600");

    fireEvent.click(screen.getByRole("button", { name: /Mar 2026/i }));
    expect(screen.queryByText("1 Mar")).toBeNull();
  });

  it("renders loading and error state", async () => {
    apiMock.apiRequest.mockImplementation(async (path: string) => {
      if (path === "/clients") return { items: [{ id: 96, name: "Active Life Therapy", client_type: "lead" }] };
      throw new Error("boom");
    });

    render(<SubMediaBuyingPage />);
    expect(screen.getByText("Loading Media Buying table...")).toBeInTheDocument();
    expect(await screen.findByText("boom")).toBeInTheDocument();
  });
});
