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

describe("SubAccount Business Profile settings page", () => {
  beforeEach(() => {
    vi.useRealTimers();
    window.localStorage.clear();
    vi.mocked(apiRequest).mockReset();
    vi.mocked(apiRequest).mockResolvedValue({
      client: { name: "Client 96", owner_email: "owner96@example.com", currency: "eur", client_logo_url: "" },
    });
  });

  it("renders all required business profile sections in Romanian", () => {
    render(<SubAccountSettingsPage />);

    expect(screen.getByText("Informații generale")).toBeInTheDocument();
    expect(screen.getByText("Informații business")).toBeInTheDocument();
    expect(screen.getByText("Adresă fizică business")).toBeInTheDocument();
    expect(screen.getByText("Reprezentant autorizat")).toBeInTheDocument();

    expect(screen.getByLabelText(/Nume business \(friendly\)/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Denumire legală business/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Email business/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Website business/i)).toBeInTheDocument();
  });

  it("validates general information fields and shows success toast on valid submit", async () => {
    render(<SubAccountSettingsPage />);
    await screen.findByDisplayValue("owner96@example.com");

    fireEvent.change(screen.getByLabelText(/Email business/i), { target: { value: "email_invalid" } });
    fireEvent.change(screen.getByLabelText(/Website business/i), { target: { value: "site-invalid" } });
    fireEvent.change(screen.getByLabelText(/Telefon business/i), { target: { value: "123" } });

    fireEvent.click(screen.getAllByRole("button", { name: "Actualizează informațiile" })[0]);

    expect(screen.getByText(/adresă de email validă/i)).toBeInTheDocument();
    expect(screen.getByText(/url valid/i)).toBeInTheDocument();
    expect(screen.getByText(/număr de telefon valid/i)).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText(/Email business/i), { target: { value: "admin@omarosa.ro" } });
    fireEvent.change(screen.getByLabelText(/Website business/i), { target: { value: "https://omarosa.ro" } });
    fireEvent.change(screen.getByLabelText(/Telefon business/i), { target: { value: "+40 725 083 012" } });

    fireEvent.click(screen.getAllByRole("button", { name: "Actualizează informațiile" })[0]);

    expect(await screen.findByText("Informațiile generale au fost actualizate.")).toBeInTheDocument();
  });

  it("loads profile defaults from API and persists general updates via PATCH", async () => {
    render(<SubAccountSettingsPage />);

    expect((await screen.findAllByDisplayValue("Client 96")).length).toBeGreaterThan(0);
    expect(screen.getByDisplayValue("owner96@example.com")).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText(/Nume business \(friendly\)/i), { target: { value: "Client 96 Updated" } });
    fireEvent.click(screen.getAllByRole("button", { name: "Actualizează informațiile" })[0]);

    expect(vi.mocked(apiRequest)).toHaveBeenCalledWith(
      "/clients/display/96",
      expect.objectContaining({
        method: "PATCH",
        body: expect.stringContaining("\"name\":\"Client 96 Updated\""),
      }),
    );
  });
});
