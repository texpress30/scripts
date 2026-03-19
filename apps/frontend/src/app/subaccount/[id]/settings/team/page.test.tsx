import React from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import SubAccountTeamPage from "./page";

const listSubaccountTeamMembersMock = vi.fn();
const createSubaccountTeamMemberMock = vi.fn();
const inviteTeamMemberMock = vi.fn();
const deactivateTeamMemberMock = vi.fn();
const reactivateTeamMemberMock = vi.fn();
const removeTeamMemberMock = vi.fn();
const getSubaccountGrantableModulesMock = vi.fn();
const getTeamModuleCatalogMock = vi.fn();
const getTeamMembershipDetailMock = vi.fn();
const updateTeamMembershipMock = vi.fn();

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
    deactivateTeamMember: (...args: unknown[]) => deactivateTeamMemberMock(...args),
    reactivateTeamMember: (...args: unknown[]) => reactivateTeamMemberMock(...args),
    removeTeamMember: (...args: unknown[]) => removeTeamMemberMock(...args),
    getSubaccountGrantableModules: (...args: unknown[]) => getSubaccountGrantableModulesMock(...args),
    getTeamModuleCatalog: (...args: unknown[]) => getTeamModuleCatalogMock(...args),
    getTeamMembershipDetail: (...args: unknown[]) => getTeamMembershipDetailMock(...args),
    updateTeamMembership: (...args: unknown[]) => updateTeamMembershipMock(...args),
  };
});

