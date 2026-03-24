import React from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import SubMediaBuyingPage from "./page";
import { formatCurrencyValue } from "@/lib/subAccountCurrency";

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

function leadPayload(displayCurrency: string = "RON") {
  return {
    meta: {
      client_id: 96,
      template_type: "lead",
      display_currency: displayCurrency,
      custom_label_1: "Appointments",
      custom_label_2: "Qualified",
      custom_label_3: "Val. Aprobata",
      custom_label_4: "Val. Nerealizata",
      custom_label_5: "Val. Vanduta",
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
        percent_change: 0.25,
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
          percent_change: 0.1,
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
            percent_change: 0.25,
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


function leadPayloadMonthsFirst() {
  const base = leadPayload();
  return {
    ...base,
    days: [],
    months: [
      {
        month: "2026-03",
        date_from: "2026-03-01",
        date_to: "2026-03-31",
        totals: { ...base.months[0].totals },
        day_count: 1,
        has_days: true,
      },
    ],
  };
}

function monthDaysPayload() {
  const base = leadPayload();
  return {
    meta: base.meta,
    month_start: "2026-03-01",
    days: base.days,
  };
}

describe("SubMediaBuyingPage", () => {
  beforeEach(() => {
    apiMock.apiRequest.mockReset();
  });


  it("renders monetary values using response display_currency (USD/RON/EUR)", async () => {
    for (const currency of ["USD", "RON", "EUR"]) {
      apiMock.apiRequest.mockReset();
      apiMock.apiRequest.mockImplementation(async (path: string) => {
        if (path === "/clients") return { items: [{ id: 96, name: "Active Life Therapy", client_type: "lead" }] };
        if (path.startsWith("/clients/96/media-buying/lead/table")) return leadPayload(currency);
        throw new Error(`Unexpected path ${path}`);
      });

      const { unmount } = render(<SubMediaBuyingPage />);
      await screen.findByRole("button", { name: /Mar 2026/i });
      expect(screen.getByText(`Currency: ${currency}`)).toBeInTheDocument();
      const expectedMoney = formatCurrencyValue(350, currency, "USD");
      const normalizedExpected = expectedMoney.replace(/ /g, " ");
      const moneyCells = screen.getAllByText((content) => content.replace(/ /g, " ") === normalizedExpected);
      expect(moneyCells.length).toBeGreaterThan(0);
      unmount();
    }
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

  it("shows Edit in Data CTA and keeps current month context", async () => {
    apiMock.apiRequest.mockImplementation(async (path: string) => {
      if (path === "/clients") return { items: [{ id: 96, name: "Active Life Therapy", client_type: "lead" }] };
      if (path.startsWith("/clients/96/media-buying/lead/table")) return leadPayload();
      throw new Error(`Unexpected path ${path}`);
    });

    render(<SubMediaBuyingPage />);
    expect(await screen.findByRole("columnheader", { name: /Appointments/ })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Edit in Data" })).toHaveAttribute("href", "/sub/96/data?month=2026-03");
  });

  it("is read-only for business values in daily rows", async () => {
    apiMock.apiRequest.mockImplementation(async (path: string) => {
      if (path === "/clients") return { items: [{ id: 96, name: "Active Life Therapy", client_type: "lead" }] };
      if (path.startsWith("/clients/96/media-buying/lead/table")) return leadPayload();
      throw new Error(`Unexpected path ${path}`);
    });

    render(<SubMediaBuyingPage />);
    expect(await screen.findByRole("button", { name: /Mar 2026/i })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Edit" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Save" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Cancel" })).toBeNull();
    expect(screen.queryByLabelText(/Leads 2026-03-11/)).toBeNull();
    expect(screen.queryByText("Edit values in Data page")).toBeNull();
  });

  it("does not expose inline label editing controls", async () => {
    apiMock.apiRequest.mockImplementation(async (path: string) => {
      if (path === "/clients") return { items: [{ id: 96, name: "Active Life Therapy", client_type: "lead" }] };
      if (path.startsWith("/clients/96/media-buying/lead/table")) return leadPayload();
      throw new Error(`Unexpected path ${path}`);
    });

    render(<SubMediaBuyingPage />);
    expect(await screen.findByRole("columnheader", { name: /Appointments/ })).toBeInTheDocument();
    expect(screen.queryByLabelText("Edit label custom_label_1")).toBeNull();
    expect(screen.queryByLabelText("Edit custom_label_1")).toBeNull();
    expect(apiMock.apiRequest).not.toHaveBeenCalledWith("/clients/96/media-buying/config", expect.objectContaining({ method: "PUT" }));
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


  it("renders percent_change values and fallback for null", async () => {
    apiMock.apiRequest.mockImplementation(async (path: string) => {
      if (path === "/clients") return { items: [{ id: 96, name: "Active Life Therapy", client_type: "lead" }] };
      if (path.startsWith("/clients/96/media-buying/lead/table")) {
        const payload = leadPayloadWithMonths();
        payload.months[0].totals.percent_change = null;
        payload.months[0].days[0].percent_change = null;
        payload.months[1].totals.percent_change = 0.5;
        payload.months[1].days[0].percent_change = -0.4;
        payload.months[2].totals.percent_change = 1.0;
        payload.months[2].days[0].percent_change = 0.25;
        return payload;
      }
      throw new Error(`Unexpected path ${path}`);
    });

    render(<SubMediaBuyingPage />);

    expect(await screen.findByRole("button", { name: /Mar 2026/i })).toBeInTheDocument();
    expect(screen.getAllByText("25.00%").length).toBeGreaterThan(0);

    fireEvent.click(screen.getByRole("button", { name: /Mar 2026/i }));
    fireEvent.click(screen.getByRole("button", { name: /Feb 2026/i }));
    expect(screen.getByText("50.00%")).toBeInTheDocument();
    expect(screen.getByText("-40.00%")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /Feb 2026/i }));
    fireEvent.click(screen.getByRole("button", { name: /Ian 2026/i }));
    expect(screen.getAllByText("—").length).toBeGreaterThan(0);
  });

  it("formats daily dates, keeps non-custom semantic styles, dashed separators, and reverse month order", async () => {
    apiMock.apiRequest.mockImplementation(async (path: string) => {
      if (path === "/clients") return { items: [{ id: 96, name: "Active Life Therapy", client_type: "lead" }] };
      if (path.startsWith("/clients/96/media-buying/lead/table")) return leadPayloadWithMonths();
      throw new Error(`Unexpected path ${path}`);
    });

    render(<SubMediaBuyingPage />);

    const monthButtons = await screen.findAllByRole("button", { name: /(Ian|Feb|Mar) 2026/i });
    expect(monthButtons.map((item) => item.textContent || "")[0]).toContain("Mar 2026");

    expect(screen.getByText("1 Mar")).toBeInTheDocument();

    const dateHeader = screen.getByRole("columnheader", { name: /^Data$/i });
    expect(dateHeader.className).toContain("sticky");
    expect(dateHeader.className).toContain("top-0");
    expect(dateHeader.className).toContain("left-0");
    expect(dateHeader.className).toContain("bg-slate-50");

    expect(screen.getByRole("columnheader", { name: /Cost Google/i }).className).toContain("text-[#bfbfbf]");
    expect(screen.getByRole("columnheader", { name: /Cost Google/i }).className).toContain("sticky");
    expect(screen.getByRole("columnheader", { name: /Cost Google/i }).className).toContain("top-0");
    expect(screen.getByRole("columnheader", { name: /Cost Total/i }).className).toContain("border-dashed");
    expect(screen.getByRole("columnheader", { name: /Total Lead-uri/i }).className).toContain("border-dashed");

    const unrealizedCells = screen.getAllByText((content) => content.includes("40") && content.toUpperCase().includes("RON") && content.includes("("));
    expect(unrealizedCells.length).toBeGreaterThan(0);
    expect(unrealizedCells[0].className || "").toContain("text-slate-900");
    expect(unrealizedCells[0].className || "").not.toContain("text-red-600");

    fireEvent.click(screen.getByRole("button", { name: /Mar 2026/i }));
    expect(screen.queryByText("1 Mar")).toBeNull();
  });

  it("keeps first date column sticky and remains compatible with column visibility", async () => {
    apiMock.apiRequest.mockImplementation(async (path: string, options?: RequestInit) => {
      if (path === "/clients") return { items: [{ id: 96, name: "Active Life Therapy", client_type: "lead" }] };
      if (path.startsWith("/clients/96/media-buying/lead/table")) return leadPayload();
      if (path === "/clients/96/media-buying/config") {
        const body = JSON.parse(String(options?.body || "{}"));
        return { ...leadPayload().meta, ...body };
      }
      throw new Error(`Unexpected path ${path}`);
    });

    render(<SubMediaBuyingPage />);
    await screen.findByRole("button", { name: /Mar 2026/i });

    const monthToggle = screen.getByRole("button", { name: /Mar 2026/i });
    const monthDateCell = monthToggle.closest("td");
    expect(monthDateCell).toBeTruthy();
    expect(monthDateCell?.className || "").toContain("sticky");
    expect(monthDateCell?.className || "").toContain("left-0");

    const dayDateCell = screen.getByText(/\d+ Mar/i).closest("td");
    expect(dayDateCell).toBeTruthy();
    expect(dayDateCell?.className || "").toContain("sticky");
    expect(dayDateCell?.className || "").toContain("left-0");

    fireEvent.click(screen.getByRole("button", { name: /Customize columns/i }));
    fireEvent.click(screen.getByLabelText(/Cost Google/i));
    expect(await screen.findByText("View saved")).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: /^Data$/i }).className).toContain("sticky");
  });

  it("renders custom value and custom rate columns without special text colors", async () => {
    apiMock.apiRequest.mockImplementation(async (path: string) => {
      if (path === "/clients") return { items: [{ id: 96, name: "Active Life Therapy", client_type: "lead" }] };
      if (path.startsWith("/clients/96/media-buying/lead/table")) {
        const payload = leadPayload();
        payload.months[0].totals.custom_value_3_amount_ron = 100;
        payload.months[0].totals.custom_value_5_amount_ron = 70;
        payload.months[0].totals.custom_value_4_amount_ron = 30;
        payload.months[0].days[0].custom_value_4_amount_ron = 0;
        payload.months[0].days[0].custom_value_5_amount_ron = 100;
        return payload;
      }
      throw new Error(`Unexpected path ${path}`);
    });

    render(<SubMediaBuyingPage />);
    await screen.findByRole("button", { name: /Mar 2026/i });

    const rateAHeader = screen.getByRole("columnheader", { name: /Rate A/i });
    const rateBHeader = screen.getByRole("columnheader", { name: /Rate B/i });
    expect(rateAHeader.className).not.toContain("text-violet-600");
    expect(rateBHeader.className).not.toContain("text-violet-600");

    const custom1Header = screen.getByRole("columnheader", { name: /Appointments/i });
    expect(custom1Header.className).not.toContain("text-[#bfbfbf]");

    const customRateCells = screen.getAllByText(/66\.67%|100\.00%/i).map((item) => item.closest("td")).filter(Boolean) as HTMLTableCellElement[];
    expect(customRateCells.length).toBeGreaterThan(0);
    for (const cell of customRateCells) {
      expect(cell.className).not.toContain("text-violet-600");
      expect(cell.className).not.toContain("text-[#bfbfbf]");
    }

    const customValueCells = screen.getAllByText(/RON\s?30\.00|30\.00\s?RON/i).map((item) => item.closest("td")).filter(Boolean) as HTMLTableCellElement[];
    expect(customValueCells.length).toBeGreaterThan(0);
    for (const cell of customValueCells) {
      expect(cell.className).not.toContain("text-violet-600");
      expect(cell.className).not.toContain("text-[#bfbfbf]");
    }

    const soldHeader = screen.getByRole("columnheader", { name: /Val\. Vanduta/i });
    expect(soldHeader.className).not.toContain("text-red-600");

    const unrealizedHeader = screen.getByRole("columnheader", { name: /Val\. Nerealizata/i });
    expect(unrealizedHeader.className).not.toContain("text-red-600");

    expect(screen.getByText(/\(RON\s?30\.00\)|\(.*30.*RON.*\)/i)).toBeInTheDocument();
    expect(screen.getAllByText(/RON\s?100\.00|100\.00\s?RON/i).length).toBeGreaterThan(0);
  });

  it("keeps custom columns uncolored even when client custom labels are changed", async () => {
    apiMock.apiRequest.mockImplementation(async (path: string) => {
      if (path === "/clients") return { items: [{ id: 96, name: "Active Life Therapy", client_type: "lead" }] };
      if (path.startsWith("/clients/96/media-buying/lead/table")) {
        const payload = leadPayload();
        payload.meta.custom_label_1 = "Lead Brut";
        payload.meta.custom_label_2 = "Lead Calificat";
        payload.meta.custom_label_3 = "Valoare Bruta";
        payload.meta.custom_label_4 = "Valoare Nerealizata";
        payload.meta.custom_label_5 = "Valoare Vanduta";
        payload.meta.custom_rate_label_1 = "Rata Conversie A";
        payload.meta.custom_rate_label_2 = "Rata Conversie B";
        return payload;
      }
      throw new Error(`Unexpected path ${path}`);
    });

    render(<SubMediaBuyingPage />);
    await screen.findByRole("button", { name: /Mar 2026/i });

    expect(screen.getByRole("columnheader", { name: /Lead Brut/i }).className).not.toContain("text-[#bfbfbf]");
    expect(screen.getByRole("columnheader", { name: /Lead Calificat/i }).className).not.toContain("text-[#bfbfbf]");
    expect(screen.getByRole("columnheader", { name: /Valoare Bruta/i }).className).not.toContain("text-[#bfbfbf]");
    expect(screen.getByRole("columnheader", { name: /Rata Conversie A/i }).className).not.toContain("text-violet-600");
    expect(screen.getByRole("columnheader", { name: /Rata Conversie B/i }).className).not.toContain("text-violet-600");
  });

  it("supports column visibility toggling and persists selected view via config", async () => {
    apiMock.apiRequest.mockImplementation(async (path: string, options?: RequestInit) => {
      if (path === "/clients") return { items: [{ id: 96, name: "Active Life Therapy", client_type: "lead" }] };
      if (path.startsWith("/clients/96/media-buying/lead/table")) {
        const payload = leadPayload();
        payload.meta.visible_columns = ["date", "cost_total", "custom_value_5_amount_ron"];
        return payload;
      }
      if (path === "/clients/96/media-buying/config") {
        const body = JSON.parse(String(options?.body || "{}"));
        return { ...leadPayload().meta, ...body };
      }
      throw new Error(`Unexpected path ${path}`);
    });

    render(<SubMediaBuyingPage />);
    await screen.findByRole("button", { name: /Mar 2026/i });

    expect(screen.queryByRole("columnheader", { name: /Cost Google/i })).toBeNull();
    expect(screen.getByRole("columnheader", { name: /Cost Total/i })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /Customize columns/i }));
    fireEvent.click(screen.getByLabelText(/Cost Google/i));

    await screen.findByText("View saved");
    expect(screen.getByRole("columnheader", { name: /Cost Google/i })).toBeInTheDocument();
    expect(apiMock.apiRequest).toHaveBeenCalledWith(
      "/clients/96/media-buying/config",
      expect.objectContaining({ method: "PUT" })
    );
  });

  it("falls back to default visible columns when config has no saved view", async () => {
    apiMock.apiRequest.mockImplementation(async (path: string) => {
      if (path === "/clients") return { items: [{ id: 96, name: "Active Life Therapy", client_type: "lead" }] };
      if (path.startsWith("/clients/96/media-buying/lead/table")) {
        const payload = leadPayload();
        delete payload.meta.visible_columns;
        return payload;
      }
      throw new Error(`Unexpected path ${path}`);
    });

    render(<SubMediaBuyingPage />);
    expect(await screen.findByRole("columnheader", { name: /Cost Google/i })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: /Val\. Aprobata/i })).toBeInTheDocument();
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


  it("uses client context currency when table display_currency is missing", async () => {
    apiMock.apiRequest.mockImplementation(async (path: string) => {
      if (path === "/clients") return { items: [{ id: 96, name: "Active Life Therapy", client_type: "lead", currency: "RON" }] };
      if (path.startsWith("/clients/96/media-buying/lead/table")) {
        const payload = leadPayload();
        delete payload.meta.display_currency;
        return payload;
      }
      throw new Error(`Unexpected path ${path}`);
    });

    render(<SubMediaBuyingPage />);
    expect(await screen.findByText("Currency: RON")).toBeInTheDocument();
  });

  it("shows placeholder currency when table and client context currencies are unavailable", async () => {
    apiMock.apiRequest.mockImplementation(async (path: string) => {
      if (path === "/clients") return { items: [{ id: 96, name: "Active Life Therapy", client_type: "lead" }] };
      if (path.startsWith("/clients/96/media-buying/lead/table")) {
        const payload = leadPayload();
        delete payload.meta.display_currency;
        return payload;
      }
      throw new Error(`Unexpected path ${path}`);
    });

    render(<SubMediaBuyingPage />);
    expect(await screen.findByText("Currency: —")).toBeInTheDocument();
    expect(screen.queryByText("Currency: USD")).toBeNull();
  });

  it("keeps non-USD currency label on table error using client context currency", async () => {
    apiMock.apiRequest.mockImplementation(async (path: string) => {
      if (path === "/clients") return { items: [{ id: 96, name: "Active Life Therapy", client_type: "lead", currency: "EUR" }] };
      if (path.startsWith("/clients/96/media-buying/lead/table")) throw new Error("boom");
      throw new Error(`Unexpected path ${path}`);
    });

    render(<SubMediaBuyingPage />);
    expect(await screen.findByText("boom")).toBeInTheDocument();
    expect(screen.getByText("Currency: EUR")).toBeInTheDocument();
    expect(screen.queryByText("Currency: USD")).toBeNull();
  });

  it("uses effective range metadata from API and requests table without implicit date query params", async () => {
    apiMock.apiRequest.mockImplementation(async (path: string) => {
      if (path === "/clients") return { items: [{ id: 96, name: "Active Life Therapy", client_type: "lead" }] };
      if (path === "/clients/96/media-buying/lead/table?include_days=false") {
        const payload = leadPayload();
        payload.meta.date_from = "2025-12-13";
        payload.meta.date_to = "2026-03-12";
        payload.meta.effective_date_from = "2026-01-01";
        payload.meta.effective_date_to = "2026-03-11";
        return payload;
      }
      throw new Error(`Unexpected path ${path}`);
    });

    render(<SubMediaBuyingPage />);

    expect(await screen.findByText(/Range: 2026-01-01 - 2026-03-11/i)).toBeInTheDocument();
    expect(apiMock.apiRequest).toHaveBeenCalledWith("/clients/96/media-buying/lead/table?include_days=false");
  });

  it("uses include_days=false on initial request and lazy-loads month days on expand", async () => {
    apiMock.apiRequest.mockImplementation(async (path: string) => {
      if (path === "/clients") return { items: [{ id: 96, name: "Active Life Therapy", client_type: "lead" }] };
      if (path === "/clients/96/media-buying/lead/table?include_days=false") return leadPayloadMonthsFirst();
      if (path === "/clients/96/media-buying/lead/month-days?month_start=2026-03-01") return monthDaysPayload();
      throw new Error(`Unexpected path ${path}`);
    });

    render(<SubMediaBuyingPage />);
    expect(await screen.findByRole("button", { name: /Mar 2026/i })).toBeInTheDocument();
    expect(apiMock.apiRequest).toHaveBeenCalledWith("/clients/96/media-buying/lead/table?include_days=false");
    expect(await screen.findByText("11 Mar")).toBeInTheDocument();
  });

  it("re-expanding an already loaded month uses cached rows without refetch", async () => {
    apiMock.apiRequest.mockImplementation(async (path: string) => {
      if (path === "/clients") return { items: [{ id: 96, name: "Active Life Therapy", client_type: "lead" }] };
      if (path === "/clients/96/media-buying/lead/table?include_days=false") return leadPayloadMonthsFirst();
      if (path === "/clients/96/media-buying/lead/month-days?month_start=2026-03-01") return monthDaysPayload();
      throw new Error(`Unexpected path ${path}`);
    });

    render(<SubMediaBuyingPage />);
    const monthButton = await screen.findByRole("button", { name: /Mar 2026/i });
    await screen.findByText("11 Mar");

    fireEvent.click(monthButton);
    expect(screen.queryByText("11 Mar")).toBeNull();
    fireEvent.click(monthButton);
    expect(await screen.findByText("11 Mar")).toBeInTheDocument();

    const monthCalls = apiMock.apiRequest.mock.calls.filter(([path]) => String(path).includes("/media-buying/lead/month-days"));
    expect(monthCalls).toHaveLength(1);
  });

  it("shows month-level error and allows retry without breaking the table", async () => {
    let monthAttempt = 0;
    apiMock.apiRequest.mockImplementation(async (path: string) => {
      if (path === "/clients") return { items: [{ id: 96, name: "Active Life Therapy", client_type: "lead" }] };
      if (path === "/clients/96/media-buying/lead/table?include_days=false") return leadPayloadMonthsFirst();
      if (path === "/clients/96/media-buying/lead/month-days?month_start=2026-03-01") {
        monthAttempt += 1;
        if (monthAttempt === 1) throw new Error("month boom");
        return monthDaysPayload();
      }
      throw new Error(`Unexpected path ${path}`);
    });

    render(<SubMediaBuyingPage />);
    expect(await screen.findByRole("button", { name: /Mar 2026/i })).toBeInTheDocument();
    expect(await screen.findByText("month boom")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /Retry/i }));
    expect(await screen.findByText("11 Mar")).toBeInTheDocument();
  });

});
