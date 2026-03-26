import React from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";

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
  apiMock.apiRequest.mockImplementation(async (path: string, options?: RequestInit) => {
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
          { id: 12, field_key: "inactive", label: "Inactive", value_kind: "amount", sort_order: 2, is_active: false },
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
            custom_value_5_amount: 55,
            notes: "note",
            derived: { sales_count: 1, revenue_amount: 500, cogs_amount: 300, custom_value_4_amount: 500, gross_profit_amount: 200 },
            sale_entries: [
              { id: 901, brand: "Toyota", model: "Corolla", sale_price_amount: 250, actual_price_amount: 150, gross_profit_amount: 100, notes: "s1" },
            ],
            dynamic_custom_values: [
              { custom_field_id: 11, label: "Appointments", value_kind: "count", numeric_value: 7 },
              { custom_field_id: 12, label: "Inactive", value_kind: "amount", numeric_value: 999, is_active: false },
            ],
          },
        ],
      };
    }
    if (path === "/clients/96/data/daily-input") return { id: 101 };
    if (path === "/clients/96/data/sale-entries") return { id: 990 };
    if (path === "/clients/96/data/sale-entries/901") return { id: 901 };
    if (path === "/clients/96/data/custom-fields") {
      if ((options?.method || "GET") === "POST") return { id: 600 };
      return {
        items: [
          { id: 11, field_key: "appointments", label: "Appointments", value_kind: "count", sort_order: 1, is_active: true, archived_at: null },
        ],
      };
    }
    if (path === "/clients/96/data/custom-fields?include_inactive=true") {
      return {
        items: [
          { id: 11, field_key: "appointments", label: "Appointments", value_kind: "count", sort_order: 1, is_active: true, archived_at: null },
          { id: 12, field_key: "inactive", label: "Inactive", value_kind: "amount", sort_order: 2, is_active: false, archived_at: "2026-03-01T10:00:00Z" },
        ],
      };
    }
    if (path === "/clients/96/data/custom-fields/11") return { id: 11 };
    if (path === "/clients/96/data/custom-fields/11/archive") return { id: 11 };
    throw new Error(`Unhandled path ${path}`);
  });
}

