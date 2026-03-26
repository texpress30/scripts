import React from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import SubMediaTrackerPage from "./page";
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

function worksheetPayload(
  weeks: Array<{ week_start: string; week_end: string; label?: string }>,
  rate: number | null = 5.09,
  displayCurrency: string = "USD",
) {
  return {
    display_currency: displayCurrency,
    display_currency_source: "agency_client_currency",
    eur_ron_rate: rate,
    eur_ron_rate_scope: { granularity: "month", period_start: "2026-03-01", period_end: "2026-03-31" },
    weeks,
    sections: [
      {
        key: "summary",
        label: "Rezumat",
        rows: [
          {
            row_key: "cost",
            label: "Cost",
            value_kind: "currency_display",
            currency_code: displayCurrency,
            source_kind: "computed",
            history_value: 300,
            weekly_values: weeks.map((w, idx) => ({ week_start: w.week_start, week_end: w.week_end, value: idx + 100 })),
          },
          {
            row_key: "weekly_cogs_taxes",
            label: "Total COGS + Taxe",
            value_kind: "currency_display",
            currency_code: displayCurrency,
            source_kind: "manual",
            is_manual_input_row: true,
            dependencies: ["manual_metrics.weekly_cogs_taxes"],
            history_value: 30,
            weekly_values: weeks.map((w, idx) => ({ week_start: w.week_start, week_end: w.week_end, value: idx + 10 })),
          },
          {
            row_key: "ncac_eur",
            label: "nCAC EUR",
            value_kind: "currency_eur",
            currency_code: "EUR",
            source_kind: "computed",
            history_value: 20,
            weekly_values: weeks.map((w) => ({ week_start: w.week_start, week_end: w.week_end, value: 10 })),
          },
          {
            row_key: "cost_wow_pct",
            label: "%",
            value_kind: "percent_ratio",
            source_kind: "comparison",
            history_value: null,
            weekly_values: weeks.map((w, idx) => ({ week_start: w.week_start, week_end: w.week_end, value: idx === 0 ? null : 1.0 })),
          },
        ],
      },
      { key: "new_clients", label: "Clienți Noi", rows: [] },
      { key: "google_spend", label: "Cheltuieli Google", rows: [] },
      { key: "meta_spend", label: "Cheltuieli Meta", rows: [] },
      { key: "tiktok_spend", label: "Cheltuieli TikTok", rows: [] },
    ],
  };
}

const monthWeeks = [
  { week_start: "2026-03-02", week_end: "2026-03-08", label: "2026-03-02" },
  { week_start: "2026-03-09", week_end: "2026-03-15", label: "2026-03-09" },
];
const quarterWeeks = [
  { week_start: "2026-01-05", week_end: "2026-01-11", label: "2026-01-05" },
  { week_start: "2026-03-30", week_end: "2026-04-05", label: "2026-03-30" },
];
const yearWeeks = [
  { week_start: "2025-12-29", week_end: "2026-01-04", label: "2025-12-29" },
  { week_start: "2026-12-28", week_end: "2027-01-03", label: "2026-12-28" },
];

