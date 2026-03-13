import React from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import SubMediaTrackerPage from "./page";

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

function worksheetPayload() {
  return {
    weeks: [
      { week_start: "2026-03-02", week_end: "2026-03-08", label: "2026-03-02" },
      { week_start: "2026-03-09", week_end: "2026-03-15", label: "2026-03-09" },
    ],
    sections: [
      {
        key: "summary",
        label: "Rezumat",
        rows: [
          {
            row_key: "cost",
            label: "Cost",
            value_kind: "currency_ron",
            source_kind: "computed",
            history_value: 300,
            weekly_values: [
              { week_start: "2026-03-02", week_end: "2026-03-08", value: 100 },
              { week_start: "2026-03-09", week_end: "2026-03-15", value: 200 },
            ],
          },
          {
            row_key: "cost_wow_pct",
            label: "%",
            value_kind: "percent_ratio",
            source_kind: "comparison",
            history_value: null,
            weekly_values: [
              { week_start: "2026-03-02", week_end: "2026-03-08", value: null },
              { week_start: "2026-03-09", week_end: "2026-03-15", value: 1.0 },
            ],
          },
          {
            row_key: "weekly_cogs_taxes",
            label: "Total COGS + Taxe",
            value_kind: "currency_ron",
            source_kind: "manual",
            is_manual_input_row: true,
            dependencies: ["manual_metrics.weekly_cogs_taxes"],
            history_value: 30,
            weekly_values: [
              { week_start: "2026-03-02", week_end: "2026-03-08", value: 10 },
              { week_start: "2026-03-09", week_end: "2026-03-15", value: 20 },
            ],
          },
          {
            row_key: "aov",
            label: "AOV",
            value_kind: "decimal",
            source_kind: "computed",
            history_value: 2.34567,
            weekly_values: [
              { week_start: "2026-03-02", week_end: "2026-03-08", value: 1.23456 },
              { week_start: "2026-03-09", week_end: "2026-03-15", value: null },
            ],
          },
        ],
      },
      {
        key: "google_spend",
        label: "Google Spend",
        rows: [
          {
            row_key: "leads_manual",
            label: "Leads",
            value_kind: "integer",
            source_kind: "manual",
            is_manual_input_row: true,
            dependencies: ["manual_metrics.google_leads_manual"],
            history_value: 7,
            weekly_values: [
              { week_start: "2026-03-02", week_end: "2026-03-08", value: 3 },
              { week_start: "2026-03-09", week_end: "2026-03-15", value: 4 },
            ],
          },
          {
            row_key: "cpa",
            label: "CPA",
            value_kind: "currency_ron",
            source_kind: "computed",
            history_value: 11,
            weekly_values: [
              { week_start: "2026-03-02", week_end: "2026-03-08", value: 5 },
              { week_start: "2026-03-09", week_end: "2026-03-15", value: 6 },
            ],
          },
        ],
      },
      { key: "new_clients", label: "Clienți Noi", rows: [] },
      { key: "meta_spend", label: "Meta Spend", rows: [] },
      { key: "tiktok_spend", label: "TikTok Spend", rows: [] },
    ],
  };
}

