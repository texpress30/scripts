import React from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import SubAccountTeamPage from "./page";

const listSubaccountTeamMembersMock = vi.fn();
const createSubaccountTeamMemberMock = vi.fn();
const inviteTeamMemberMock = vi.fn();
const getSubaccountGrantableModulesMock = vi.fn();

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
    inviteTeamMember: (...args: unknown[]) => inviteTeamMemberMock(...args),
    getSubaccountGrantableModules: (...args: unknown[]) => getSubaccountGrantableModulesMock(...args),
  };
});

describe("SubAccount Team management page", () => {
  beforeEach(() => {
    listSubaccountTeamMembersMock.mockReset();
    createSubaccountTeamMemberMock.mockReset();
    inviteTeamMemberMock.mockReset();
    getSubaccountGrantableModulesMock.mockReset();
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
    getSubaccountGrantableModulesMock.mockResolvedValue({
      items: [
        { key: "dashboard", label: "Dashboard", order: 1, grantable: true },
        { key: "campaigns", label: "Campaigns", order: 2, grantable: true },
        { key: "creative", label: "Creative", order: 3, grantable: false },
      ],
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
    await screen.findByRole("checkbox", { name: "Permisiune modul Dashboard" });
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
        module_keys: ["dashboard", "campaigns"],
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

  it("renders invite action and calls endpoint with membership_id", async () => {
    inviteTeamMemberMock.mockResolvedValue({ message: "Invitația a fost trimisă" });

    render(<SubAccountTeamPage />);

    const inviteButtons = await screen.findAllByRole("button", { name: /Trimite invitație/i });
    expect(inviteButtons[0]).toBeEnabled();

    fireEvent.click(inviteButtons[0]);

    await waitFor(() => {
      expect(inviteTeamMemberMock).toHaveBeenCalledWith(1);
    });
    expect(await screen.findByText("Invitația a fost trimisă")).toBeInTheDocument();
  });

  it("shows per-row loading during invite", async () => {
    let resolveInvite: ((value: { message: string }) => void) | null = null;
    inviteTeamMemberMock.mockReturnValue(new Promise((resolve) => {
      resolveInvite = resolve;
    }));

    render(<SubAccountTeamPage />);

    const inviteButtons = await screen.findAllByRole("button", { name: /Trimite invitație/i });
    fireEvent.click(inviteButtons[0]);

    expect(await screen.findByRole("button", { name: /Se trimite.../i })).toBeDisabled();
    expect(inviteButtons[1]).toBeEnabled();

    resolveInvite?.({ message: "Invitația a fost trimisă" });
    await waitFor(() => expect(screen.getByText("Invitația a fost trimisă")).toBeInTheDocument());
  });

  it("shows friendly 403 and 503 invite errors", async () => {
    const { ApiRequestError } = await import("@/lib/api");
    inviteTeamMemberMock.mockRejectedValueOnce(new ApiRequestError("forbidden", 403));

    render(<SubAccountTeamPage />);
    const inviteButtons = await screen.findAllByRole("button", { name: /Trimite invitație/i });
    fireEvent.click(inviteButtons[0]);

    expect(await screen.findByText("Nu ai permisiunea să trimiți invitația pentru acest utilizator.")).toBeInTheDocument();

    inviteTeamMemberMock.mockRejectedValueOnce(new ApiRequestError("down", 503));
    fireEvent.click(inviteButtons[0]);
    expect(await screen.findByText("Invitațiile sunt indisponibile temporar. Încearcă din nou mai târziu.")).toBeInTheDocument();
  });

  it("disables invite when membership_id is missing", async () => {
    listSubaccountTeamMembersMock.mockResolvedValueOnce({
      items: [
        {
          membership_id: Number.NaN,
          user_id: 10,
          display_id: "TM-NA",
          first_name: "Fara",
          last_name: "Membership",
          email: "fara@example.com",
          phone: "",
          extension: "",
          role_key: "subaccount_user",
          role_label: "Subaccount User",
          source_scope: "subaccount",
          source_label: "Client 96",
          is_active: true,
          is_inherited: false,
        },
      ],
      total: 1,
      page: 1,
      page_size: 5,
      subaccount_id: 96,
    });

    render(<SubAccountTeamPage />);

    const inviteButton = await screen.findByTitle("Invitația nu este disponibilă pentru acest rând");
    expect(inviteButton).toBeDisabled();
    expect(inviteTeamMemberMock).not.toHaveBeenCalled();
  });


  it("loads and renders module permissions with default grantable selection", async () => {
    render(<SubAccountTeamPage />);
    await waitFor(() => expect(listSubaccountTeamMembersMock).toHaveBeenCalled());

    fireEvent.click(screen.getByRole("button", { name: /Adaugă Utilizator/i }));

    await waitFor(() => expect(getSubaccountGrantableModulesMock).toHaveBeenCalledWith(96));

    const dashboard = await screen.findByRole("checkbox", { name: "Permisiune modul Dashboard" });
    const campaigns = screen.getByRole("checkbox", { name: "Permisiune modul Campaigns" });
    const creative = screen.getByRole("checkbox", { name: "Permisiune modul Creative" });

    expect(dashboard).toBeChecked();
    expect(campaigns).toBeChecked();
    expect(creative).toBeDisabled();
    expect(screen.getByText("Nu poate fi acordat din permisiunile tale curente.")).toBeInTheDocument();
  });

  it("updates module selection and sends only selected grantable module_keys", async () => {
    createSubaccountTeamMemberMock.mockResolvedValue({ item: {} });

    render(<SubAccountTeamPage />);
    await waitFor(() => expect(listSubaccountTeamMembersMock).toHaveBeenCalled());

    fireEvent.click(screen.getByRole("button", { name: /Adaugă Utilizator/i }));
    const campaigns = await screen.findByRole("checkbox", { name: "Permisiune modul Campaigns" });
    fireEvent.click(campaigns);

    fireEvent.change(screen.getByPlaceholderText("Prenume"), { target: { value: "Elena" } });
    fireEvent.change(screen.getByPlaceholderText("Nume"), { target: { value: "Popa" } });
    fireEvent.change(screen.getByPlaceholderText("Email"), { target: { value: "elena@example.com" } });
    fireEvent.click(screen.getByRole("button", { name: "Înainte" }));

    await waitFor(() => {
      expect(createSubaccountTeamMemberMock).toHaveBeenCalledWith(96, expect.objectContaining({ module_keys: ["dashboard"] }));
    });
  });

  it("blocks submit when all grantable modules are unchecked", async () => {
    render(<SubAccountTeamPage />);
    await waitFor(() => expect(listSubaccountTeamMembersMock).toHaveBeenCalled());

    fireEvent.click(screen.getByRole("button", { name: /Adaugă Utilizator/i }));

    const dashboard = await screen.findByRole("checkbox", { name: "Permisiune modul Dashboard" });
    const campaigns = screen.getByRole("checkbox", { name: "Permisiune modul Campaigns" });
    fireEvent.click(dashboard);
    fireEvent.click(campaigns);

    fireEvent.change(screen.getByPlaceholderText("Prenume"), { target: { value: "Elena" } });
    fireEvent.change(screen.getByPlaceholderText("Nume"), { target: { value: "Popa" } });
    fireEvent.change(screen.getByPlaceholderText("Email"), { target: { value: "elena@example.com" } });
    fireEvent.click(screen.getByRole("button", { name: "Înainte" }));

    expect(await screen.findByText("Selectează cel puțin un modul.")).toBeInTheDocument();
    expect(createSubaccountTeamMemberMock).not.toHaveBeenCalled();
  });

  it("shows friendly create errors for 403 and grant ceiling violations", async () => {
    const { ApiRequestError } = await import("@/lib/api");

    createSubaccountTeamMemberMock.mockRejectedValueOnce(new ApiRequestError("forbidden", 403));

    render(<SubAccountTeamPage />);
    await waitFor(() => expect(listSubaccountTeamMembersMock).toHaveBeenCalled());

    fireEvent.click(screen.getByRole("button", { name: /Adaugă Utilizator/i }));
    await screen.findByRole("checkbox", { name: "Permisiune modul Dashboard" });

    fireEvent.change(screen.getByPlaceholderText("Prenume"), { target: { value: "Elena" } });
    fireEvent.change(screen.getByPlaceholderText("Nume"), { target: { value: "Popa" } });
    fireEvent.change(screen.getByPlaceholderText("Email"), { target: { value: "elena@example.com" } });
    fireEvent.click(screen.getByRole("button", { name: "Înainte" }));

    expect(await screen.findByText("Permisiuni insuficiente pentru această acțiune.")).toBeInTheDocument();

    createSubaccountTeamMemberMock.mockRejectedValueOnce(new ApiRequestError("Nu poți acorda module în afara permisiunilor proprii: campaigns", 400));
    fireEvent.click(screen.getByRole("button", { name: "Înainte" }));
    expect(await screen.findByText("Nu poți acorda module în afara permisiunilor proprii: campaigns")).toBeInTheDocument();
  });

  it("shows clear 403 access message", async () => {
    const { ApiRequestError } = await import("@/lib/api");
    listSubaccountTeamMembersMock.mockRejectedValueOnce(new ApiRequestError("forbidden", 403));

    render(<SubAccountTeamPage />);

    expect(await screen.findByText("Nu ai acces la acest sub-account.")).toBeInTheDocument();
  });
});
