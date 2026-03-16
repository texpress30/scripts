import React from "react";
import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";

import SubAccountTeamPage from "./page";

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

describe("SubAccount Team management page", () => {
  it("renders listing view with filters, search, actions, and pagination", () => {
    render(<SubAccountTeamPage />);

    expect(screen.getByRole("heading", { name: "Echipa Mea" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Adaugă Utilizator/i })).toBeInTheDocument();
    expect(screen.getByRole("combobox")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("Nume, email, telefon, id-uri")).toBeInTheDocument();

    expect(screen.getByRole("columnheader", { name: "Nume" })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "Email" })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "Telefon" })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "Tip Utilizator" })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "Acțiuni" })).toBeInTheDocument();

    expect(screen.getByRole("button", { name: "Anterior" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Următor" })).toBeInTheDocument();
  });

  it("shows toast on copy id and opens direct add/edit form flow", () => {
    render(<SubAccountTeamPage />);

    fireEvent.click(screen.getAllByRole("button", { name: /Copiere ID:/i })[0]);
    expect(screen.getByText("ID Copiat")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /Adaugă Utilizator/i }));
    expect(screen.getByRole("button", { name: "← Înapoi" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Informații Utilizator" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Roluri și Permisiuni" })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Anulează" }));
    fireEvent.click(screen.getByRole("button", { name: /Editează Ana Ionescu/i }));

    expect(screen.getByDisplayValue("Ana")).toBeInTheDocument();
    expect(screen.getByDisplayValue("Ionescu")).toBeInTheDocument();
    expect(screen.getByDisplayValue("ana.ionescu@acme.ro")).toBeInTheDocument();
  });

  it("validates required fields, email format, extension numeric, and advanced password toggle", () => {
    render(<SubAccountTeamPage />);
    fireEvent.click(screen.getByRole("button", { name: /Adaugă Utilizator/i }));

    expect(screen.queryByPlaceholderText("Parolă")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /Setări Avansate/i }));
    expect(screen.getByPlaceholderText("Parolă")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Înainte" }));
    expect(screen.getByText("Prenumele este obligatoriu.")).toBeInTheDocument();
    expect(screen.getByText("Numele este obligatoriu.")).toBeInTheDocument();
    expect(screen.getByText("Email-ul este obligatoriu.")).toBeInTheDocument();

    fireEvent.change(screen.getByPlaceholderText("Prenume"), { target: { value: "Ana" } });
    fireEvent.change(screen.getByPlaceholderText("Nume"), { target: { value: "Ionescu" } });
    fireEvent.change(screen.getByPlaceholderText("Email"), { target: { value: "email_invalid" } });
    fireEvent.change(screen.getByPlaceholderText("Extensie"), { target: { value: "abc" } });
    fireEvent.click(screen.getByRole("button", { name: "Înainte" }));

    expect(screen.getByText("Introdu o adresă de email validă.")).toBeInTheDocument();
    expect(screen.getByText("Extensia trebuie să fie numerică.")).toBeInTheDocument();

    fireEvent.change(screen.getByPlaceholderText("Email"), { target: { value: "ana@acme.ro" } });
    fireEvent.change(screen.getByPlaceholderText("Extensie"), { target: { value: "123" } });
    fireEvent.click(screen.getByRole("button", { name: "Înainte" }));

    expect(screen.getByRole("heading", { name: "Echipa Mea" })).toBeInTheDocument();
    expect(screen.getByText("Utilizator adăugat.")).toBeInTheDocument();
  });
});
