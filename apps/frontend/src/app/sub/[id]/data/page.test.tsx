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

function setupApiMock() {
  apiMock.apiRequest.mockImplementation(async (path: string) => {
    if (path === "/clients") return { items: [{ id: 96, name: "Active Life Therapy" }] };
    if (path === "/clients/96/data/config") {
      return {
        currency_code: "RON",
        sources: [
          { key: "meta_ads", label: "Meta" },
          { key: "google_ads", label: "Google" },
        ],
        fixed_fields: [
          { key: "leads", label: "Lead-uri" },
          { key: "phones", label: "Telefoane" },
          { key: "custom_value_1_count", label: "CV1" },
          { key: "custom_value_2_count", label: "CV2" },
          { key: "custom_value_3_amount", label: "CV3" },
          { key: "custom_value_4_amount", label: "CV4" },
          { key: "custom_value_5_amount", label: "CV5" },
        ],
        dynamic_custom_fields: [
          { id: 11, field_key: "appointments", label: "Appointments", value_kind: "count", sort_order: 1, is_active: true },
        ],
      };
    }
    if (path.includes("/clients/96/data/table")) {
      return {
        rows: [
          {
            daily_input_id: 101,
            metric_date: "2026-03-11",
            source: "meta_ads",
            source_label: "Meta",
            leads: 12,
            phones: 5,
            custom_value_1_count: 1,
            custom_value_2_count: 2,
            custom_value_3_amount: 100,
            custom_value_4_amount: 80,
            custom_value_5_amount: 20,
            sales_count: 1,
            gross_profit_amount: 50,
            dynamic_custom_values: [
              { custom_field_id: 11, label: "Appointments", value_kind: "count", numeric_value: 7 },
            ],
          },
        ],
      };
    }
    if (path === "/clients/96/data/daily-input") return { id: 101 };
    if (path.startsWith("/clients/96/data/custom-fields")) return { items: [] };
    throw new Error(`Unhandled path ${path}`);
  });
}

describe("SubDataPage canonical-only UI", () => {
  beforeEach(() => {
    apiMock.apiRequest.mockReset();
    routerMock.replace.mockReset();
    searchState.month = "2026-03";
    setupApiMock();
  });

  it("removes interactive sales/notes controls from Data page", async () => {
    render(<SubDataPage />);
    await screen.findByRole("heading", { name: "Data - Active Life Therapy" });

    expect(screen.queryByText("Șterge vânzarea")).not.toBeInTheDocument();
    expect(screen.queryByText("Adaugă încă o vânzare")).not.toBeInTheDocument();
    expect(screen.queryByText("Adaugă vânzare")).not.toBeInTheDocument();
    expect(screen.queryByText("Mențiuni")).not.toBeInTheDocument();
  });

  it("saves canonical daily payload (date/source/fixed fields/dynamic custom values) and keeps source validation", async () => {
    render(<SubDataPage />);
    await screen.findByRole("heading", { name: "Data - Active Life Therapy" });

    fireEvent.click(screen.getByRole("button", { name: "Adaugă rând" }));
    fireEvent.click(screen.getByRole("button", { name: "Salvează rând" }));
    await screen.findByText("Selectează o sursă validă înainte de salvare.");

    fireEvent.change(screen.getByLabelText("Data rând nou"), { target: { value: "2026-03-12" } });
    fireEvent.change(screen.getByLabelText("Sursa rând nou"), { target: { value: "meta_ads" } });
    fireEvent.change(screen.getByLabelText("Lead-uri rând nou"), { target: { value: "9" } });
    fireEvent.change(screen.getByLabelText("New row phones"), { target: { value: "4" } });
    fireEvent.change(screen.getByLabelText("New row cv1"), { target: { value: "2" } });
    fireEvent.change(screen.getByLabelText("New row cv2"), { target: { value: "1" } });
    fireEvent.change(screen.getByLabelText("New row cv3"), { target: { value: "120" } });
    fireEvent.change(screen.getByLabelText("Dynamic field Appointments rând nou"), { target: { value: "6" } });
    fireEvent.click(screen.getByRole("button", { name: "Salvează rând" }));

    await waitFor(() => {
      expect(apiMock.apiRequest).toHaveBeenCalledWith(
        "/clients/96/data/daily-input",
        expect.objectContaining({
          method: "PUT",
          body: expect.stringContaining('"dynamic_custom_values":[{"custom_field_id":11,"numeric_value":6}]'),
        }),
      );
    });

    const putCall = apiMock.apiRequest.mock.calls.find((call: any[]) => call[0] === "/clients/96/data/daily-input");
    const putBody = String(putCall?.[1]?.body || "");
    expect(putBody).toContain('"metric_date":"2026-03-12"');
    expect(putBody).toContain('"source":"meta_ads"');
    expect(putBody).not.toContain("sale_entries");
    expect(putBody).not.toContain("notes");
  });
});