describe("SubDataPage editable flows", () => {
  beforeEach(() => {
    apiMock.apiRequest.mockReset();
    routerMock.replace.mockReset();
    searchState.month = "2026-03";
    vi.stubGlobal("confirm", vi.fn(() => true));
    setupApiMock();
  });

  it("shows Add row and saves a new daily row via PUT", async () => {
    render(<SubDataPage />);
    await screen.findByRole("heading", { name: "Data - Active Life Therapy" });
    expect(screen.getByText("Valorile salvate aici alimentează Media Buying și Media Tracker.")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Adaugă rând" }));
    expect(screen.getByLabelText("Săptămâna rând nou")).toHaveValue("9");
    expect(screen.getByLabelText("Custom Value 4 rând nou")).toHaveValue("");
    expect(screen.getByLabelText("Vânzări rând nou")).toHaveValue("");
    expect(screen.getByLabelText("P/L brut rând nou 1")).toHaveValue("");
    fireEvent.change(screen.getByLabelText("Data rând nou"), { target: { value: "2026-03-12" } });
    expect(screen.getByLabelText("Săptămâna rând nou")).toHaveValue("11");
    fireEvent.change(screen.getByLabelText("Sursa rând nou"), { target: { value: "meta_ads" } });
    fireEvent.change(screen.getByLabelText("Lead-uri rând nou"), { target: { value: "10" } });
    fireEvent.change(screen.getByLabelText("Custom Value 4 rând nou"), { target: { value: "250" } });
    fireEvent.change(screen.getByLabelText("Vânzări rând nou"), { target: { value: "3" } });
    fireEvent.change(screen.getByLabelText("Preț vânzare rând nou 1"), { target: { value: "250" } });
    expect(screen.getByLabelText("Custom Value 4 rând nou")).toHaveValue("250");
    expect(screen.getByLabelText("Vânzări rând nou")).toHaveValue("3");
    fireEvent.change(screen.getByLabelText("Preț actual rând nou 1"), { target: { value: "150" } });
    fireEvent.change(screen.getByLabelText("New row cv3"), { target: { value: "500" } });
    fireEvent.change(screen.getByLabelText("Dynamic field Appointments rând nou"), { target: { value: "7" } });
    expect(screen.getByLabelText("New row cv5")).toHaveValue("250,00 RON");
    fireEvent.click(screen.getByRole("button", { name: "Salvează rând" }));

    await waitFor(() => {
      expect(apiMock.apiRequest).toHaveBeenCalledWith(
        "/clients/96/data/daily-input",
        expect.objectContaining({
          method: "PUT",
          body: expect.stringContaining('"dynamic_custom_values":[{"custom_field_id":11,"numeric_value":7}]'),
        }),
      );
    });

    await waitFor(() => {
      expect(apiMock.apiRequest).toHaveBeenCalledWith(
        "/clients/96/data/sale-entries",
        expect.objectContaining({ method: "POST", body: expect.stringContaining('"daily_input_id":101') }),
      );
    });
  });

  it("keeps add-row fields labeled, week first, no placeholders, and saves daily row only when sale section is empty", async () => {
    render(<SubDataPage />);
    await screen.findByRole("heading", { name: "Data - Active Life Therapy" });
    fireEvent.click(screen.getByRole("button", { name: "Adaugă rând" }));

    const addRowTitle = screen.getByRole("heading", { name: "Adaugă rând" });
    const addRowSection = addRowTitle.parentElement as HTMLElement;
    const addRowGrid = addRowTitle.parentElement?.querySelector(".grid");
    expect(addRowGrid).toBeTruthy();
    const fieldLabels = Array.from(addRowGrid?.querySelectorAll("label") ?? []).map((node) => node.textContent?.trim());
    expect(fieldLabels[0]).toBe("Săptămâna");
    expect(fieldLabels.slice(0, 5)).toEqual(["Săptămâna", "Data vânzare", "Sursa", "Lead-uri", "Telefoane"]);

    expect(screen.getByLabelText("Data rând nou")).toBeInTheDocument();
    expect(screen.getByLabelText("Sursa rând nou")).toBeInTheDocument();
    expect(screen.getByLabelText("Lead-uri rând nou")).toBeInTheDocument();
    expect(screen.getByLabelText("New row phones")).toBeInTheDocument();
    expect(screen.getByLabelText("New row cv1")).toBeInTheDocument();
    expect(screen.getByLabelText("New row cv2")).toBeInTheDocument();
    expect(screen.getByLabelText("New row cv3")).toBeInTheDocument();
    expect(screen.getByLabelText("Custom Value 4 rând nou")).toBeInTheDocument();
    expect(screen.getByLabelText("New row cv5")).toBeInTheDocument();
    expect(screen.getByLabelText("New row notes")).toBeInTheDocument();
    expect(screen.getByLabelText("Marcă rând nou 1")).toBeInTheDocument();
    expect(screen.getByLabelText("Model rând nou 1")).toBeInTheDocument();
    expect(screen.getByLabelText("Preț vânzare rând nou 1")).toBeInTheDocument();
    expect(screen.getByLabelText("Preț actual rând nou 1")).toBeInTheDocument();
    expect(screen.getByLabelText("P/L brut rând nou 1")).toBeInTheDocument();

    expect(within(addRowSection).getByText("Mențiuni")).toBeInTheDocument();
    expect(within(addRowSection).getByText("Lead-uri")).toBeInTheDocument();
    expect(within(addRowSection).getByText("Telefoane")).toBeInTheDocument();
    expect(within(addRowSection).getByText("CV1")).toBeInTheDocument();
    expect(within(addRowSection).getByText("CV2")).toBeInTheDocument();
    expect(within(addRowSection).getByText("CV3")).toBeInTheDocument();
    expect(within(addRowSection).getByText("CV4")).toBeInTheDocument();
    expect(within(addRowSection).getByText("CV5")).toBeInTheDocument();

    expect(screen.getByLabelText("Lead-uri rând nou")).not.toHaveAttribute("placeholder");
    expect(screen.getByLabelText("New row phones")).not.toHaveAttribute("placeholder");
    expect(screen.getByLabelText("New row cv1")).not.toHaveAttribute("placeholder");
    expect(screen.getByLabelText("Preț vânzare rând nou 1")).not.toHaveAttribute("placeholder");
    expect(screen.getByLabelText("P/L brut rând nou 1")).toHaveValue("");
    expect(screen.getByLabelText("Custom Value 4 rând nou")).toHaveValue("");
    expect(screen.getByLabelText("Vânzări rând nou")).toHaveValue("");

    fireEvent.change(screen.getByLabelText("Data rând nou"), { target: { value: "2026-03-12" } });
    fireEvent.change(screen.getByLabelText("Sursa rând nou"), { target: { value: "meta_ads" } });
    fireEvent.change(screen.getByLabelText("Lead-uri rând nou"), { target: { value: "9" } });
    fireEvent.click(screen.getByRole("button", { name: "Salvează rând" }));

    await waitFor(() => {
      expect(apiMock.apiRequest).toHaveBeenCalledWith(
        "/clients/96/data/daily-input",
        expect.objectContaining({ method: "PUT", body: expect.stringContaining('"leads":9') }),
      );
    });
    expect(
      apiMock.apiRequest.mock.calls.some((call: any[]) => call[0] === "/clients/96/data/sale-entries"),
    ).toBe(false);
  });

  it("edits existing row and persists dynamic_custom_values via daily-input save", async () => {
    render(<SubDataPage />);
    await screen.findByText("Meta");

    const row = screen.getByText("Meta").closest("tr");
    expect(row).toBeTruthy();
    fireEvent.click(within(row as HTMLTableRowElement).getAllByRole("button", { name: "Editează" })[0]);
    fireEvent.change(screen.getByLabelText(/Editează leads/), { target: { value: "14" } });
    fireEvent.click(screen.getByRole("button", { name: /^Save$/ }));

    await waitFor(() => {
      expect(apiMock.apiRequest).toHaveBeenCalledWith(
        "/clients/96/data/daily-input",
        expect.objectContaining({ method: "PUT", body: expect.stringContaining('"leads":14') }),
      );
    });

    const dailyInputCall = apiMock.apiRequest.mock.calls.find((call: any[]) => call[0] === "/clients/96/data/daily-input");
    expect(dailyInputCall).toBeTruthy();
    expect(String(dailyInputCall?.[1]?.body || "")).toContain('"dynamic_custom_values":[{"custom_field_id":11,"numeric_value":7}]');
  });

  it("sends dynamic_custom_values as empty array when dynamic fields are blank", async () => {
    render(<SubDataPage />);
    await screen.findByRole("heading", { name: "Data - Active Life Therapy" });
    fireEvent.click(screen.getByRole("button", { name: "Adaugă rând" }));
    fireEvent.change(screen.getByLabelText("Data rând nou"), { target: { value: "2026-03-12" } });
    fireEvent.change(screen.getByLabelText("Sursa rând nou"), { target: { value: "meta_ads" } });
    fireEvent.change(screen.getByLabelText("Lead-uri rând nou"), { target: { value: "10" } });
    fireEvent.click(screen.getByRole("button", { name: "Salvează rând" }));

    await waitFor(() => {
      expect(apiMock.apiRequest).toHaveBeenCalledWith(
        "/clients/96/data/daily-input",
        expect.objectContaining({ method: "PUT", body: expect.stringContaining('"dynamic_custom_values":[]') }),
      );
    });
  });

  it("saves multiple sale_entries from add-row main form", async () => {
    render(<SubDataPage />);
    await screen.findByRole("heading", { name: "Data - Active Life Therapy" });
    fireEvent.click(screen.getByRole("button", { name: "Adaugă rând" }));

    fireEvent.change(screen.getByLabelText("Data rând nou"), { target: { value: "2026-03-12" } });
    fireEvent.change(screen.getByLabelText("Sursa rând nou"), { target: { value: "meta_ads" } });
    fireEvent.change(screen.getByLabelText("Lead-uri rând nou"), { target: { value: "10" } });
    fireEvent.change(screen.getByLabelText("Preț vânzare rând nou 1"), { target: { value: "200" } });
    fireEvent.change(screen.getByLabelText("Preț actual rând nou 1"), { target: { value: "150" } });

    fireEvent.click(screen.getByRole("button", { name: "Adaugă încă o vânzare" }));
    fireEvent.change(screen.getByLabelText("Marcă rând nou 2"), { target: { value: "VW" } });
    fireEvent.change(screen.getByLabelText("Model rând nou 2"), { target: { value: "Golf" } });
    fireEvent.change(screen.getByLabelText("Preț vânzare rând nou 2"), { target: { value: "300" } });
    fireEvent.change(screen.getByLabelText("Preț actual rând nou 2"), { target: { value: "210" } });

    fireEvent.click(screen.getByRole("button", { name: "Salvează rând" }));

    await waitFor(() => {
      const saleCalls = apiMock.apiRequest.mock.calls.filter((call: any[]) => call[0] === "/clients/96/data/sale-entries" && call[1]?.method === "POST");
      expect(saleCalls).toHaveLength(2);
      expect(String(saleCalls[0][1].body)).toContain('"daily_input_id":101');
      expect(String(saleCalls[1][1].body)).toContain('"brand":"VW"');
    });
  });

  it("adds, edits and deletes sale entries through POST/PATCH/DELETE", async () => {
    render(<SubDataPage />);
    await screen.findByText("Vezi");
    fireEvent.click(screen.getByText("Vezi"));

    fireEvent.click(screen.getByRole("button", { name: "Adaugă vânzare" }));
    fireEvent.change(screen.getByLabelText(/Adaugă vânzare brand/), { target: { value: "Opel" } });
    fireEvent.change(screen.getByLabelText(/Adaugă vânzare price/), { target: { value: "200" } });
    fireEvent.click(screen.getByRole("button", { name: "Salvează vânzarea" }));

    await waitFor(() => expect(apiMock.apiRequest).toHaveBeenCalledWith(
      "/clients/96/data/sale-entries",
      expect.objectContaining({ method: "POST" }),
    ));

    fireEvent.click(screen.getAllByRole("button", { name: "Editează" })[1]);
    fireEvent.change(screen.getByLabelText(/Editează sale price 901/), { target: { value: "300" } });
    fireEvent.click(screen.getByRole("button", { name: /^Save$/ }));

    await waitFor(() => expect(apiMock.apiRequest).toHaveBeenCalledWith(
      "/clients/96/data/sale-entries/901",
      expect.objectContaining({ method: "PATCH" }),
    ));

    fireEvent.click(screen.getByRole("button", { name: "Șterge" }));
    await waitFor(() => expect(apiMock.apiRequest).toHaveBeenCalledWith(
      "/clients/96/data/sale-entries/901",
      expect.objectContaining({ method: "DELETE" }),
    ));
  });

  it("opens manager, lists fields, creates, updates and archives custom fields", async () => {
    render(<SubDataPage />);
    await screen.findByText("Gestionează câmpuri custom");
    fireEvent.click(screen.getByRole("button", { name: "Gestionează câmpuri custom" }));
    await screen.findByText("Appointments · appointments · count · sort: 1");

    fireEvent.change(screen.getByLabelText("New field label"), { target: { value: "Followups" } });
    fireEvent.change(screen.getByLabelText("New field type"), { target: { value: "count" } });
    fireEvent.click(screen.getByRole("button", { name: "Creează câmp" }));

    await waitFor(() => expect(apiMock.apiRequest).toHaveBeenCalledWith(
      "/clients/96/data/custom-fields",
      expect.objectContaining({ method: "POST" }),
    ));

    fireEvent.click(screen.getAllByRole("button", { name: "Editează" })[0]);
    fireEvent.change(screen.getByLabelText("Editează label 11"), { target: { value: "Appointments Updated" } });
    fireEvent.click(screen.getByRole("button", { name: /^Save$/ }));

    await waitFor(() => expect(apiMock.apiRequest).toHaveBeenCalledWith(
      "/clients/96/data/custom-fields/11",
      expect.objectContaining({ method: "PATCH" }),
    ));

    fireEvent.click(screen.getByRole("button", { name: "Arhivează" }));
    await waitFor(() => expect(apiMock.apiRequest).toHaveBeenCalledWith(
      "/clients/96/data/custom-fields/11/archive",
      expect.objectContaining({ method: "POST" }),
    ));
  });

  it("toggles include_inactive and renders archived field read-only", async () => {
    render(<SubDataPage />);
    await screen.findByRole("button", { name: "Gestionează câmpuri custom" });
    fireEvent.click(screen.getByRole("button", { name: "Gestionează câmpuri custom" }));
    await screen.findByText("Appointments · appointments · count · sort: 1");

    fireEvent.click(screen.getByLabelText("Afișează și arhivate"));
    await screen.findByText("Inactive · inactive · amount · sort: 2 · arhivat");
    const editButtons = screen.getAllByRole("button", { name: "Editează" });
    expect(editButtons[1]).toBeDisabled();
  });

  it("shows custom-fields API error state in manager", async () => {
    apiMock.apiRequest.mockImplementation(async (path: string, options?: RequestInit) => {
      if (path === "/clients") return { items: [{ id: 96, name: "Active Life Therapy" }] };
      if (path === "/clients/96/data/config") return { currency_code: "RON", sources: [] };
      if (String(path).startsWith("/clients/96/data/table")) return { rows: [] };
      if (path.startsWith("/clients/96/data/custom-fields")) throw new Error("boom custom fields");
      throw new Error(`Unhandled path ${path}`);
    });

    render(<SubDataPage />);
    await screen.findByRole("button", { name: "Gestionează câmpuri custom" });
    fireEvent.click(screen.getByRole("button", { name: "Gestionează câmpuri custom" }));
    await screen.findByText("boom custom fields");
  });
});
