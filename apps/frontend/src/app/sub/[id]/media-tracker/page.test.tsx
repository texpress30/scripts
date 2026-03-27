import React from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import SubMediaTrackerPage from "./page";

const apiMock = vi.hoisted(() => ({ apiRequest: vi.fn() }));

vi.mock("@/lib/api", () => ({ apiRequest: apiMock.apiRequest }));
vi.mock("next/navigation", () => ({ useParams: () => ({ id: "96" }) }));
vi.mock("@/components/ProtectedPage", () => ({ ProtectedPage: ({ children }: { children: React.ReactNode }) => <>{children}</> }));
vi.mock("@/components/AppShell", () => ({
  AppShell: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}));

class ResizeObserverMock {
  observe() {}
  unobserve() {}
  disconnect() {}
}
vi.stubGlobal("ResizeObserver", ResizeObserverMock);

const monthWeeks = [
  { week_start: "2026-03-02", week_end: "2026-03-08", label: "2026-03-02" },
  { week_start: "2026-03-09", week_end: "2026-03-15", label: "2026-03-09" },
];

function worksheetPayload(rate: number | null = 5.09) {
  return {
    display_currency: "RON",
    eur_ron_rate: rate,
    weeks: monthWeeks,
    sections: [
      {
        key: "summary",
        label: "Rezumat",
        rows: [
          {
            row_key: "cost",
            label: "Cost",
            value_kind: "currency_display",
            source_kind: "computed",
            history_value: 300,
            weekly_values: monthWeeks.map((w, idx) => ({ week_start: w.week_start, week_end: w.week_end, value: idx + 100 })),
          },
        ],
      },
    ],
  };
}

function overviewPayload() {
  return {
    display_currency: "RON",
    weeks: monthWeeks,
    custom_labels: {
      custom_label_1: "Aplicații",
      custom_label_2: "Aplicații aprobate",
      custom_label_3: "Val. Aprobată",
      custom_label_4: "Val. Vândută",
      custom_label_5: "Val. Nerealizată",
    },
    sales: {
      total_sales_trend: monthWeeks.map((w, i) => ({ ...w, label: w.label, revenue_total: 1000 + i * 200 })),
      channel_sales_composition: monthWeeks.map((w, i) => ({ ...w, label: w.label, google: 300 + i, meta: 200 + i, tiktok: 100 + i })),
      sales_efficiency_scatter: [
        { week_start: monthWeeks[0].week_start, week_end: monthWeeks[0].week_end, label: monthWeeks[0].label, channel: "google", cost: 100, sold_value: 400 },
      ],
    },
    financial: {
      cost_efficiency: monthWeeks.map((w) => ({ ...w, label: w.label, google_cpa: 10, google_ncac: 20, meta_cpa: 11, meta_ncac: 21, tiktok_cpa: 12, tiktok_ncac: 22 })),
      spend_vs_revenue_mix: monthWeeks.map((w) => ({ ...w, label: w.label, google_cost: 100, meta_cost: 80, tiktok_cost: 60, revenue_total: 400 })),
      conversion_funnel: monthWeeks.map((w) => ({ ...w, label: w.label, leads: 50, custom_value_1_count: 20, custom_value_2_count: 10, sales: 5 })),
      profitability: monthWeeks.map((w) => ({ ...w, label: w.label, gross_profit: 200, cogs_taxes: 120 })),
      cost_per_new_client: monthWeeks.map((w) => ({ ...w, label: w.label, cost_per_new_client: 350 })),
      channel_performance: [
        { channel: "google", cpa: 10, conversion_rate: 0.2, sales_volume: 15 },
        { channel: "meta", cpa: 11, conversion_rate: 0.18, sales_volume: 11 },
        { channel: "tiktok", cpa: 12, conversion_rate: 0.17, sales_volume: 9 },
      ],
    },
  };
}

