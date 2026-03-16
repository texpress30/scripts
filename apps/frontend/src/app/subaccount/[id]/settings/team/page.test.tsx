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

describe("SubAccount Team table", () => {
  it("renders team listing controls and table headers", () => {
    render(<SubAccountTeamPage />);

    expect(screen.getByText("Echipa Mea")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "+ Adaugă Utilizator" })).toBeInTheDocument();

    expect(screen.getByRole("combobox")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("Nume, email, telefon, id-uri")).toBeInTheDocument();

    expect(screen.getByRole("columnheader", { name: "Nume" })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "Email" })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "Telefon" })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "Tip Utilizator" })).toBeInTheDocument();
    expect(screen.getByText("Pagina 1")).toBeInTheDocument();
    expect(screen.getByText("Andrei Pop")).toBeInTheDocument();
  });

  it("filters by role, supports search reset, and shows copy toast", () => {
    render(<SubAccountTeamPage />);

    fireEvent.change(screen.getByRole("combobox"), { target: { value: "ACCOUNT-ADMIN" } });
    expect(screen.getByText("Mihai Sava")).toBeInTheDocument();
    expect(screen.queryByText("Andrei Pop")).not.toBeInTheDocument();

    fireEvent.change(screen.getByPlaceholderText("Nume, email, telefon, id-uri"), { target: { value: "nu-exista" } });
    expect(screen.getByText("Nu există utilizatori pentru filtrele selectate.")).toBeInTheDocument();

    fireEvent.change(screen.getByPlaceholderText("Nume, email, telefon, id-uri"), { target: { value: "" } });
    const copyIdButton = screen.getByRole("button", { name: "t91Ks0QazP2nL8mN56cx" });
    fireEvent.click(copyIdButton);
    expect(screen.getByText("ID Copiat")).toBeInTheDocument();
  });
});
