import React from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import SubDataPage from "./page";

const apiMock = vi.hoisted(() => ({ apiRequest: vi.fn() }));
const routerMock = vi.hoisted(() => ({ replace: vi.fn() }));
const searchState = vi.hoisted(() => ({ month: "2026-03" }));

vi.mock("@/lib/api", () => ({ apiRequest: apiMock.apiRequest }));
vi.mock("next/navigation", () => ({
  useParams: () => ({ id: "96" }),
  useRouter: () => routerMock,
  useSearchParams: () => ({
    get: (key: string) => (key === "month" ? searchState.month : null),
    toString: () => (searchState.month ? `month=${searchState.month}` : ""),
  }),
}));
vi.mock("@/components/ProtectedPage", () => ({ ProtectedPage: ({ children }: { children: React.ReactNode }) => <>{children}</> }));
vi.mock("@/components/AppShell", () => ({
  AppShell: ({ children, title }: { children: React.ReactNode; title: React.ReactNode }) => (
    <div>
      <div data-testid="app-shell-title">{title === null ? "" : String(title ?? "")}</div>
      {children}
    </div>
  ),
}));

describe("SubDataPage", () => {
  beforeEach(() => {
    apiMock.apiRequest.mockReset();
    routerMock.replace.mockReset();
    searchState.month = "2026-03";

    apiMock.apiRequest.mockImplementation(async (path: string) => {
      if (path === "/clients") {
        return { items: [{ id: 96, name: "Active Life Therapy" }] };
      }
      if (path === "/clients/96/data/config") {
        return {
          currency_code: "RON",
          fixed_fields: [
            { key: "leads", label: "Lead-uri" },
            { key: "phones", label: "Telefoane" },
            { key: "custom_value_1_count", label: "CV1" },
            { key: "custom_value_2_count", label: "CV2" },
            { key: "custom_value_3_amount", label: "CV3" },
            { key: "custom_value_4_amount", label: "CV4 derivat" },
            { key: "custom_value_5_amount", label: "CV5" },
          ],
          dynamic_custom_fields: [
            { id: 11, field_key: "appointments", label: "Appointments", value_kind: "count", sort_order: 1, is_active: true },
            { id: 12, field_key: "inactive_field", label: "Inactive", value_kind: "amount", sort_order: 2, is_active: false },
          ],
        };
      }
      if (path.includes("/clients/96/data/table")) {
        return {
          rows: [
            {
              metric_date: "2026-03-11",
              source_label: "Meta",
              leads: 12,
              phones: 5,
              custom_value_1_count: 1,
              custom_value_2_count: 2,
              custom_value_3_amount: 100,
              custom_value_5_amount: 55,
              notes: "note",
              derived: {
                sales_count: 2,
                revenue_amount: 500,
                cogs_amount: 300,
                custom_value_4_amount: 500,
                gross_profit_amount: 200,
              },
              sale_entries: [
                {
                  brand: "Toyota",
                  model: "Corolla",
                  sale_price_amount: 250,
                  actual_price_amount: 150,
                  gross_profit_amount: 100,
                  notes: "s1",
                },
              ],
              dynamic_custom_values: [
                { custom_field_id: 11, label: "Appointments", value_kind: "count", numeric_value: 7 },
                { custom_field_id: 12, label: "Inactive", value_kind: "amount", numeric_value: 999 },
              ],
            },
          ],
        };
      }
      throw new Error(`Unhandled path ${path}`);
    });
  });

  it("renders read-only data table with active dynamic columns and details", async () => {
    render(<SubDataPage />);

    expect(screen.getByText("Loading data table...")).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "Data - Active Life Therapy" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Data" })).toHaveAttribute("href", "/sub/96/data");
    expect(screen.getByText("CV4 derivat")).toBeInTheDocument();
    expect(screen.getByText("Appointments")).toBeInTheDocument();
    expect(screen.queryByRole("columnheader", { name: "Inactive" })).toBeNull();
    expect(screen.getByText("Meta")).toBeInTheDocument();
    expect(screen.getByText("note")).toBeInTheDocument();
    expect(screen.getByText("View")).toBeInTheDocument();

    fireEvent.click(screen.getByText("View"));
    expect(await screen.findByText("Toyota")).toBeInTheDocument();
    expect(screen.getByText(/Inactive:/)).toBeInTheDocument();
  });

  it("updates URL month parameter via Previous/Next controls", async () => {
    render(<SubDataPage />);

    await screen.findByRole("heading", { name: "Data - Active Life Therapy" });
    fireEvent.click(screen.getByRole("button", { name: "Previous" }));
    expect(routerMock.replace).toHaveBeenCalledWith(expect.stringContaining("month=2026-02"));

    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    expect(routerMock.replace).toHaveBeenCalledWith(expect.stringContaining("month=2026-04"));
  });

  it("shows clear empty state", async () => {
    apiMock.apiRequest.mockImplementationOnce(async () => ({ items: [{ id: 96, name: "Active Life Therapy" }] }));
    apiMock.apiRequest.mockImplementationOnce(async () => ({ currency_code: "RON", fixed_fields: [], dynamic_custom_fields: [] }));
    apiMock.apiRequest.mockImplementationOnce(async () => ({ rows: [] }));

    render(<SubDataPage />);
    expect(await screen.findByText("Nu există date pentru perioada selectată.")).toBeInTheDocument();
  });

  it("shows clear error state", async () => {
    apiMock.apiRequest.mockReset();
    apiMock.apiRequest.mockRejectedValue(new Error("boom"));
    render(<SubDataPage />);
    await waitFor(() => expect(screen.getByText("boom")).toBeInTheDocument());
  });
});