describe("SubMediaTrackerPage", () => {
  beforeEach(() => {
    apiMock.apiRequest.mockReset();
    apiMock.apiRequest.mockImplementation(async (path: string) => {
      if (path === "/clients") return { items: [{ id: 96, name: "Active Life Therapy" }] };
      if (path.includes("/clients/96/media-tracker/overview-charts")) return overviewPayload();
      if (path.includes("/clients/96/media-tracker/worksheet-foundation")) return worksheetPayload();
      if (path === "/clients/96/media-tracker/worksheet/eur-ron-rate") return worksheetPayload(5.15);
      throw new Error(`Unexpected path ${path}`);
    });
  });

  it("renders top-level tabs Vânzări, Financiare, Fișă săptămânală", async () => {
    render(<SubMediaTrackerPage />);
    expect(screen.getByRole("button", { name: "Vânzări" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Financiare" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Fișă săptămânală" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Prezentare generală" })).toBeNull();
    await screen.findByLabelText("Trendul Vânzărilor Totale");
    expect(screen.getByRole("button", { name: /Last 30 days:/i })).toBeInTheDocument();
  });

  it("switches between Vânzări and Financiare and keeps selected calendar range for charts", async () => {
    render(<SubMediaTrackerPage />);
    await screen.findByLabelText("Trendul Vânzărilor Totale");
    fireEvent.click(screen.getByRole("button", { name: "Financiare" }));

    await screen.findByLabelText("Analiza Eficienței Costurilor (CPA și nCAC)");

    const overviewCalls = apiMock.apiRequest.mock.calls
      .map(([path]) => String(path))
      .filter((path) => path.includes("/clients/96/media-tracker/overview-charts"));
    expect(overviewCalls.some((path) => path.includes("granularity=year"))).toBe(true);
  });

  it("uses custom labels from payload in financial conversion funnel legend/title context", async () => {
    render(<SubMediaTrackerPage />);
    fireEvent.click(screen.getByRole("button", { name: "Financiare" }));
    await screen.findByLabelText("Analiza Pâlniei de Conversie");
    expect(screen.getByText("Analiza Pâlniei de Conversie")).toBeInTheDocument();
  });

  it("worksheet tab remains functional including EUR/RON save", async () => {
    render(<SubMediaTrackerPage />);
    fireEvent.click(screen.getByRole("button", { name: "Fișă săptămânală" }));
    await screen.findByRole("button", { name: "Salvează curs" });

    fireEvent.change(screen.getByLabelText("Curs EUR/RON"), { target: { value: "5.15" } });
    fireEvent.click(screen.getByRole("button", { name: "Salvează curs" }));

    await screen.findByText("Cursul EUR/RON a fost salvat.");
    const rateCalls = apiMock.apiRequest.mock.calls.filter(([path]) => path === "/clients/96/media-tracker/worksheet/eur-ron-rate");
    expect(rateCalls.length).toBe(1);
    expect(rateCalls[0][1]?.method).toBe("PUT");
  });

  it("renders required charts in Vânzări and Financiare", async () => {
    render(<SubMediaTrackerPage />);
    await screen.findByLabelText("Trendul Vânzărilor Totale");
    expect(screen.getByLabelText("Compoziția Vânzărilor pe Canale")).toBeInTheDocument();
    expect(screen.getByLabelText("Eficiența Vânzărilor")).toBeInTheDocument();
    expect(screen.getByLabelText("Aplicații / Aplicații Aprobate / Vânzări")).toBeInTheDocument();
    expect(screen.getByLabelText("Aprobări / Vânzări")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Financiare" }));
    await screen.findByLabelText("Analiza Pâlniei de Conversie");
    expect(screen.queryByLabelText("Analiza Mixului de Cheltuieli vs. Venituri")).toBeNull();
    expect(screen.getByLabelText("Profitabilitatea")).toBeInTheDocument();
    expect(screen.getByLabelText("Analiza Performanței pe Canale")).toBeInTheDocument();
    expect(screen.getByLabelText("Cost per Client Nou")).toBeInTheDocument();
  });

  it("shows worksheet loading/error states", async () => {
    let throwNextWorksheet = false;
    apiMock.apiRequest.mockImplementation(async (path: string) => {
      if (path === "/clients") return { items: [{ id: 96, name: "Active Life Therapy" }] };
      if (path.includes("/clients/96/media-tracker/overview-charts")) return overviewPayload();
      if (path.includes("/clients/96/media-tracker/worksheet-foundation")) {
        if (throwNextWorksheet) throw new Error("boom");
        return worksheetPayload();
      }
      if (path === "/clients/96/media-tracker/worksheet/eur-ron-rate") return worksheetPayload(5.15);
      throw new Error(`Unexpected path ${path}`);
    });

    render(<SubMediaTrackerPage />);
    fireEvent.click(screen.getByRole("button", { name: "Fișă săptămânală" }));
    await screen.findByRole("button", { name: "Salvează curs" });

    throwNextWorksheet = true;
    fireEvent.click(screen.getByRole("button", { name: "Următor" }));
    await screen.findByText("boom");
  });
});