describe("SubAccount Team management page", () => {
  async function openPermissionsTab() {
    fireEvent.click(await screen.findByRole("button", { name: "Roluri și Permisiuni" }));
  }

  beforeEach(() => {
    listSubaccountTeamMembersMock.mockReset();
    createSubaccountTeamMemberMock.mockReset();
    inviteTeamMemberMock.mockReset();
    deactivateTeamMemberMock.mockReset();
    reactivateTeamMemberMock.mockReset();
    removeTeamMemberMock.mockReset();
    getSubaccountGrantableModulesMock.mockReset();
    getTeamModuleCatalogMock.mockReset();
    getTeamMembershipDetailMock.mockReset();
    updateTeamMembershipMock.mockReset();
    vi.spyOn(window, "confirm").mockReturnValue(true);
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
          membership_status: "active",
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
          membership_status: "inactive",
          is_inherited: true,
        },
      ],
      total: 2,
      page: 1,
      page_size: 5,
      subaccount_id: 96,
    });
    deactivateTeamMemberMock.mockResolvedValue({ membership_id: 1, status: "inactive", message: "Accesul a fost dezactivat pentru sesiunile noi și pentru verificările bazate pe datele curente." });
    reactivateTeamMemberMock.mockResolvedValue({ membership_id: 2, status: "active", message: "Accesul a fost reactivat" });
    removeTeamMemberMock.mockResolvedValue({ membership_id: 1, removed: true, message: "Accesul a fost eliminat" });
    getSubaccountGrantableModulesMock.mockResolvedValue({
      items: [
        { key: "dashboard", label: "Dashboard", order: 1, grantable: true },
        { key: "campaigns", label: "Campaigns", order: 2, grantable: true },
        { key: "settings", label: "Settings", order: 100, grantable: true },
        { key: "settings_team", label: "My Team", order: 110, grantable: true },
        { key: "creative", label: "Creative", order: 3, grantable: false },
      ],
    });
    getTeamModuleCatalogMock.mockResolvedValue({
      items: [
        { key: "dashboard", label: "Dashboard", order: 1, scope: "subaccount", group_key: "main_nav", group_label: "Main Navigation" },
        { key: "campaigns", label: "Campaigns", order: 2, scope: "subaccount", group_key: "main_nav", group_label: "Main Navigation" },
        { key: "creative", label: "Creative", order: 3, scope: "subaccount", group_key: "main_nav", group_label: "Main Navigation" },
        { key: "settings", label: "Settings", order: 100, scope: "subaccount", group_key: "settings", group_label: "Settings", is_container: true },
        { key: "settings_team", label: "My Team", order: 110, scope: "subaccount", group_key: "settings", group_label: "Settings", parent_key: "settings" },
      ],
    });
    getTeamMembershipDetailMock.mockResolvedValue({
      item: {
        membership_id: 1,
        user_id: 10,
        scope_type: "subaccount",
        subaccount_id: 96,
        subaccount_name: "Client 96",
        role_key: "subaccount_user",
        role_label: "Subaccount User",
        module_keys: ["dashboard", "campaigns", "settings", "settings_team"],
        source_scope: "subaccount",
        is_inherited: false,
        first_name: "Irina",
        last_name: "Stoica",
        email: "irina@example.com",
        phone: "+40 721 000 111",
        extension: "",
      },
    });
    updateTeamMembershipMock.mockResolvedValue({ item: {} });
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
    await openPermissionsTab();
    await screen.findByRole("checkbox", { name: "Permisiune modul Dashboard" });
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
        module_keys: ["dashboard", "campaigns", "settings", "settings_team"],
      });
    });

    await waitFor(() => expect(listSubaccountTeamMembersMock).toHaveBeenCalledTimes(2));
    expect(screen.getByText("Utilizator adăugat.")).toBeInTheDocument();
  });

  it("create role options are only subaccount roles", async () => {
    render(<SubAccountTeamPage />);
    await waitFor(() => expect(listSubaccountTeamMembersMock).toHaveBeenCalled());

    fireEvent.click(screen.getByRole("button", { name: /Adaugă Utilizator/i }));
    await openPermissionsTab();

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
          membership_status: "active",
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


  it("loads full subaccount catalog + grantable set and keeps non-grantable keys disabled", async () => {
    render(<SubAccountTeamPage />);
    await waitFor(() => expect(listSubaccountTeamMembersMock).toHaveBeenCalled());

    fireEvent.click(screen.getByRole("button", { name: /Adaugă Utilizator/i }));
    await openPermissionsTab();

    await waitFor(() => expect(getSubaccountGrantableModulesMock).toHaveBeenCalledWith(96));
    await waitFor(() => expect(getTeamModuleCatalogMock).toHaveBeenCalledWith("subaccount"));

    const dashboard = await screen.findByRole("checkbox", { name: "Permisiune modul Dashboard" });
    const campaigns = screen.getByRole("checkbox", { name: "Permisiune modul Campaigns" });
    const creative = screen.getByRole("checkbox", { name: "Permisiune modul Creative" });
    expect(screen.getByText("Nu poate fi acordat din grant ceiling-ul tău curent.")).toBeInTheDocument();
    fireEvent.click(await screen.findByRole("button", { name: /^Settings/i }));
    const settings = screen.getByRole("checkbox", { name: "Permisiune modul Settings" });
    const settingsTeam = screen.getByRole("checkbox", { name: "Permisiune modul My Team" });

    expect(dashboard).toBeChecked();
    expect(campaigns).toBeChecked();
    expect(settings).toBeChecked();
    expect(settingsTeam).toBeChecked();
    expect(creative).toBeDisabled();
  });

  it("updates module selection and sends only selected grantable module_keys", async () => {
    createSubaccountTeamMemberMock.mockResolvedValue({ item: {} });

    render(<SubAccountTeamPage />);
    await waitFor(() => expect(listSubaccountTeamMembersMock).toHaveBeenCalled());

    fireEvent.click(screen.getByRole("button", { name: /Adaugă Utilizator/i }));
    fireEvent.change(screen.getByPlaceholderText("Prenume"), { target: { value: "Elena" } });
    fireEvent.change(screen.getByPlaceholderText("Nume"), { target: { value: "Popa" } });
    fireEvent.change(screen.getByPlaceholderText("Email"), { target: { value: "elena@example.com" } });
    await openPermissionsTab();
    const campaigns = await screen.findByRole("checkbox", { name: "Permisiune modul Campaigns" });
    fireEvent.click(campaigns);
    fireEvent.click(await screen.findByRole("button", { name: /^Settings/i }));
    fireEvent.click(screen.getByRole("button", { name: "Înainte" }));

    await waitFor(() => {
      expect(createSubaccountTeamMemberMock).toHaveBeenCalledWith(
        96,
        expect.objectContaining({ module_keys: ["dashboard", "settings", "settings_team"] }),
      );
    });
  });

  it("syncs settings parent and child toggles coherently", async () => {
    render(<SubAccountTeamPage />);
    await waitFor(() => expect(listSubaccountTeamMembersMock).toHaveBeenCalled());
    fireEvent.click(screen.getByRole("button", { name: /Adaugă Utilizator/i }));
    fireEvent.change(screen.getByPlaceholderText("Prenume"), { target: { value: "Elena" } });
    fireEvent.change(screen.getByPlaceholderText("Nume"), { target: { value: "Popa" } });
    fireEvent.change(screen.getByPlaceholderText("Email"), { target: { value: "elena@example.com" } });
    await openPermissionsTab();
    fireEvent.click(await screen.findByRole("button", { name: /^Settings/i }));

    const settings = await screen.findByRole("checkbox", { name: "Permisiune modul Settings" });
    const settingsTeam = screen.getByRole("checkbox", { name: "Permisiune modul My Team" });

    expect(settings).toBeChecked();
    expect(settingsTeam).toBeChecked();

    fireEvent.click(settings);
    expect(settings).not.toBeChecked();
    expect(settingsTeam).not.toBeChecked();

    fireEvent.click(settingsTeam);
    expect(settings).toBeChecked();
    expect(settingsTeam).toBeChecked();

    fireEvent.click(settingsTeam);
    expect(settings).not.toBeChecked();
    expect(settingsTeam).not.toBeChecked();
  });

  it("supports permissions search and group switching in shared editor", async () => {
    render(<SubAccountTeamPage />);
    await waitFor(() => expect(listSubaccountTeamMembersMock).toHaveBeenCalled());
    fireEvent.click(screen.getByRole("button", { name: /Adaugă Utilizator/i }));
    await openPermissionsTab();

    fireEvent.change(screen.getByPlaceholderText("Caută după label, key sau grup"), { target: { value: "team" } });
    fireEvent.click(await screen.findByRole("button", { name: /^Settings/i }));

    expect(await screen.findByRole("checkbox", { name: "Permisiune modul My Team" })).toBeInTheDocument();
    expect(screen.queryByRole("checkbox", { name: "Permisiune modul Dashboard" })).not.toBeInTheDocument();
  });

  it("edit mode preloads module keys and blocks save when selected key is outside grant ceiling", async () => {
    getSubaccountGrantableModulesMock.mockResolvedValueOnce({
      items: [
        { key: "dashboard", label: "Dashboard", order: 1, grantable: true },
        { key: "campaigns", label: "Campaigns", order: 2, grantable: false },
        { key: "settings", label: "Settings", order: 100, grantable: true },
        { key: "settings_team", label: "My Team", order: 110, grantable: true },
      ],
    });
    getTeamMembershipDetailMock.mockResolvedValueOnce({
      item: {
        membership_id: 1,
        user_id: 10,
        scope_type: "subaccount",
        subaccount_id: 96,
        subaccount_name: "Client 96",
        role_key: "subaccount_user",
        role_label: "Subaccount User",
        module_keys: ["dashboard", "campaigns", "settings", "settings_team"],
        source_scope: "subaccount",
        is_inherited: false,
        first_name: "Irina",
        last_name: "Stoica",
        email: "irina@example.com",
        phone: "",
        extension: "",
      },
    });

    render(<SubAccountTeamPage />);
    const editButtons = await screen.findAllByRole("button", { name: "Editează" });
    fireEvent.click(editButtons[0]);
    await openPermissionsTab();

    expect(await screen.findByText(/depășesc accesul tău curent/i)).toBeInTheDocument();
    fireEvent.click(await screen.findByRole("button", { name: /^Main Navigation/i }));
    expect(screen.getByRole("checkbox", { name: "Permisiune modul Campaigns" })).toBeChecked();
    expect(screen.getByRole("button", { name: "Salvează" })).toBeDisabled();
    expect(updateTeamMembershipMock).not.toHaveBeenCalled();
  });

  it("edit mode sends only subaccount + grantable module keys", async () => {
    render(<SubAccountTeamPage />);
    const editButtons = await screen.findAllByRole("button", { name: "Editează" });
    fireEvent.click(editButtons[0]);
    await openPermissionsTab();

    const campaigns = await screen.findByRole("checkbox", { name: "Permisiune modul Campaigns" });
    fireEvent.click(campaigns);
    fireEvent.click(await screen.findByRole("button", { name: /^Settings/i }));
    fireEvent.change(screen.getByDisplayValue("Subaccount User"), { target: { value: "subaccount_viewer" } });
    fireEvent.click(screen.getByRole("button", { name: "Salvează" }));

    await waitFor(() => {
      expect(updateTeamMembershipMock).toHaveBeenCalledWith(1, {
        user_role: "subaccount_viewer",
        module_keys: ["dashboard", "settings", "settings_team"],
      });
    });
  });

  it("blocks submit when all grantable modules are unchecked", async () => {
    render(<SubAccountTeamPage />);
    await waitFor(() => expect(listSubaccountTeamMembersMock).toHaveBeenCalled());

    fireEvent.click(screen.getByRole("button", { name: /Adaugă Utilizator/i }));
    await openPermissionsTab();

    const dashboard = await screen.findByRole("checkbox", { name: "Permisiune modul Dashboard" });
    const campaigns = screen.getByRole("checkbox", { name: "Permisiune modul Campaigns" });
    const settings = screen.getByRole("checkbox", { name: "Permisiune modul Settings" });
    fireEvent.click(dashboard);
    fireEvent.click(campaigns);
    expect(dashboard).not.toBeChecked();
    expect(campaigns).not.toBeChecked();
    fireEvent.click(await screen.findByRole("button", { name: /^Settings/i }));
    const settings = screen.getByRole("checkbox", { name: "Permisiune modul Settings" });
    fireEvent.click(settings);
    expect(settings).not.toBeChecked();

    fireEvent.click(screen.getByRole("button", { name: "Înainte" }));

    expect(await screen.findByText("Selectează cel puțin o permisiune de navigare.")).toBeInTheDocument();
    expect(createSubaccountTeamMemberMock).not.toHaveBeenCalled();
  });

  it("shows friendly create errors for 403 and grant ceiling violations", async () => {
    const { ApiRequestError } = await import("@/lib/api");

    createSubaccountTeamMemberMock.mockRejectedValueOnce(new ApiRequestError("forbidden", 403));

    render(<SubAccountTeamPage />);
    await waitFor(() => expect(listSubaccountTeamMembersMock).toHaveBeenCalled());

    fireEvent.click(screen.getByRole("button", { name: /Adaugă Utilizator/i }));
    fireEvent.change(screen.getByPlaceholderText("Prenume"), { target: { value: "Elena" } });
    fireEvent.change(screen.getByPlaceholderText("Nume"), { target: { value: "Popa" } });
    fireEvent.change(screen.getByPlaceholderText("Email"), { target: { value: "elena@example.com" } });
    await openPermissionsTab();
    await screen.findByRole("checkbox", { name: "Permisiune modul Dashboard" });
    fireEvent.click(screen.getByRole("button", { name: "Înainte" }));

    expect(await screen.findByText("Permisiuni insuficiente pentru această acțiune.")).toBeInTheDocument();

    createSubaccountTeamMemberMock.mockRejectedValueOnce(new ApiRequestError("Nu poți acorda module în afara permisiunilor proprii: campaigns", 400));
    fireEvent.click(screen.getByRole("button", { name: "Înainte" }));
    expect(await screen.findByText("Nu poți acorda module în afara permisiunilor proprii: campaigns")).toBeInTheDocument();
  });

  it("keeps permissions state when switching between user and permissions tabs", async () => {
    render(<SubAccountTeamPage />);
    await waitFor(() => expect(listSubaccountTeamMembersMock).toHaveBeenCalled());
    fireEvent.click(screen.getByRole("button", { name: /Adaugă Utilizator/i }));

    await openPermissionsTab();
    const campaigns = await screen.findByRole("checkbox", { name: "Permisiune modul Campaigns" });
    fireEvent.click(campaigns);
    expect(campaigns).not.toBeChecked();

    fireEvent.click(screen.getByRole("button", { name: "Informații Utilizator" }));
    expect(screen.getByPlaceholderText("Prenume")).toBeInTheDocument();

    await openPermissionsTab();
    expect(screen.getByRole("checkbox", { name: "Permisiune modul Campaigns" })).not.toBeChecked();
  });

  it("renders membership status badges and lifecycle actions for active/inactive rows", async () => {
    render(<SubAccountTeamPage />);

    expect(await screen.findByText("Activ")).toBeInTheDocument();
    expect(await screen.findByText("Inactiv")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Dezactivează" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Reactivează" })).toBeDisabled();
  });

  it("calls deactivate for active membership and refetches list", async () => {
    render(<SubAccountTeamPage />);
    await waitFor(() => expect(listSubaccountTeamMembersMock).toHaveBeenCalledTimes(1));

    fireEvent.click(screen.getByRole("button", { name: "Dezactivează" }));

    await waitFor(() => expect(deactivateTeamMemberMock).toHaveBeenCalledWith(1));
    await waitFor(() => expect(listSubaccountTeamMembersMock).toHaveBeenCalledTimes(2));
    expect(await screen.findByText(/Accesul a fost dezactivat/i)).toBeInTheDocument();
  });

  it("reactivates inactive direct membership", async () => {
    listSubaccountTeamMembersMock.mockResolvedValueOnce({
      items: [
        { membership_id: 7, user_id: 21, display_id: "TM-7", first_name: "Ira", last_name: "A", email: "ira@example.com", phone: "", extension: "", role_key: "subaccount_user", role_label: "Subaccount User", source_scope: "subaccount", source_label: "Client 96", is_active: false, membership_status: "inactive", is_inherited: false },
      ],
      total: 1, page: 1, page_size: 5, subaccount_id: 96,
    });

    render(<SubAccountTeamPage />);
    const reactivateBtn = await screen.findByRole("button", { name: "Reactivează" });
    fireEvent.click(reactivateBtn);
    await waitFor(() => expect(reactivateTeamMemberMock).toHaveBeenCalledWith(7));
    expect(await screen.findByText(/Accesul a fost reactivat/i)).toBeInTheDocument();
  });

  it("shows lifecycle 403 error clearly", async () => {
    const { ApiRequestError } = await import("@/lib/api");

    reactivateTeamMemberMock.mockRejectedValueOnce(new ApiRequestError("forbidden", 403));
    listSubaccountTeamMembersMock.mockResolvedValueOnce({
      items: [{ membership_id: 8, user_id: 22, display_id: "TM-8", first_name: "R", last_name: "B", email: "r@example.com", phone: "", extension: "", role_key: "subaccount_user", role_label: "Subaccount User", source_scope: "subaccount", source_label: "Client 96", is_active: false, membership_status: "inactive", is_inherited: false }],
      total: 1, page: 1, page_size: 5, subaccount_id: 96,
    });
    render(<SubAccountTeamPage />);
    fireEvent.click(await screen.findByRole("button", { name: "Reactivează" }));
    expect(await screen.findByText("Nu ai permisiuni suficiente pentru această acțiune.")).toBeInTheDocument();
  });

  it("shows lifecycle 404 error clearly", async () => {
    const { ApiRequestError } = await import("@/lib/api");

    reactivateTeamMemberMock.mockRejectedValueOnce(new ApiRequestError("gone", 404));
    listSubaccountTeamMembersMock.mockResolvedValueOnce({
      items: [{ membership_id: 9, user_id: 22, display_id: "TM-9", first_name: "R", last_name: "B", email: "r@example.com", phone: "", extension: "", role_key: "subaccount_user", role_label: "Subaccount User", source_scope: "subaccount", source_label: "Client 96", is_active: false, membership_status: "inactive", is_inherited: false }],
      total: 1, page: 1, page_size: 5, subaccount_id: 96,
    });
    render(<SubAccountTeamPage />);
    fireEvent.click(await screen.findByRole("button", { name: "Reactivează" }));
    expect(await screen.findByText("Membership inexistent sau inaccesibil.")).toBeInTheDocument();
  });

  it("shows lifecycle 409 error clearly", async () => {
    const { ApiRequestError } = await import("@/lib/api");

    reactivateTeamMemberMock.mockRejectedValueOnce(new ApiRequestError("conflict", 409));
    listSubaccountTeamMembersMock.mockResolvedValueOnce({
      items: [{ membership_id: 10, user_id: 22, display_id: "TM-10", first_name: "R", last_name: "B", email: "r@example.com", phone: "", extension: "", role_key: "subaccount_user", role_label: "Subaccount User", source_scope: "subaccount", source_label: "Client 96", is_active: false, membership_status: "inactive", is_inherited: false }],
      total: 1, page: 1, page_size: 5, subaccount_id: 96,
    });
    render(<SubAccountTeamPage />);
    fireEvent.click(await screen.findByRole("button", { name: "Reactivează" }));
    expect(await screen.findByText("Acest access este moștenit și nu poate fi modificat aici")).toBeInTheDocument();
  });

  it("renders remove action, confirms, and calls remove endpoint", async () => {
    render(<SubAccountTeamPage />);
    await waitFor(() => expect(listSubaccountTeamMembersMock).toHaveBeenCalledTimes(1));

    const removeButtons = await screen.findAllByRole("button", { name: "Elimină accesul" });
    expect(removeButtons[0]).toBeEnabled();
    expect(removeButtons[1]).toBeDisabled();

    fireEvent.click(removeButtons[0]);

    await waitFor(() => {
      expect(window.confirm).toHaveBeenCalledWith(
        "Sigur vrei să elimini acest acces? Această acțiune șterge doar access grant-ul curent, nu utilizatorul global.",
      );
    });
    await waitFor(() => expect(removeTeamMemberMock).toHaveBeenCalledWith(1));
  });

  it("does not call remove endpoint when confirmation is cancelled", async () => {
    vi.spyOn(window, "confirm").mockReturnValueOnce(false);
    render(<SubAccountTeamPage />);
    await waitFor(() => expect(listSubaccountTeamMembersMock).toHaveBeenCalledTimes(1));

    const removeButtons = await screen.findAllByRole("button", { name: "Elimină accesul" });
    fireEvent.click(removeButtons[0]);

    await waitFor(() => expect(removeTeamMemberMock).not.toHaveBeenCalled());
  });

  it("remove success shows feedback and refetches list", async () => {
    render(<SubAccountTeamPage />);
    await waitFor(() => expect(listSubaccountTeamMembersMock).toHaveBeenCalledTimes(1));

    const removeButtons = await screen.findAllByRole("button", { name: "Elimină accesul" });
    fireEvent.click(removeButtons[0]);

    await waitFor(() => expect(removeTeamMemberMock).toHaveBeenCalledWith(1));
    await waitFor(() => expect(listSubaccountTeamMembersMock).toHaveBeenCalledTimes(2));
    expect(await screen.findByText(/Accesul a fost eliminat/i)).toBeInTheDocument();
  });

  it("handles remove 403 error clearly", async () => {
    const { ApiRequestError } = await import("@/lib/api");
    removeTeamMemberMock.mockRejectedValueOnce(new ApiRequestError("forbidden", 403));

    render(<SubAccountTeamPage />);
    await waitFor(() => expect(listSubaccountTeamMembersMock).toHaveBeenCalledTimes(1));
    fireEvent.click((await screen.findAllByRole("button", { name: "Elimină accesul" }))[0]);
    expect(await screen.findByText("Nu ai permisiuni suficiente pentru a elimina acest acces.")).toBeInTheDocument();
  });

  it("handles remove 404 gracefully and refreshes list", async () => {
    const { ApiRequestError } = await import("@/lib/api");
    removeTeamMemberMock.mockRejectedValueOnce(new ApiRequestError("Membership inexistent", 404));

    render(<SubAccountTeamPage />);
    await waitFor(() => expect(listSubaccountTeamMembersMock).toHaveBeenCalledTimes(1));
    fireEvent.click((await screen.findAllByRole("button", { name: "Elimină accesul" }))[0]);

    expect(await screen.findByText(/Membership inexistent/i)).toBeInTheDocument();
    await waitFor(() => expect(listSubaccountTeamMembersMock).toHaveBeenCalledTimes(2));
  });

  it("handles remove 409 self-removal conflict clearly", async () => {
    const { ApiRequestError } = await import("@/lib/api");
    removeTeamMemberMock.mockRejectedValueOnce(new ApiRequestError("Nu îți poți elimina propriul membership din sesiunea curentă", 409));

    render(<SubAccountTeamPage />);
    await waitFor(() => expect(listSubaccountTeamMembersMock).toHaveBeenCalledTimes(1));
    fireEvent.click((await screen.findAllByRole("button", { name: "Elimină accesul" }))[0]);
    expect(await screen.findByText("Nu îți poți elimina accesul curent din această sesiune")).toBeInTheDocument();
  });

  it("shows row-level remove loading state", async () => {
    let release: (() => void) | null = null;
    removeTeamMemberMock.mockImplementation(() => new Promise((resolve) => {
      release = () => resolve({ membership_id: 1, removed: true, message: "ok remove" });
    }));

    render(<SubAccountTeamPage />);
    await waitFor(() => expect(listSubaccountTeamMembersMock).toHaveBeenCalledTimes(1));
    const removeButtons = await screen.findAllByRole("button", { name: "Elimină accesul" });
    fireEvent.click(removeButtons[0]);

    expect(await screen.findByText("Se elimină...")).toBeInTheDocument();
    release?.();
    await waitFor(() => expect(screen.getByText("ok remove")).toBeInTheDocument());
  });

  it("shows row-level lifecycle loading state", async () => {
    let release: (() => void) | null = null;
    deactivateTeamMemberMock.mockImplementation(() => new Promise((resolve) => {
      release = () => resolve({ membership_id: 1, status: "inactive", message: "ok" });
    }));

    render(<SubAccountTeamPage />);
    const deactivateBtn = await screen.findByRole("button", { name: "Dezactivează" });
    fireEvent.click(deactivateBtn);

    expect(await screen.findByText("Se procesează...")).toBeInTheDocument();
    release?.();
    await waitFor(() => expect(screen.getByText("ok")).toBeInTheDocument());
  });


  it("shows clear 403 access message", async () => {
    const { ApiRequestError } = await import("@/lib/api");
    listSubaccountTeamMembersMock.mockRejectedValueOnce(new ApiRequestError("forbidden", 403));

    render(<SubAccountTeamPage />);

    expect(await screen.findByText("Nu ai acces la acest sub-account.")).toBeInTheDocument();
  });
});
