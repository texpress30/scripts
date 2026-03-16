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

describe("SubAccount Team user form", () => {
  it("renders left tabs and user info form in Romanian", () => {
    render(<SubAccountTeamPage />);

    expect(screen.getByRole("button", { name: "← Înapoi" })).toBeInTheDocument();
    expect(screen.getByText("Editează sau gestionează echipa ta.")).toBeInTheDocument();

    expect(screen.getByRole("button", { name: "Informații Utilizator" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Roluri și Permisiuni" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Setări Apeluri și Mesaje Vocale" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Disponibilitate Utilizator" })).toBeInTheDocument();

    expect(screen.getByText("Imagine Profil")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("Prenume")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("Nume")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("Email")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("Telefon")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("Extensie")).toBeInTheDocument();
    expect(screen.getByText("Semnătură Utilizator")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Anulează" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Înainte" })).toBeInTheDocument();
  });

  it("keeps advanced settings collapsed by default, toggles password field, and validates required fields", () => {
    render(<SubAccountTeamPage />);

    expect(screen.queryByPlaceholderText("Parolă")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /Setări Avansate/i }));
    expect(screen.getByPlaceholderText("Parolă")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Înainte" }));
    expect(screen.getByText("Prenumele este obligatoriu.")).toBeInTheDocument();
    expect(screen.getByText("Numele este obligatoriu.")).toBeInTheDocument();
    expect(screen.getByText("Email-ul este obligatoriu.")).toBeInTheDocument();

    fireEvent.change(screen.getByPlaceholderText("Prenume"), { target: { value: "Ana" } });
    fireEvent.change(screen.getByPlaceholderText("Nume"), { target: { value: "Ionescu" } });
    fireEvent.change(screen.getByPlaceholderText("Email"), { target: { value: "ana@acme.ro" } });

    fireEvent.click(screen.getByRole("button", { name: "Înainte" }));
    expect(screen.queryByText("Prenumele este obligatoriu.")).not.toBeInTheDocument();
    expect(screen.queryByText("Numele este obligatoriu.")).not.toBeInTheDocument();
    expect(screen.queryByText("Email-ul este obligatoriu.")).not.toBeInTheDocument();
  });
});
