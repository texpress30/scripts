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
    requested_scope: { granularity: "month", anchor_date: "2026-03-15" },
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
            history_value: 300,
            weekly_values: [
              { week_start: "2026-03-02", week_end: "2026-03-08", value: 100 },
              { week_start: "2026-03-09", week_end: "2026-03-15", value: 200 },
            ],
          },
          {
            row_key: "cost_wow_pct",
            label: "%",
            history_value: null,
            weekly_values: [
              { week_start: "2026-03-02", week_end: "2026-03-08", value: null },
              { week_start: "2026-03-09", week_end: "2026-03-15", value: 1.0 },
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
            history_value: 70,
            weekly_values: [
              { week_start: "2026-03-02", week_end: "2026-03-08", value: 30 },
              { week_start: "2026-03-09", week_end: "2026-03-15", value: 40 },
            ],
          },
        ],
      },
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
    expect(await screen.findByRole("columnheader", { name: "Istorie" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Overview" })).toBeInTheDocument();
  });

  it("granularity switch changes worksheet request parameters", async () => {
    apiMock.apiRequest.mockImplementation(async (path: string) => {
      if (path === "/clients") return { items: [{ id: 96, name: "Active Life Therapy" }] };
      if (path.includes("/clients/96/media-tracker/worksheet-foundation")) return worksheetPayload();
      throw new Error(`Unexpected path ${path}`);
    });

    render(<SubMediaTrackerPage />);
    fireEvent.click(screen.getByRole("button", { name: "Weekly Worksheet" }));
    await screen.findByRole("columnheader", { name: "Istorie" });

    fireEvent.click(screen.getByRole("button", { name: "quarter" }));

    await waitFor(() => {
      const calls = apiMock.apiRequest.mock.calls.map(([path]) => String(path));
      expect(calls.some((path) => path.includes("granularity=quarter"))).toBe(true);
    });
  });

  it("previous/next navigation changes anchor_date by month/quarter/year", async () => {
    apiMock.apiRequest.mockImplementation(async (path: string) => {
      if (path === "/clients") return { items: [{ id: 96, name: "Active Life Therapy" }] };
      if (path.includes("/clients/96/media-tracker/worksheet-foundation")) return worksheetPayload();
      throw new Error(`Unexpected path ${path}`);
    });

    render(<SubMediaTrackerPage />);
    fireEvent.click(screen.getByRole("button", { name: "Weekly Worksheet" }));
    await screen.findByRole("columnheader", { name: "Istorie" });

    fireEvent.click(screen.getByRole("button", { name: "Previous" }));
    fireEvent.click(screen.getByRole("button", { name: "quarter" }));
    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    fireEvent.click(screen.getByRole("button", { name: "year" }));
    fireEvent.click(screen.getByRole("button", { name: "Next" }));

    await waitFor(() => {
      const calls = apiMock.apiRequest.mock.calls.map(([path]) => String(path)).filter((path) => path.includes("/worksheet-foundation"));
      expect(calls.length).toBeGreaterThan(3);
      const anchorValues = calls.map((path) => new URL(`http://local${path}`).searchParams.get("anchor_date"));
      const granularityValues = calls.map((path) => new URL(`http://local${path}`).searchParams.get("granularity"));
      expect(granularityValues).toContain("month");
      expect(granularityValues).toContain("quarter");
      expect(granularityValues).toContain("year");
      expect(new Set(anchorValues).size).toBeGreaterThan(2);
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
    await screen.findByRole("columnheader", { name: "Istorie" });

    apiMock.apiRequest.mockImplementation(async (path: string) => {
      if (path === "/clients") return { items: [{ id: 96, name: "Active Life Therapy" }] };
      if (path.includes("/clients/96/media-tracker/worksheet-foundation")) throw new Error("boom");
      throw new Error(`Unexpected path ${path}`);
    });

    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    expect(await screen.findByText("boom")).toBeInTheDocument();
  });

  it("renders sections, rows, and week columns in backend order with history first, including percent rows", async () => {
    apiMock.apiRequest.mockImplementation(async (path: string) => {
      if (path === "/clients") return { items: [{ id: 96, name: "Active Life Therapy" }] };
      if (path.includes("/clients/96/media-tracker/worksheet-foundation")) return worksheetPayload();
      throw new Error(`Unexpected path ${path}`);
    });

    render(<SubMediaTrackerPage />);
    fireEvent.click(screen.getByRole("button", { name: "Weekly Worksheet" }));

    const headers = await screen.findAllByRole("columnheader");
    expect(headers.map((h) => h.textContent)).toEqual(["Row", "Istorie", "2026-03-02", "2026-03-09"]);

    const rezumatCell = screen.getByRole("cell", { name: "Rezumat" });
    const googleCell = screen.getByRole("cell", { name: "Google Spend" });
    expect(rezumatCell.compareDocumentPosition(googleCell) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();

    const rowLabels = screen.getAllByRole("cell", { name: /^(Cost|%)$/ }).map((n) => n.textContent);
    expect(rowLabels.slice(0, 3)).toEqual(["Cost", "%", "Cost"]);
  });
});
