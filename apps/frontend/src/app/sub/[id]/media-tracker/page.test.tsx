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

function worksheetPayload(rate: number | null = 5.09) {
  return {
    eur_ron_rate: rate,
    eur_ron_rate_scope: { granularity: "month", period_start: "2026-03-01", period_end: "2026-03-31" },
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

  it("renders worksheet shell and EUR/RON value from payload", async () => {
    apiMock.apiRequest.mockImplementation(async (path: string) => {
      if (path === "/clients") return { items: [{ id: 96, name: "Active Life Therapy" }] };
      if (path.includes("/clients/96/media-tracker/worksheet-foundation")) return worksheetPayload(5.09);
      throw new Error(`Unexpected path ${path}`);
    });

    render(<SubMediaTrackerPage />);
    fireEvent.click(screen.getByRole("button", { name: "Weekly Worksheet" }));

    expect(await screen.findByRole("columnheader", { name: "Săptămâna" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "5.09" })).toBeInTheDocument();
    expect(screen.getByText("EUR/RON")).toBeInTheDocument();
  });

  it("renders clean placeholder when eur_ron_rate is null", async () => {
    apiMock.apiRequest.mockImplementation(async (path: string) => {
      if (path === "/clients") return { items: [{ id: 96, name: "Active Life Therapy" }] };
      if (path.includes("/clients/96/media-tracker/worksheet-foundation")) return worksheetPayload(null);
      throw new Error(`Unexpected path ${path}`);
    });

    render(<SubMediaTrackerPage />);
    fireEvent.click(screen.getByRole("button", { name: "Weekly Worksheet" }));
    await screen.findByRole("columnheader", { name: "Săptămâna" });

    expect(screen.getByRole("button", { name: "—" })).toBeInTheDocument();
  });

  it("submits EUR/RON save with correct payload for current scope", async () => {
    apiMock.apiRequest.mockImplementation(async (path: string, options?: RequestInit) => {
      if (path === "/clients") return { items: [{ id: 96, name: "Active Life Therapy" }] };
      if (path.includes("/clients/96/media-tracker/worksheet-foundation")) return worksheetPayload(5.09);
      if (path === "/clients/96/media-tracker/worksheet/eur-ron-rate") {
        expect(options?.method).toBe("PUT");
        const parsed = JSON.parse(String(options?.body || "{}"));
        expect(parsed.granularity).toBe("month");
        expect(typeof parsed.anchor_date).toBe("string");
        expect(parsed.value).toBe(5.2);
        return worksheetPayload(5.2);
      }
      throw new Error(`Unexpected path ${path}`);
    });

    render(<SubMediaTrackerPage />);
    fireEvent.click(screen.getByRole("button", { name: "Weekly Worksheet" }));
    await screen.findByRole("columnheader", { name: "Săptămâna" });

    fireEvent.click(screen.getByRole("button", { name: "5.09" }));
    const input = screen.getByDisplayValue("5.09");
    fireEvent.change(input, { target: { value: "5.2" } });
    fireEvent.keyDown(input, { key: "Enter" });

    await waitFor(() => {
      expect(apiMock.apiRequest).toHaveBeenCalledWith(
        "/clients/96/media-tracker/worksheet/eur-ron-rate",
        expect.objectContaining({ method: "PUT" })
      );
    });
    expect(screen.getByRole("button", { name: "5.20" })).toBeInTheDocument();
  });

  it("empty EUR/RON input sends null clear semantics", async () => {
    apiMock.apiRequest.mockImplementation(async (path: string, options?: RequestInit) => {
      if (path === "/clients") return { items: [{ id: 96, name: "Active Life Therapy" }] };
      if (path.includes("/clients/96/media-tracker/worksheet-foundation")) return worksheetPayload(5.09);
      if (path === "/clients/96/media-tracker/worksheet/eur-ron-rate") {
        const parsed = JSON.parse(String(options?.body || "{}"));
        expect(parsed.value).toBeNull();
        return worksheetPayload(null);
      }
      throw new Error(`Unexpected path ${path}`);
    });

    render(<SubMediaTrackerPage />);
    fireEvent.click(screen.getByRole("button", { name: "Weekly Worksheet" }));
    await screen.findByRole("columnheader", { name: "Săptămâna" });

    fireEvent.click(screen.getByRole("button", { name: "5.09" }));
    const input = screen.getByDisplayValue("5.09");
    fireEvent.change(input, { target: { value: " " } });
    fireEvent.keyDown(input, { key: "Enter" });

    await waitFor(() => expect(screen.getByRole("button", { name: "—" })).toBeInTheDocument());
  });

  it("EUR/RON save failure shows error and keeps edit value", async () => {
    apiMock.apiRequest.mockImplementation(async (path: string) => {
      if (path === "/clients") return { items: [{ id: 96, name: "Active Life Therapy" }] };
      if (path.includes("/clients/96/media-tracker/worksheet-foundation")) return worksheetPayload(5.09);
      if (path === "/clients/96/media-tracker/worksheet/eur-ron-rate") throw new Error("rate save failed");
      throw new Error(`Unexpected path ${path}`);
    });

    render(<SubMediaTrackerPage />);
    fireEvent.click(screen.getByRole("button", { name: "Weekly Worksheet" }));
    await screen.findByRole("columnheader", { name: "Săptămâna" });

    fireEvent.click(screen.getByRole("button", { name: "5.09" }));
    const input = screen.getByDisplayValue("5.09");
    fireEvent.change(input, { target: { value: "4.99" } });
    fireEvent.keyDown(input, { key: "Enter" });

    expect(await screen.findByText("rate save failed")).toBeInTheDocument();
    expect(screen.getByDisplayValue("4.99")).toBeInTheDocument();
  });

  it("manual weekly editing behavior remains intact", async () => {
    apiMock.apiRequest.mockImplementation(async (path: string, options?: RequestInit) => {
      if (path === "/clients") return { items: [{ id: 96, name: "Active Life Therapy" }] };
      if (path.includes("/clients/96/media-tracker/worksheet-foundation")) return worksheetPayload();
      if (path === "/clients/96/media-tracker/worksheet/manual-values") {
        const parsed = JSON.parse(String(options?.body || "{}"));
        expect(parsed.entries).toEqual([{ week_start: "2026-03-02", field_key: "weekly_cogs_taxes", value: 15.5 }]);
        return worksheetPayload();
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
