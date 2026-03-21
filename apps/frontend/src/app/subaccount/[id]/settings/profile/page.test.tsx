import React from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";

import SubAccountSettingsPage from "./page";
import { apiRequest } from "@/lib/api";

vi.mock("next/navigation", () => ({ useParams: () => ({ id: "96" }) }));
vi.mock("@/lib/api", () => ({ apiRequest: vi.fn() }));
vi.mock("@/components/ProtectedPage", () => ({ ProtectedPage: ({ children }: { children: React.ReactNode }) => <>{children}</> }));
vi.mock("@/components/AppShell", () => ({
  AppShell: ({ children, title }: { children: React.ReactNode; title: React.ReactNode }) => (
    <div>
      <div data-testid="app-shell-title">{String(title ?? "")}</div>
      {children}
    </div>
  ),
}));

type Store = {
  general: Record<string, unknown>;
  business: Record<string, unknown>;
  address: Record<string, unknown>;
  representative: Record<string, unknown>;
  logo_url: string;
};

describe("SubAccount Business Profile settings page", () => {
  beforeEach(() => {
    vi.useRealTimers();
    window.localStorage.clear();
  });

  function setupApiMock(initial?: Partial<Store>) {
    const db: Store = {
      general: {},
      business: {},
      address: {},
      representative: {},
      logo_url: "",
      ...(initial ?? {}),
    };

    vi.mocked(apiRequest).mockImplementation(async (path: string, options?: RequestInit) => {
      if (path === "/clients/96/business-profile" && (!options || !options.method || options.method === "GET")) {
        return {
          client_name: "Client 96",
          client_id: 1,
          display_id: 96,
          general: db.general,
          business: db.business,
          address: db.address,
          representative: db.representative,
          logo_url: db.logo_url,
        };
      }
      if (path === "/clients/96/business-profile" && options?.method === "PUT") {
        const payload = JSON.parse(String(options.body ?? "{}")) as Store;
        db.general = payload.general ?? {};
        db.business = payload.business ?? {};
        db.address = payload.address ?? {};
        db.representative = payload.representative ?? {};
        db.logo_url = String(payload.logo_url ?? "");
        return {
          client_name: "Client 96",
          client_id: 1,
          display_id: 96,
          general: db.general,
          business: db.business,
          address: db.address,
          representative: db.representative,
          logo_url: db.logo_url,
        };
      }
      throw new Error(`Unexpected path ${path}`);
    });
  }

  it("starts with empty form values when business profile is not saved, even if display data exists", async () => {
    setupApiMock();
    render(<SubAccountSettingsPage />);

    expect(await screen.findByTestId("app-shell-title")).toHaveTextContent("Client 96 — Profil Business");
    expect(screen.getByLabelText(/Nume business \(friendly\)/i)).toHaveValue("");
    expect(screen.getByLabelText(/Email business/i)).toHaveValue("");
    expect(screen.getByLabelText(/Oraș/i)).toHaveValue("");
    expect(screen.queryByText("Logo salvat")).not.toBeInTheDocument();
    expect(screen.getByRole("option", { name: "Parc Auto" })).toBeInTheDocument();

    const nicheOptions = Array.from(screen.getByLabelText(/Nișa business/i).querySelectorAll("option")).map((opt) => opt.textContent);
    expect(nicheOptions).toEqual([
      "Selectează",
      "Agenție de marketing",
      "E-commerce",
      "Estetică Medicală",
      "Ortopedie",
      "Parc Auto",
      "Recuperare Medicală",
      "SaaS",
      "Stomatologie",
    ]);

    const industryOptions = Array.from(screen.getByLabelText(/Industrie/i).querySelectorAll("option")).map((opt) => opt.textContent);
    expect(industryOptions).toEqual([
      "Selectează",
      "Auto",
      "Dating",
      "Educație",
      "Energie",
      "Marketing",
      "Media",
      "Retail",
      "Servicii Medicale",
    ]);
  });

  it("saves profile explicitly and reloads saved values from business-profile endpoint", async () => {
    setupApiMock();
    const { unmount } = render(<SubAccountSettingsPage />);
    await screen.findByTestId("app-shell-title");

    fireEvent.change(screen.getByLabelText(/Nume business \(friendly\)/i), { target: { value: "ROC Auto" } });
    fireEvent.change(screen.getByLabelText(/Denumire legală business/i), { target: { value: "ROC Auto SRL" } });
    fireEvent.change(screen.getByLabelText(/Email business/i), { target: { value: "biz@roc.example" } });
    fireEvent.change(screen.getByLabelText(/Telefon business/i), { target: { value: "+40 700 111 222" } });
    fireEvent.change(screen.getByLabelText(/Website business/i), { target: { value: "https://roc.example" } });
    fireEvent.change(screen.getByLabelText(/Nișa business/i), { target: { value: "parc_auto" } });
    fireEvent.change(screen.getByLabelText(/Monedă business/i), { target: { value: "EUR" } });
    fireEvent.change(screen.getByLabelText(/Oraș/i), { target: { value: "Onești" } });
    fireEvent.click(screen.getAllByRole("button", { name: "Actualizează informațiile" })[0]);
    await screen.findByText("Informațiile generale au fost actualizate.");

    expect(vi.mocked(apiRequest)).toHaveBeenCalledWith(
      "/clients/96/business-profile",
      expect.objectContaining({ method: "PUT" }),
    );

    unmount();
    render(<SubAccountSettingsPage />);
    await screen.findByTestId("app-shell-title");

    expect(screen.getByLabelText(/Nume business \(friendly\)/i)).toHaveValue("ROC Auto");
    expect(screen.getByLabelText(/Email business/i)).toHaveValue("biz@roc.example");
    expect(screen.getByLabelText(/Oraș/i)).toHaveValue("Onești");
    expect(screen.getByLabelText(/Nișa business/i)).toHaveValue("parc_auto");
  });

  it("does not use localStorage snapshots as permanent prefill source", async () => {
    window.localStorage.setItem(
      "subaccount_profile_settings_96",
      JSON.stringify({
        general: { friendlyName: "From localStorage", email: "ls@example.com" },
        address: { city: "Storage City" },
      }),
    );
    setupApiMock();
    render(<SubAccountSettingsPage />);
    await screen.findByTestId("app-shell-title");

    expect(screen.getByLabelText(/Nume business \(friendly\)/i)).toHaveValue("");
    expect(screen.getByLabelText(/Email business/i)).toHaveValue("");
    expect(screen.getByLabelText(/Oraș/i)).toHaveValue("");
  });
});