describe("SubMediaTrackerPage", () => {
  beforeEach(() => {
    apiMock.apiRequest.mockReset();
  });

  it("renders worksheet header/order and keeps overview switch", async () => {
    apiMock.apiRequest.mockImplementation(async (path: string) => {
      if (path === "/clients") return { items: [{ id: 96, name: "Active Life Therapy" }] };
      if (path.includes("/clients/96/media-tracker/worksheet-foundation")) return worksheetPayload();
      throw new Error(`Unexpected path ${path}`);
    });

    render(<SubMediaTrackerPage />);
    expect(screen.getByText("Coming Soon")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Weekly Worksheet" }));
    const headers = await screen.findAllByRole("columnheader");
    expect(headers.map((h) => h.textContent)).toEqual([
      "Săptămâna", "Istorie", "Săpt. 1", "Săpt. 2",
      "Data Începere", " ", "2026-03-02", "2026-03-09",
    ]);
    expect(screen.getByRole("button", { name: "Overview" })).toBeInTheDocument();
  });

  it("only manual weekly cells are editable; history/computed/comparison remain read-only", async () => {
    apiMock.apiRequest.mockImplementation(async (path: string) => {
      if (path === "/clients") return { items: [{ id: 96, name: "Active Life Therapy" }] };
      if (path.includes("/clients/96/media-tracker/worksheet-foundation")) return worksheetPayload();
      throw new Error(`Unexpected path ${path}`);
    });

    render(<SubMediaTrackerPage />);
    fireEvent.click(screen.getByRole("button", { name: "Weekly Worksheet" }));
    await screen.findByRole("columnheader", { name: "Săptămâna" });

    fireEvent.click(screen.getByTestId("cell-summary-weekly_cogs_taxes-2026-03-02").querySelector("button")!);
    expect(screen.getByDisplayValue("10")).toBeInTheDocument();

    fireEvent.click(screen.getByTestId("cell-summary-cost-2026-03-02"));
    expect(screen.queryByDisplayValue("100")).toBeNull();

    fireEvent.click(screen.getByTestId("cell-summary-cost_wow_pct-2026-03-09"));
    expect(screen.queryByDisplayValue("1")).toBeNull();

    fireEvent.click(screen.getByTestId("history-summary-weekly_cogs_taxes"));
    expect(screen.queryByDisplayValue("30")).toBeNull();
  });

  it("submits manual cell edit with correct PUT payload", async () => {
    apiMock.apiRequest.mockImplementation(async (path: string, options?: RequestInit) => {
      if (path === "/clients") return { items: [{ id: 96, name: "Active Life Therapy" }] };
      if (path.includes("/clients/96/media-tracker/worksheet-foundation")) return worksheetPayload();
      if (path === "/clients/96/media-tracker/worksheet/manual-values") {
        expect(options?.method).toBe("PUT");
        const parsed = JSON.parse(String(options?.body || "{}"));
        expect(parsed.granularity).toBe("month");
        expect(typeof parsed.anchor_date).toBe("string");
        expect(parsed.entries).toEqual([{ week_start: "2026-03-02", field_key: "weekly_cogs_taxes", value: 15.5 }]);
        const payload = worksheetPayload();
        payload.sections[0].rows[2].weekly_values[0].value = 15.5;
        payload.sections[0].rows[2].history_value = 35.5;
        return payload;
      }
      throw new Error(`Unexpected path ${path}`);
    });

    render(<SubMediaTrackerPage />);
    fireEvent.click(screen.getByRole("button", { name: "Weekly Worksheet" }));
    await screen.findByRole("columnheader", { name: "Săptămâna" });

    fireEvent.click(screen.getByTestId("cell-summary-weekly_cogs_taxes-2026-03-02").querySelector("button")!);
    const input = screen.getByDisplayValue("10");
    fireEvent.change(input, { target: { value: "15.5" } });
    fireEvent.keyDown(input, { key: "Enter" });

    await waitFor(() => {
      expect(apiMock.apiRequest).toHaveBeenCalledWith(
        "/clients/96/media-tracker/worksheet/manual-values",
        expect.objectContaining({ method: "PUT" })
      );
    });
  });

  it("empty input sends null clear semantics", async () => {
    apiMock.apiRequest.mockImplementation(async (path: string, options?: RequestInit) => {
      if (path === "/clients") return { items: [{ id: 96, name: "Active Life Therapy" }] };
      if (path.includes("/clients/96/media-tracker/worksheet-foundation")) return worksheetPayload();
      if (path === "/clients/96/media-tracker/worksheet/manual-values") {
        const parsed = JSON.parse(String(options?.body || "{}"));
        expect(parsed.entries).toEqual([{ week_start: "2026-03-02", field_key: "weekly_cogs_taxes", value: null }]);
        const payload = worksheetPayload();
        payload.sections[0].rows[2].weekly_values[0].value = null;
        return payload;
      }
      throw new Error(`Unexpected path ${path}`);
    });

    render(<SubMediaTrackerPage />);
    fireEvent.click(screen.getByRole("button", { name: "Weekly Worksheet" }));
    await screen.findByRole("columnheader", { name: "Săptămâna" });

    fireEvent.click(screen.getByTestId("cell-summary-weekly_cogs_taxes-2026-03-02").querySelector("button")!);
    const input = screen.getByDisplayValue("10");
    fireEvent.change(input, { target: { value: "   " } });
    fireEvent.keyDown(input, { key: "Enter" });

    await screen.findAllByText("—");
  });

  it("save failure keeps edit mode and shows inline error", async () => {
    apiMock.apiRequest.mockImplementation(async (path: string) => {
      if (path === "/clients") return { items: [{ id: 96, name: "Active Life Therapy" }] };
      if (path.includes("/clients/96/media-tracker/worksheet-foundation")) return worksheetPayload();
      if (path === "/clients/96/media-tracker/worksheet/manual-values") throw new Error("save failed");
      throw new Error(`Unexpected path ${path}`);
    });

    render(<SubMediaTrackerPage />);
    fireEvent.click(screen.getByRole("button", { name: "Weekly Worksheet" }));
    await screen.findByRole("columnheader", { name: "Săptămâna" });

    fireEvent.click(screen.getByTestId("cell-summary-weekly_cogs_taxes-2026-03-02").querySelector("button")!);
    const input = screen.getByDisplayValue("10");
    fireEvent.change(input, { target: { value: "22" } });
    fireEvent.keyDown(input, { key: "Enter" });

    expect(await screen.findByText("save failed")).toBeInTheDocument();
    expect(screen.getByDisplayValue("22")).toBeInTheDocument();
  });

  it("loading and error state for worksheet fetch still work", async () => {
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
    fireEvent.click(screen.getByRole("button", { name: "Weekly Worksheet" }));
    expect(screen.getByText("Loading worksheet...")).toBeInTheDocument();

    resolver?.(worksheetPayload());
    await screen.findByRole("columnheader", { name: "Săptămâna" });

    apiMock.apiRequest.mockImplementation(async (path: string) => {
      if (path === "/clients") return { items: [{ id: 96, name: "Active Life Therapy" }] };
      if (path.includes("/clients/96/media-tracker/worksheet-foundation")) throw new Error("boom");
      throw new Error(`Unexpected path ${path}`);
    });

    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    expect(await screen.findByText("boom")).toBeInTheDocument();
  });
});
