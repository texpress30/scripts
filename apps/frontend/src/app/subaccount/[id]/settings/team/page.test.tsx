import React from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import SubAccountTeamPage from "./page";

const listSubaccountTeamMembersMock = vi.fn();
const createSubaccountTeamMemberMock = vi.fn();

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
vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    listSubaccountTeamMembers: (...args: unknown[]) => listSubaccountTeamMembersMock(...args),
    createSubaccountTeamMember: (...args: unknown[]) => createSubaccountTeamMemberMock(...args),
  };
});

describe("SubAccount Team management page", () => {
  beforeEach(() => {
    listSubaccountTeamMembersMock.mockReset();
    createSubaccountTeamMemberMock.mockReset();
    listSubaccountTeamMembersMock.mockResolvedValue({
      items: [
        {
          membership_id: 1,
          user_id: 10,
          display_id: "TM-1",
          first_name: "Irina",
          last_name: "Stoica",
          email: "irina@example.com",
          phone: "+40 721 000 111",
          extension: "",
          role_key: "subaccount_user",
          role_label: "Subaccount User",
          source_scope: "subaccount",
          source_label: "Client 96",
          is_active: true,
          is_inherited: false,
        },
        {
          membership_id: 2,
          user_id: 11,
          display_id: "TM-2",
          first_name: "Andrei",
          last_name: "Matei",
          email: "andrei@example.com",
          phone: "",
          extension: "",
          role_key: "agency_admin",
          role_label: "Agency Admin",
          source_scope: "agency",
          source_label: "Agency access",
          is_active: true,
          is_inherited: true,
        },
      ],
      total: 2,
      page: 1,
      page_size: 5,
      subaccount_id: 96,
    });
  });

  it("loads members from real endpoint helper and renders inherited indicator", async () => {
    render(<SubAccountTeamPage />);

    await waitFor(() => {
      expect(listSubaccountTeamMembersMock).toHaveBeenCalledWith({
        subaccountId: 96,
        search: "",
        userRole: "",
        page: 1,
        pageSize: 5,
      });
    });

    expect(await screen.findByText("Irina Stoica")).toBeInTheDocument();
    expect(screen.getByText("Andrei Matei")).toBeInTheDocument();
    expect(screen.getByText(/Acces moștenit/i)).toBeInTheDocument();
    expect(screen.queryByText("Ana Ionescu")).not.toBeInTheDocument();
  });

  it("refetches list when filters change", async () => {
    render(<SubAccountTeamPage />);
    await waitFor(() => expect(listSubaccountTeamMembersMock).toHaveBeenCalledTimes(1));

    fireEvent.change(screen.getByLabelText("Filtru rol"), { target: { value: "subaccount_admin" } });
    await waitFor(() => {
      expect(listSubaccountTeamMembersMock).toHaveBeenLastCalledWith({
        subaccountId: 96,
        search: "",
        userRole: "subaccount_admin",
        page: 1,
        pageSize: 5,
      });
    });

    fireEvent.change(screen.getByPlaceholderText("Nume, email, telefon, id-uri"), { target: { value: "irina" } });
    await waitFor(() => {
      expect(listSubaccountTeamMembersMock).toHaveBeenLastCalledWith({
        subaccountId: 96,
        search: "irina",
        userRole: "subaccount_admin",
        page: 1,
        pageSize: 5,
      });
    });
  });

  it("create sends request to subaccount endpoint helper with route id and refetches", async () => {
    createSubaccountTeamMemberMock.mockResolvedValue({ item: {} });

    render(<SubAccountTeamPage />);
    await waitFor(() => expect(listSubaccountTeamMembersMock).toHaveBeenCalledTimes(1));

    fireEvent.click(screen.getByRole("button", { name: /Adaugă Utilizator/i }));
    fireEvent.change(screen.getByPlaceholderText("Prenume"), { target: { value: "Elena" } });
    fireEvent.change(screen.getByPlaceholderText("Nume"), { target: { value: "Popa" } });
    fireEvent.change(screen.getByPlaceholderText("Email"), { target: { value: "elena@example.com" } });
    fireEvent.change(screen.getByPlaceholderText("Telefon"), { target: { value: "+40 700 111 222" } });
    fireEvent.change(screen.getByPlaceholderText("Extensie"), { target: { value: "12" } });
    fireEvent.change(screen.getByDisplayValue("Subaccount User"), { target: { value: "subaccount_admin" } });
    fireEvent.click(screen.getByRole("button", { name: "Înainte" }));

    await waitFor(() => {
      expect(createSubaccountTeamMemberMock).toHaveBeenCalledWith(96, {
        first_name: "Elena",
        last_name: "Popa",
        email: "elena@example.com",
        phone: "+40 700 111 222",
        extension: "12",
        user_role: "subaccount_admin",
      });
    });

    await waitFor(() => expect(listSubaccountTeamMembersMock).toHaveBeenCalledTimes(2));
    expect(screen.getByText("Utilizator adăugat.")).toBeInTheDocument();
  });

  it("create role options are only subaccount roles", async () => {
    render(<SubAccountTeamPage />);
    await waitFor(() => expect(listSubaccountTeamMembersMock).toHaveBeenCalled());

    fireEvent.click(screen.getByRole("button", { name: /Adaugă Utilizator/i }));

    const optionTexts = screen.getAllByRole("option").map((node) => node.textContent ?? "");
    expect(optionTexts).toContain("Subaccount Admin");
    expect(optionTexts).toContain("Subaccount User");
    expect(optionTexts).toContain("Subaccount Viewer");
    expect(optionTexts).not.toContain("Agency Admin");
    expect(optionTexts).not.toContain("Agency Member");
  });

  it("shows clear 403 access message", async () => {
    const { ApiRequestError } = await import("@/lib/api");
    listSubaccountTeamMembersMock.mockRejectedValueOnce(new ApiRequestError("forbidden", 403));

    render(<SubAccountTeamPage />);

    expect(await screen.findByText("Nu ai acces la acest sub-account.")).toBeInTheDocument();
  });
});
