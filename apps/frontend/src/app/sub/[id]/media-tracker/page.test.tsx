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
            row_key: "ncac_eur",
            label: "nCAC EUR",
            value_kind: "currency_eur",
            source_kind: "computed",
            history_value: 12.5,
            weekly_values: [
              { week_start: "2026-03-02", week_end: "2026-03-08", value: 6.25 },
              { week_start: "2026-03-09", week_end: "2026-03-15", value: 6.25 },
            ],
          },
          {
            row_key: "leads",
            label: "Leads",
            value_kind: "integer",
            source_kind: "computed",
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
        key: "new_clients",
        label: "Clienți Noi",
        rows: [
          {
            row_key: "cost_per_new_client",
            label: "Cost per Client Nou",
            value_kind: "currency_ron",
            source_kind: "computed",
            history_value: 22,
            weekly_values: [
              { week_start: "2026-03-02", week_end: "2026-03-08", value: 10 },
              { week_start: "2026-03-09", week_end: "2026-03-15", value: 12 },
            ],
          },
        ],
      },
      {
        key: "google_spend",
        label: "Google Spend",
        rows: [
          {
            row_key: "cost",
            label: "Cost",
            value_kind: "currency_ron",
            source_kind: "computed",
            history_value: 70,
            weekly_values: [
              { week_start: "2026-03-02", week_end: "2026-03-08", value: 30 },
              { week_start: "2026-03-09", week_end: "2026-03-15", value: 40 },
            ],
          },
        ],
      },
      { key: "meta_spend", label: "Meta Spend", rows: [] },
      { key: "tiktok_spend", label: "TikTok Spend", rows: [] },
    ],
  };
}

describe("SubMediaTrackerPage", () => {
  beforeEach(() => {
    apiMock.apiRequest.mockReset();
  });

  it("opens Weekly Worksheet view without breaking existing overview", async () => {
    apiMock.apiRequest.mockImplementation(async (path: string) => {
      if (path === "/clients") return { items: [{ id: 96, name: "Active Life Therapy" }] };
      if (path.includes("/clients/96/media-tracker/worksheet-foundation")) return worksheetPayload();
      throw new Error(`Unexpected path ${path}`);
    });

    render(<SubMediaTrackerPage />);
    expect(screen.getByText("Coming Soon")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Weekly Worksheet" }));
    expect(await screen.findByRole("columnheader", { name: "Săptămâna" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Overview" })).toBeInTheDocument();
  });

  it("renders two-row worksheet header with Istorie before week columns in backend order", async () => {
    apiMock.apiRequest.mockImplementation(async (path: string) => {
      if (path === "/clients") return { items: [{ id: 96, name: "Active Life Therapy" }] };
      if (path.includes("/clients/96/media-tracker/worksheet-foundation")) return worksheetPayload();
      throw new Error(`Unexpected path ${path}`);
    });

    render(<SubMediaTrackerPage />);
    fireEvent.click(screen.getByRole("button", { name: "Weekly Worksheet" }));

    const headers = await screen.findAllByRole("columnheader");
    expect(headers.map((h) => h.textContent)).toEqual([
      "Săptămâna", "Istorie", "Săpt. 1", "Săpt. 2",
      "Data Începere", " ", "2026-03-02", "2026-03-09",
    ]);
  });

  it("renders section headers and rows in backend order, with comparison row immediately after source row", async () => {
    apiMock.apiRequest.mockImplementation(async (path: string) => {
      if (path === "/clients") return { items: [{ id: 96, name: "Active Life Therapy" }] };
      if (path.includes("/clients/96/media-tracker/worksheet-foundation")) return worksheetPayload();
      throw new Error(`Unexpected path ${path}`);
    });

    render(<SubMediaTrackerPage />);
    fireEvent.click(screen.getByRole("button", { name: "Weekly Worksheet" }));

    const sections = await screen.findAllByRole("cell", { name: /^(Rezumat|Clienți Noi|Google Spend|Meta Spend|TikTok Spend)$/ });
    expect(sections.map((n) => n.textContent)).toEqual(["Rezumat", "Clienți Noi", "Google Spend", "Meta Spend", "TikTok Spend"]);

    const rowLabels = screen.getAllByRole("cell", { name: /^(Cost|%|nCAC EUR|Leads|AOV|Cost per Client Nou)$/ }).map((n) => n.textContent);
    expect(rowLabels.slice(0, 6)).toEqual(["Cost", "%", "nCAC EUR", "Leads", "AOV", "Cost per Client Nou"]);
  });

  it("formats values by value_kind and shows null placeholder", async () => {
    apiMock.apiRequest.mockImplementation(async (path: string) => {
      if (path === "/clients") return { items: [{ id: 96, name: "Active Life Therapy" }] };
      if (path.includes("/clients/96/media-tracker/worksheet-foundation")) return worksheetPayload();
      throw new Error(`Unexpected path ${path}`);
    });

    render(<SubMediaTrackerPage />);
    fireEvent.click(screen.getByRole("button", { name: "Weekly Worksheet" }));

    expect((await screen.findAllByText(/RON/)).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/€/).length).toBeGreaterThan(0);
    expect(screen.getByText("100.00%")).toBeInTheDocument();
    expect(screen.getByText("30")).toBeInTheDocument();
    expect(screen.getByText("2.3457")).toBeInTheDocument();
    expect(screen.getAllByText("—").length).toBeGreaterThan(0);
  });

  it("granularity and previous/next controls still update worksheet request params", async () => {
    apiMock.apiRequest.mockImplementation(async (path: string) => {
      if (path === "/clients") return { items: [{ id: 96, name: "Active Life Therapy" }] };
      if (path.includes("/clients/96/media-tracker/worksheet-foundation")) return worksheetPayload();
      throw new Error(`Unexpected path ${path}`);
    });

    render(<SubMediaTrackerPage />);
    fireEvent.click(screen.getByRole("button", { name: "Weekly Worksheet" }));
    await screen.findByRole("columnheader", { name: "Săptămâna" });

    fireEvent.click(screen.getByRole("button", { name: "Previous" }));
    fireEvent.click(screen.getByRole("button", { name: "quarter" }));
    fireEvent.click(screen.getByRole("button", { name: "Next" }));

    await waitFor(() => {
      const calls = apiMock.apiRequest.mock.calls.map(([path]) => String(path)).filter((path) => path.includes("/worksheet-foundation"));
      expect(calls.some((path) => path.includes("granularity=quarter"))).toBe(true);
      const anchorValues = calls.map((path) => new URL(`http://local${path}`).searchParams.get("anchor_date"));
      expect(new Set(anchorValues).size).toBeGreaterThan(1);
    });
  });

  it("renders loading and error states for worksheet fetch", async () => {
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
