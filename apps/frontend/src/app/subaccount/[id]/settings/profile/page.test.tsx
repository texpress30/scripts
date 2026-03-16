import React from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";

import SubAccountSettingsPage from "./page";

vi.mock("next/navigation", () => ({ useParams: () => ({ id: "96" }) }));
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
    vi.useFakeTimers();
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

  it("validates general information fields and shows success toast on valid submit", () => {
    render(<SubAccountSettingsPage />);

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

    expect(screen.getByText("Informațiile generale au fost actualizate.")).toBeInTheDocument();
  });
});