describe("SubMediaTrackerPage", () => {
  beforeEach(() => {
    apiMock.apiRequest.mockReset();
  });

  it("month/quarter/year headers show real ISO week numbers instead of local sequence", async () => {
    apiMock.apiRequest.mockImplementation(async (path: string) => {
      if (path === "/clients") return { items: [{ id: 96, name: "Active Life Therapy" }] };
      if (path.includes("/clients/96/media-tracker/worksheet-foundation")) {
        const url = new URL(`http://local${path}`);
        const granularity = url.searchParams.get("granularity");
        if (granularity === "quarter") return worksheetPayload(quarterWeeks);
        if (granularity === "year") return worksheetPayload(yearWeeks);
        return worksheetPayload(monthWeeks);
      }
      throw new Error(`Unexpected path ${path}`);
    });

    render(<SubMediaTrackerPage />);
    fireEvent.click(screen.getByRole("button", { name: "Fișă săptămânală" }));

    expect(await screen.findByRole("columnheader", { name: "Săpt. 10" })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "Săpt. 11" })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Trimestru" }));
    expect(await screen.findByRole("columnheader", { name: "Săpt. 2" })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "Săpt. 14" })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "An" }));
    expect(await screen.findByRole("columnheader", { name: "Săpt. 1" })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "Săpt. 53" })).toBeInTheDocument();
  });

  it("renders main Media Tracker UI texts in Romanian", async () => {
    apiMock.apiRequest.mockImplementation(async (path: string) => {
      if (path === "/clients") return { items: [{ id: 96, name: "Active Life Therapy" }] };
      if (path.includes("/clients/96/media-tracker/worksheet-foundation")) return worksheetPayload(monthWeeks);
      throw new Error(`Unexpected path ${path}`);
    });

    render(<SubMediaTrackerPage />);
    expect(screen.getByRole("button", { name: "Prezentare generală" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Fișă săptămânală" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Overview" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Weekly Worksheet" })).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "Fișă săptămânală" }));
    await screen.findByRole("columnheader", { name: "Săpt. 10" });
    expect(screen.getByRole("button", { name: "Lună" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Trimestru" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "An" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Anterior" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Următor" })).toBeInTheDocument();
    expect(screen.getByText("Monedă: USD")).toBeInTheDocument();
  });

  it("handles year-boundary week correctly (2025-12-29 => ISO week 1) and keeps row-2 dates", async () => {
    apiMock.apiRequest.mockImplementation(async (path: string) => {
      if (path === "/clients") return { items: [{ id: 96, name: "Active Life Therapy" }] };
      if (path.includes("/clients/96/media-tracker/worksheet-foundation")) return worksheetPayload(yearWeeks);
      throw new Error(`Unexpected path ${path}`);
    });

    render(<SubMediaTrackerPage />);
    fireEvent.click(screen.getByRole("button", { name: "Fișă săptămânală" }));

    expect(await screen.findByRole("columnheader", { name: "Săpt. 1" })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "2025-12-29" })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "2026-12-28" })).toBeInTheDocument();
  });

  it("applies dashed black vertical separators on header and body columns", async () => {
    apiMock.apiRequest.mockImplementation(async (path: string) => {
      if (path === "/clients") return { items: [{ id: 96, name: "Active Life Therapy" }] };
      if (path.includes("/clients/96/media-tracker/worksheet-foundation")) return worksheetPayload(monthWeeks);
      throw new Error(`Unexpected path ${path}`);
    });

    render(<SubMediaTrackerPage />);
    fireEvent.click(screen.getByRole("button", { name: "Fișă săptămânală" }));

    const weekHeader = await screen.findByRole("columnheader", { name: "Săpt. 10" });
    const dateHeader = screen.getByRole("columnheader", { name: "2026-03-02" });
    const bodyCell = screen.getByTestId("cell-summary-cost-2026-03-02");

    for (const node of [weekHeader, dateHeader, bodyCell]) {
      expect(node.className).toContain("border-dashed");
      expect(node.className).toContain("border-black");
      expect(node.className).toContain("border-r");
    }
  });

  it("allows editing EUR/RON, sends PUT, and refreshes worksheet", async () => {
    let worksheetCallCount = 0;
    apiMock.apiRequest.mockImplementation(async (path: string) => {
      if (path === "/clients") return { items: [{ id: 96, name: "Active Life Therapy" }] };
      if (path.includes("/clients/96/media-tracker/worksheet-foundation")) {
        worksheetCallCount += 1;
        return worksheetPayload(monthWeeks, worksheetCallCount > 1 ? 5.15 : 5.09);
      }
      if (path === "/clients/96/media-tracker/worksheet/eur-ron-rate") return worksheetPayload(monthWeeks, 5.15);
      throw new Error(`Unexpected path ${path}`);
    });

    render(<SubMediaTrackerPage />);
    fireEvent.click(screen.getByRole("button", { name: "Fișă săptămânală" }));
    await screen.findByRole("columnheader", { name: "Săpt. 10" });
    const rateInput = screen.getByLabelText("Curs EUR/RON");
    expect(rateInput).not.toHaveAttribute("disabled");
    fireEvent.change(rateInput, { target: { value: "5.15" } });
    fireEvent.click(screen.getByRole("button", { name: "Salvează curs" }));

    await screen.findByText("Cursul EUR/RON a fost salvat.");
    expect(screen.getByDisplayValue("5.15")).toBeInTheDocument();
    const rateCalls = apiMock.apiRequest.mock.calls.filter(([path]) => path === "/clients/96/media-tracker/worksheet/eur-ron-rate");
    expect(rateCalls.length).toBe(1);
    expect(rateCalls[0][1]?.method).toBe("PUT");
    const parsedBody = JSON.parse(String(rateCalls[0][1]?.body ?? "{}"));
    expect(parsedBody.granularity).toBe("month");
    expect(typeof parsedBody.anchor_date).toBe("string");
    expect(parsedBody.value).toBe(5.15);
  });

  it("worksheet business cells are read-only and page links to Data month context", async () => {
    apiMock.apiRequest.mockImplementation(async (path: string) => {
      if (path === "/clients") return { items: [{ id: 96, name: "Active Life Therapy" }] };
      if (path.includes("/clients/96/media-tracker/worksheet-foundation")) return worksheetPayload(monthWeeks);
      throw new Error(`Unexpected path ${path}`);
    });

    render(<SubMediaTrackerPage />);
    expect(screen.getByText("Valorile manuale se editează acum din pagina Data.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Deschide pagina Data" })).toHaveAttribute("href", "/sub/96/data?month=2026-03");
    fireEvent.click(screen.getByRole("button", { name: "Fișă săptămânală" }));
    await screen.findByRole("columnheader", { name: "Săpt. 10" });
    expect(screen.getByTestId("cell-summary-weekly_cogs_taxes-2026-03-02").querySelector("button")).toBeNull();
    const manualCalls = apiMock.apiRequest.mock.calls.filter(([path]) => path === "/clients/96/media-tracker/worksheet/manual-values");
    expect(manualCalls.length).toBe(0);
  });


  it("renders worksheet currency_display rows with page/row currency metadata and EUR rows in EUR", async () => {
    apiMock.apiRequest.mockImplementation(async (path: string) => {
      if (path === "/clients") return { items: [{ id: 96, name: "Active Life Therapy" }] };
      if (path.includes("/clients/96/media-tracker/worksheet-foundation")) return worksheetPayload(monthWeeks, 5.09, "USD");
      throw new Error(`Unexpected path ${path}`);
    });

    render(<SubMediaTrackerPage />);
    fireEvent.click(screen.getByRole("button", { name: "Fișă săptămânală" }));

    await screen.findByRole("columnheader", { name: "Săpt. 10" });
    expect(screen.getByText("Monedă: USD")).toBeInTheDocument();

    const historyCost = screen.getByTestId("history-summary-cost");
    expect(historyCost.textContent).toBe(formatCurrencyValue(300, "USD", "USD"));

    const eurCell = screen.getByTestId("cell-summary-ncac_eur-2026-03-02");
    expect(eurCell.textContent).toBe(formatCurrencyValue(10, "EUR", "EUR"));
  });

  it("loading and error states for worksheet fetch still work", async () => {
    let resolver: ((value: unknown) => void) | null = null;
    apiMock.apiRequest.mockImplementation((path: string) => {
      if (path === "/clients") return Promise.resolve({ items: [{ id: 96, name: "Active Life Therapy" }] });
      if (path.includes("/clients/96/media-tracker/worksheet-foundation")) {
        return new Promise((resolve) => {
          resolver = resolve;
        });
      }
      return Promise.reject(new Error(`Unexpected path ${path}`));
    });

    render(<SubMediaTrackerPage />);
    fireEvent.click(screen.getByRole("button", { name: "Fișă săptămânală" }));
    expect(screen.getByText("Se încarcă fișa săptămânală...")).toBeInTheDocument();

    resolver?.(worksheetPayload(monthWeeks));
    await screen.findByRole("columnheader", { name: "Săpt. 10" });

    apiMock.apiRequest.mockImplementation(async (path: string) => {
      if (path === "/clients") return { items: [{ id: 96, name: "Active Life Therapy" }] };
      if (path.includes("/clients/96/media-tracker/worksheet-foundation")) throw new Error("boom");
      throw new Error(`Unexpected path ${path}`);
    });

    fireEvent.click(screen.getByRole("button", { name: "Următor" }));
    expect(await screen.findByText("boom")).toBeInTheDocument();
  });
});
