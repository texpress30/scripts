import React from "react";
import { describe, expect, it, vi, beforeEach } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import SettingsTeamPage from "./page";
import { ApiRequestError } from "@/lib/api";

const apiRequestMock = vi.fn();
const inviteTeamMemberMock = vi.fn();
const deleteTeamUserMock = vi.fn();

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    apiRequest: (...args: unknown[]) => apiRequestMock(...args),
    getTeamModuleCatalog: (scope = "subaccount") => apiRequestMock(`/team/module-catalog?scope=${encodeURIComponent(scope)}`),
    inviteTeamMember: (...args: unknown[]) => inviteTeamMemberMock(...args),
    getTeamMembershipDetail: (membershipId: string | number) => apiRequestMock(`/team/members/${encodeURIComponent(String(membershipId))}`),
    updateTeamMembership: (membershipId: string | number, payload: unknown) => apiRequestMock(`/team/members/${encodeURIComponent(String(membershipId))}`, { method: "PATCH", body: JSON.stringify(payload) }),
    deactivateTeamMember: (membershipId: string | number) => apiRequestMock(`/team/members/${encodeURIComponent(String(membershipId))}/deactivate`, { method: "POST", body: JSON.stringify({}) }),
    reactivateTeamMember: (membershipId: string | number) => apiRequestMock(`/team/members/${encodeURIComponent(String(membershipId))}/reactivate`, { method: "POST", body: JSON.stringify({}) }),
    removeTeamMember: (membershipId: string | number) => apiRequestMock(`/team/members/${encodeURIComponent(String(membershipId))}/remove`, { method: "POST", body: JSON.stringify({}) }),
    deleteTeamUser: (...args: unknown[]) => deleteTeamUserMock(...args),
  };
});

vi.mock("@/components/ProtectedPage", () => ({
  ProtectedPage: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

vi.mock("@/components/AppShell", () => ({
  AppShell: ({ children, title }: { children: React.ReactNode; title: React.ReactNode }) => (
    <div>
      <div data-testid="app-shell-title">{String(title ?? "")}</div>
      {children}
    </div>
  ),
}));

describe("Settings team page subaccount integration", () => {
  function getCreateMemberCalls() {
    return apiRequestMock.mock.calls.filter((call) => call[0] === "/team/members" && call[1]?.method === "POST");
  }

  function getCheckboxByLabelText(label: string): HTMLInputElement {
    const candidates = screen.getAllByText(label);
    for (const node of candidates) {
      const checkbox = node.closest("label")?.querySelector("input[type='checkbox']") as HTMLInputElement | null;
      if (checkbox) return checkbox;
    }
    throw new Error(`Checkbox not found for label: ${label}`);
  }

  async function openPermissionsTab() {
    fireEvent.click(screen.getByRole("button", { name: "Roluri și Permisiuni" }));
    await screen.findByPlaceholderText("Caută după label, key sau grup");
  }

  beforeEach(() => {
    apiRequestMock.mockReset();
    inviteTeamMemberMock.mockReset();
    deleteTeamUserMock.mockReset();
    vi.spyOn(window, "confirm").mockReturnValue(true);
    apiRequestMock.mockImplementation((path: string, options?: { method?: string; body?: string }) => {
      if (path.startsWith("/team/members?")) {
        return Promise.resolve({
          items: [
            {
              id: 101,
              membership_id: 101,
              user_id: 201,
              first_name: "Ana",
              last_name: "Ionescu",
              email: "ana@example.com",
              phone: "",
              extension: "",
              user_type: "agency",
              user_role: "admin",
              location: "România",
              subaccount: "Toate",
              allowed_subaccount_ids: [],
              has_restricted_subaccount_access: false,
              membership_status: "active",
            },
            {
              id: 102,
              membership_id: null,
              user_id: 202,
              first_name: "No",
              last_name: "Membership",
              email: "",
              phone: "",
              extension: "",
              user_type: "agency",
              user_role: "member",
              location: "România",
              subaccount: "Toate",
              allowed_subaccount_ids: [2, 3],
              allowed_subaccounts: [
                { id: 2, name: "Client Alpha", label: "#11 — Client Alpha" },
                { id: 3, name: "Client Beta", label: "Client Beta" },
              ],
              has_restricted_subaccount_access: true,
              membership_status: "inactive",
            },
          ],
          total: 2,
          page: 1,
          page_size: 10,
        });
      }
      if (path === "/team/subaccount-options") {
        return Promise.resolve({
          items: [
            { id: 2, name: "Client Alpha", label: "#11 — Client Alpha" },
            { id: 3, name: "Client Beta", label: "" },
          ],
        });
      }
      if (path === "/team/module-catalog?scope=subaccount") {
        return Promise.resolve({
          items: [
            { key: "dashboard", label: "Dashboard", order: 1, scope: "subaccount" },
            { key: "campaigns", label: "Campaigns", order: 2, scope: "subaccount" },
            { key: "rules", label: "Rules", order: 3, scope: "subaccount" },
            { key: "creative", label: "Creative", order: 4, scope: "subaccount" },
            { key: "recommendations", label: "Recommendations", order: 5, scope: "subaccount" },
          ],
        });
      }
      if (path === "/team/module-catalog?scope=agency") {
        return Promise.resolve({
          items: [
            { key: "agency_dashboard", label: "Dashboard", order: 1, scope: "agency", group_key: "main_nav", group_label: "Main Navigation" },
            { key: "settings", label: "Settings", order: 100, scope: "agency", group_key: "settings", group_label: "Settings", is_container: true },
            { key: "settings_my_team", label: "My Team", order: 130, scope: "agency", group_key: "settings", group_label: "Settings", parent_key: "settings" },
          ],
        });
      }

      if (path === "/team/members/101") {
        return Promise.resolve({
          item: {
            membership_id: 101,
            user_id: 201,
            scope_type: "agency",
            subaccount_id: null,
            subaccount_name: "Toate",
            role_key: "agency_admin",
            role_label: "Agency Admin",
            module_keys: [],
            allowed_subaccount_ids: [],
            allowed_subaccounts: [],
            has_restricted_subaccount_access: false,
            source_scope: "agency",
            is_inherited: false,
            first_name: "Ana",
            last_name: "Ionescu",
            email: "ana@example.com",
            phone: "",
            extension: "",
          },
        });
      }
      if (path === "/team/members/103") {
        return Promise.resolve({
          item: {
            membership_id: 103,
            user_id: 203,
            scope_type: "subaccount",
            subaccount_id: 2,
            subaccount_name: "Client Alpha",
            role_key: "subaccount_user",
            role_label: "Subaccount User",
            module_keys: ["dashboard", "creative"],
            source_scope: "subaccount",
            is_inherited: false,
            first_name: "Mihai",
            last_name: "Pop",
            email: "mihai@example.com",
            phone: "0700",
            extension: "12",
          },
        });
      }
      if (path === "/team/members/105") {
        return Promise.resolve({
          item: {
            membership_id: 105,
            user_id: 205,
            scope_type: "agency",
            subaccount_id: null,
            subaccount_name: "Toate",
            role_key: "agency_member",
            role_label: "Agency Member",
            module_keys: ["agency_dashboard", "settings", "settings_my_team"],
            allowed_subaccount_ids: [2, 3],
            allowed_subaccounts: [
              { id: 2, name: "Client Alpha", label: "#11 — Client Alpha" },
              { id: 3, name: "Client Beta", label: "Client Beta" },
            ],
            has_restricted_subaccount_access: true,
            source_scope: "agency",
            is_inherited: false,
            first_name: "Agen",
            last_name: "Member",
            email: "agency-member@example.com",
            phone: "",
            extension: "",
          },
        });
      }
      if (path === "/team/members/104") {
        return Promise.resolve({
          item: {
            membership_id: 104,
            user_id: 204,
            scope_type: "subaccount",
            subaccount_id: 3,
            subaccount_name: "Client Beta",
            role_key: "subaccount_user",
            role_label: "Subaccount User",
            module_keys: ["dashboard"],
            source_scope: "subaccount",
            is_inherited: true,
            first_name: "Inh",
            last_name: "User",
            email: "inh@example.com",
            phone: "",
            extension: "",
          },
        });
      }
      if (path === "/team/members/101/deactivate" && options?.method === "POST") {
        return Promise.resolve({ membership_id: 101, status: "inactive", message: "Accesul a fost dezactivat pentru sesiunile noi și pentru verificările bazate pe datele curente." });
      }
      if (path === "/team/members/102/reactivate" && options?.method === "POST") {
        return Promise.resolve({ membership_id: 102, status: "active", message: "Accesul a fost reactivat" });
      }
      if (path === "/team/members" && options?.method === "POST") {
        return Promise.resolve({ item: { id: 1 } });
      }
      if (path.startsWith("/team/members/") && options?.method === "PATCH") {
        const membershipId = Number(path.split("/").at(-1));
        const body = JSON.parse(String(options.body ?? "{}"));
        return Promise.resolve({
          item: {
            membership_id: membershipId,
            user_id: 201,
            scope_type: membershipId === 101 ? "agency" : "subaccount",
            subaccount_id: membershipId === 101 ? null : 2,
            subaccount_name: membershipId === 101 ? "Toate" : "Client Alpha",
            role_key: body.user_role ?? (membershipId === 101 ? "agency_admin" : "subaccount_user"),
            role_label: "Updated",
            module_keys: body.module_keys ?? [],
            allowed_subaccount_ids: body.allowed_subaccount_ids ?? [],
            allowed_subaccounts: [],
            has_restricted_subaccount_access: Array.isArray(body.allowed_subaccount_ids) && body.allowed_subaccount_ids.length > 0,
            source_scope: membershipId === 101 ? "agency" : "subaccount",
            is_inherited: false,
            first_name: "Ana",
            last_name: "Ionescu",
            email: "ana@example.com",
            phone: "",
            extension: "",
          },
        });
      }
      return Promise.reject(new Error(`Unexpected path: ${path}`));
    });
    inviteTeamMemberMock.mockResolvedValue({ message: "Invitația a fost trimisă" });
    deleteTeamUserMock.mockResolvedValue({
      user_id: 201,
      deleted: true,
      deleted_memberships_count: 1,
      message: "Utilizator șters complet din sistem",
    });
  });

  it("loads real subaccount options for list filter and re-filters on selection", async () => {
    render(<SettingsTeamPage />);

    await waitFor(() => expect(apiRequestMock).toHaveBeenCalledWith("/team/subaccount-options"));

    const selects = screen.getAllByRole("combobox");
    const listSubaccountSelect = selects[2] as HTMLSelectElement;

    expect(screen.getByRole("option", { name: "Toate" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "#11 — Client Alpha" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "Client Beta" })).toBeInTheDocument();

    fireEvent.change(listSubaccountSelect, { target: { value: "2" } });

    await waitFor(() => {
      const memberCalls = apiRequestMock.mock.calls
        .map((call) => String(call[0]))
        .filter((path) => path.startsWith("/team/members?"));
      expect(memberCalls.some((path) => path.includes("subaccount=2"))).toBe(true);
    });
  });

  it("shows `Acces / Conturi` instead of `Locație` and renders correct access summary", async () => {
    render(<SettingsTeamPage />);

    expect(await screen.findByText("Acces / Conturi")).toBeInTheDocument();
    expect(screen.queryByText("Locație")).not.toBeInTheDocument();

    // agency users should show account access semantics, not geographic placeholders
    expect(screen.getAllByText("Toate conturile").length).toBeGreaterThan(0);
  });

  it("includes `Agency Owner` in agency role selector", async () => {
    render(<SettingsTeamPage />);
    fireEvent.click(screen.getByRole("button", { name: /Adaugă Utilizator/i }));
    const roleSelect = await screen.findByLabelText("Rol Utilizator");
    expect(screen.getByRole("option", { name: "Agency Owner" })).toBeInTheDocument();
    fireEvent.change(roleSelect, { target: { value: "owner" } });
    expect((roleSelect as HTMLSelectElement).value).toBe("owner");
  });

  it("hides grants selector for Agency Owner and Agency Admin", async () => {
    render(<SettingsTeamPage />);
    fireEvent.click(screen.getByRole("button", { name: /Adaugă Utilizator/i }));
    const roleSelect = await screen.findByLabelText("Rol Utilizator");

    fireEvent.change(roleSelect, { target: { value: "owner" } });
    expect(screen.queryByText("Acces sub-account-uri (agency)")).not.toBeInTheDocument();

    fireEvent.change(roleSelect, { target: { value: "admin" } });
    expect(screen.queryByText("Acces sub-account-uri (agency)")).not.toBeInTheDocument();
  });

  it("shows grants selector for Agency Member and Agency Viewer", async () => {
    render(<SettingsTeamPage />);
    fireEvent.click(screen.getByRole("button", { name: /Adaugă Utilizator/i }));
    const roleSelect = await screen.findByLabelText("Rol Utilizator");

    fireEvent.change(roleSelect, { target: { value: "member" } });
    expect(screen.getByText("Acces sub-account-uri (agency)")).toBeInTheDocument();
    expect(screen.getByText("Niciun sub-account selectat = acces la toate conturile.")).toBeInTheDocument();

    fireEvent.change(roleSelect, { target: { value: "viewer" } });
    expect(screen.getByText("Acces sub-account-uri (agency)")).toBeInTheDocument();
  });

  it("renders subaccount name in `Acces / Conturi` for client memberships", async () => {
    apiRequestMock.mockImplementation((path: string) => {
      if (path.startsWith("/team/members?")) {
        return Promise.resolve({
          items: [
            {
              id: 103,
              membership_id: 103,
              user_id: 203,
              first_name: "Mihai",
              last_name: "Pop",
              email: "mihai@example.com",
              phone: "",
              extension: "",
              user_type: "client",
              user_role: "member",
              location: "România",
              subaccount: "Client Alpha",
              membership_status: "active",
            },
          ],
          total: 1,
          page: 1,
          page_size: 10,
        });
      }
      if (path === "/team/subaccount-options") return Promise.resolve({ items: [] });
      if (path === "/team/module-catalog?scope=subaccount") return Promise.resolve({ items: [] });
      if (path === "/team/module-catalog?scope=agency") return Promise.resolve({ items: [] });
      return Promise.reject(new Error(`Unexpected path: ${path}`));
    });

    render(<SettingsTeamPage />);

    expect(await screen.findByText("Client Alpha")).toBeInTheDocument();
    expect(screen.queryByText("România")).not.toBeInTheDocument();
  });

  it("requires a real subaccount only for client users and submits selected id as string", async () => {
    render(<SettingsTeamPage />);

    fireEvent.click(screen.getByRole("button", { name: /Adaugă Utilizator/i }));

    const subaccountSelect = await screen.findByRole("combobox", { name: "Sub-cont" });
    expect(subaccountSelect).toBeDisabled();

    fireEvent.change(screen.getByLabelText("Tip Utilizator"), { target: { value: "client" } });
    expect(subaccountSelect).not.toBeDisabled();

    fireEvent.change(screen.getByRole("textbox", { name: "Prenume" }), { target: { value: "Ana" } });
    fireEvent.change(screen.getByRole("textbox", { name: "Nume" }), { target: { value: "Ionescu" } });
    fireEvent.change(screen.getByRole("textbox", { name: /Email/i }), { target: { value: "ana@example.com" } });

    fireEvent.click(screen.getByRole("button", { name: "Pasul Următor" }));
    expect(screen.getByText(/Selectarea unui sub-cont este obligatorie/i)).toBeInTheDocument();

    fireEvent.change(subaccountSelect, { target: { value: "2" } });
    fireEvent.click(screen.getByRole("button", { name: "Pasul Următor" }));
    fireEvent.click(screen.getByRole("button", { name: "Creează utilizator" }));

    await waitFor(() => {
      const postCall = apiRequestMock.mock.calls.find((call) => call[0] === "/team/members" && call[1]?.method === "POST");
      expect(postCall).toBeTruthy();
      const body = JSON.parse(String(postCall?.[1]?.body ?? "{}"));
      expect(body.user_type).toBe("client");
      expect(body.subaccount).toBe("2");
    });
  });

  it("create payload includes allowed_subaccount_ids for agency member/viewer when selected", async () => {
    render(<SettingsTeamPage />);
    fireEvent.click(screen.getByRole("button", { name: /Adaugă Utilizator/i }));

    fireEvent.change(screen.getByRole("textbox", { name: "Prenume" }), { target: { value: "Ana" } });
    fireEvent.change(screen.getByRole("textbox", { name: "Nume" }), { target: { value: "Ionescu" } });
    fireEvent.change(screen.getByRole("textbox", { name: /Email/i }), { target: { value: "ana@example.com" } });
    fireEvent.change(screen.getByLabelText("Rol Utilizator"), { target: { value: "member" } });

    fireEvent.click(await screen.findByLabelText("#11 — Client Alpha"));
    fireEvent.click(screen.getByLabelText("Client Beta"));

    fireEvent.click(screen.getByRole("button", { name: "Pasul Următor" }));
    fireEvent.click(screen.getByRole("button", { name: "Creează utilizator" }));

    await waitFor(() => {
      const postCall = getCreateMemberCalls()[0];
      const body = JSON.parse(String(postCall?.[1]?.body ?? "{}"));
      expect(body.user_type).toBe("agency");
      expect(body.user_role).toBe("member");
      expect(body.allowed_subaccount_ids).toEqual([2, 3]);
    });
  });

  it("create payload keeps unrestricted semantics for agency member/viewer when no grants are selected", async () => {
    render(<SettingsTeamPage />);
    fireEvent.click(screen.getByRole("button", { name: /Adaugă Utilizator/i }));

    fireEvent.change(screen.getByRole("textbox", { name: "Prenume" }), { target: { value: "Ana" } });
    fireEvent.change(screen.getByRole("textbox", { name: "Nume" }), { target: { value: "Ionescu" } });
    fireEvent.change(screen.getByRole("textbox", { name: /Email/i }), { target: { value: "ana@example.com" } });
    fireEvent.change(screen.getByLabelText("Rol Utilizator"), { target: { value: "viewer" } });

    fireEvent.click(screen.getByRole("button", { name: "Pasul Următor" }));
    fireEvent.click(screen.getByRole("button", { name: "Creează utilizator" }));

    await waitFor(() => {
      const postCall = getCreateMemberCalls()[0];
      const body = JSON.parse(String(postCall?.[1]?.body ?? "{}"));
      expect(body.allowed_subaccount_ids).toEqual([]);
    });
  });


  it("renders auto-invite checkbox in create form and keeps default unchecked", async () => {
    render(<SettingsTeamPage />);

    fireEvent.click(screen.getByRole("button", { name: /Adaugă Utilizator/i }));

    const checkbox = await screen.findByRole("checkbox", { name: "Trimite invitație imediat după creare" });
    expect(checkbox).not.toBeChecked();
  });

  it("does not render `Locație` input in create or edit flows", async () => {
    render(<SettingsTeamPage />);

    fireEvent.click(screen.getByRole("button", { name: /Adaugă Utilizator/i }));
    expect(screen.queryByLabelText("Locație")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Înapoi" }));
    const editButtons = await screen.findAllByRole("button", { name: "Editează" });
    fireEvent.click(editButtons[0]);
    expect(await screen.findByRole("button", { name: "Salvează" })).toBeInTheDocument();
    expect(screen.queryByLabelText("Locație")).not.toBeInTheDocument();
  });

  it("edit flow preloads restricted grants and allows switching to unrestricted", async () => {
    const baseImpl = apiRequestMock.getMockImplementation();
    apiRequestMock.mockImplementation((path: string, options?: { method?: string; body?: string }) => {
      if (path === "/team/members/101") {
        return Promise.resolve({
          item: {
            membership_id: 101,
            user_id: 201,
            scope_type: "agency",
            subaccount_id: null,
            subaccount_name: "Toate",
            role_key: "agency_member",
            role_label: "Agency Member",
            module_keys: ["agency_dashboard", "settings", "settings_my_team"],
            allowed_subaccount_ids: [2, 3],
            allowed_subaccounts: [
              { id: 2, name: "Client Alpha", label: "#11 — Client Alpha" },
              { id: 3, name: "Client Beta", label: "Client Beta" },
            ],
            has_restricted_subaccount_access: true,
            source_scope: "agency",
            is_inherited: false,
            first_name: "Ana",
            last_name: "Ionescu",
            email: "ana@example.com",
            phone: "",
            extension: "",
          },
        });
      }
      return baseImpl ? baseImpl(path, options) : Promise.reject(new Error(`Unexpected path: ${path}`));
    });

    render(<SettingsTeamPage />);
    await screen.findByText("Ana Ionescu");
    fireEvent.click(screen.getAllByRole("button", { name: "Editează" })[0]);
    await waitFor(() => expect(screen.getByLabelText("Rol Utilizator")).toBeInTheDocument());

    expect(screen.getByText("Acces sub-account-uri (agency)")).toBeInTheDocument();
    const alpha = screen.getByLabelText("#11 — Client Alpha") as HTMLInputElement;
    const beta = screen.getByLabelText("Client Beta") as HTMLInputElement;
    expect(alpha.checked).toBe(true);
    expect(beta.checked).toBe(true);
    fireEvent.click(alpha);
    fireEvent.click(beta);

    fireEvent.click(screen.getByRole("button", { name: "Roluri și Permisiuni" }));
    await screen.findByRole("button", { name: "Salvează" });
    fireEvent.click(screen.getByRole("button", { name: "Salvează" }));

    await waitFor(() => {
      const patchCall = apiRequestMock.mock.calls.find((call) => String(call[0]).startsWith("/team/members/") && call[1]?.method === "PATCH");
      const payload = JSON.parse(String(patchCall?.[1]?.body ?? "{}"));
      expect(payload.allowed_subaccount_ids).toEqual([]);
    });
  });

  it("create without auto-invite does not call invite endpoint", async () => {
    render(<SettingsTeamPage />);

    fireEvent.click(screen.getByRole("button", { name: /Adaugă Utilizator/i }));
    fireEvent.change(screen.getByRole("textbox", { name: "Prenume" }), { target: { value: "Ana" } });
    fireEvent.change(screen.getByRole("textbox", { name: "Nume" }), { target: { value: "Ionescu" } });
    fireEvent.change(screen.getByRole("textbox", { name: /Email/i }), { target: { value: "ana@example.com" } });

    fireEvent.click(screen.getByRole("button", { name: "Pasul Următor" }));
    fireEvent.click(screen.getByRole("button", { name: "Creează utilizator" }));

    await waitFor(() => {
      const postCall = apiRequestMock.mock.calls.find((call) => call[0] === "/team/members" && call[1]?.method === "POST");
      expect(postCall).toBeTruthy();
    });

    expect(inviteTeamMemberMock).not.toHaveBeenCalled();
    expect(await screen.findByText("Utilizator adăugat cu succes.")).toBeInTheDocument();
  });

  it("in create mode, next step only switches tab and does not call create API", async () => {
    render(<SettingsTeamPage />);

    fireEvent.click(screen.getByRole("button", { name: /Adaugă Utilizator/i }));
    fireEvent.change(screen.getByRole("textbox", { name: "Prenume" }), { target: { value: "Lia" } });
    fireEvent.change(screen.getByRole("textbox", { name: "Nume" }), { target: { value: "Matei" } });
    fireEvent.change(screen.getByRole("textbox", { name: /Email/i }), { target: { value: "lia@example.com" } });

    fireEvent.click(screen.getByRole("button", { name: "Pasul Următor" }));

    expect(screen.getByRole("heading", { name: "Roluri și Permisiuni" })).toBeInTheDocument();
    expect(getCreateMemberCalls()).toHaveLength(0);
  });

  it("create identity step is rendered outside form; permissions step owns the real submit form", async () => {
    render(<SettingsTeamPage />);

    fireEvent.click(screen.getByRole("button", { name: /Adaugă Utilizator/i }));
    fireEvent.change(screen.getByRole("textbox", { name: "Prenume" }), { target: { value: "Lia" } });
    fireEvent.change(screen.getByRole("textbox", { name: "Nume" }), { target: { value: "Matei" } });
    fireEvent.change(screen.getByRole("textbox", { name: /Email/i }), { target: { value: "lia@example.com" } });

    const identityForm = screen.getByRole("heading", { name: "Informații Utilizator" }).closest("form");
    expect(identityForm).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "Pasul Următor" }));

    const permissionsForm = screen.getByRole("heading", { name: "Roluri și Permisiuni" }).closest("form");
    expect(permissionsForm).toBeTruthy();
    expect(screen.getByRole("button", { name: "Creează utilizator" })).toBeInTheDocument();
  });

  it("enter in identity step does not create user and keeps data until explicit next step", async () => {
    render(<SettingsTeamPage />);

    fireEvent.click(screen.getByRole("button", { name: /Adaugă Utilizator/i }));
    fireEvent.change(screen.getByRole("textbox", { name: "Prenume" }), { target: { value: "Lia" } });
    fireEvent.change(screen.getByRole("textbox", { name: "Nume" }), { target: { value: "Matei" } });
    const emailInput = screen.getByRole("textbox", { name: /Email/i });
    fireEvent.change(emailInput, { target: { value: "lia@example.com" } });

    fireEvent.keyDown(emailInput, { key: "Enter", code: "Enter", charCode: 13 });

    expect(screen.getByRole("heading", { name: "Informații Utilizator" })).toBeInTheDocument();
    expect(getCreateMemberCalls()).toHaveLength(0);
    expect(screen.getByRole("textbox", { name: "Prenume" })).toHaveValue("Lia");
    expect(screen.getByRole("textbox", { name: "Nume" })).toHaveValue("Matei");
    expect(screen.getByRole("textbox", { name: /Email/i })).toHaveValue("lia@example.com");
  });

  it("step values persist forward/backward and create API is called only on final submit", async () => {
    render(<SettingsTeamPage />);

    fireEvent.click(screen.getByRole("button", { name: /Adaugă Utilizator/i }));
    fireEvent.change(screen.getByRole("textbox", { name: "Prenume" }), { target: { value: "Lia" } });
    fireEvent.change(screen.getByRole("textbox", { name: "Nume" }), { target: { value: "Matei" } });
    fireEvent.change(screen.getByRole("textbox", { name: /Email/i }), { target: { value: "lia@example.com" } });
    fireEvent.change(screen.getByRole("textbox", { name: "Telefon" }), { target: { value: "0712345" } });

    fireEvent.click(screen.getByRole("button", { name: "Pasul Următor" }));
    expect(screen.getByRole("heading", { name: "Roluri și Permisiuni" })).toBeInTheDocument();
    expect(getCreateMemberCalls()).toHaveLength(0);

    fireEvent.click(screen.getByRole("button", { name: "Informații Utilizator" }));
    expect(screen.getByRole("textbox", { name: "Prenume" })).toHaveValue("Lia");
    expect(screen.getByRole("textbox", { name: "Nume" })).toHaveValue("Matei");
    expect(screen.getByRole("textbox", { name: /Email/i })).toHaveValue("lia@example.com");
    expect(screen.getByRole("textbox", { name: "Telefon" })).toHaveValue("0712345");

    fireEvent.click(screen.getByRole("button", { name: "Pasul Următor" }));
    fireEvent.click(screen.getByRole("button", { name: "Creează utilizator" }));

    await waitFor(() => expect(getCreateMemberCalls()).toHaveLength(1));
  });

  it("create with auto-invite checked calls invite with created membership id", async () => {
    apiRequestMock.mockImplementation((path: string, options?: { method?: string; body?: string }) => {
      if (path.startsWith("/team/members?")) {
        return Promise.resolve({ items: [], total: 0, page: 1, page_size: 10 });
      }
      if (path === "/team/subaccount-options") return Promise.resolve({ items: [] });
      if (path === "/team/module-catalog?scope=subaccount") return Promise.resolve({ items: [] });
      if (path === "/team/module-catalog?scope=agency") return Promise.resolve({ items: [] });

      if (path === "/team/members/101") {
        return Promise.resolve({
          item: {
            membership_id: 101,
            user_id: 201,
            scope_type: "agency",
            subaccount_id: null,
            subaccount_name: "Toate",
            role_key: "agency_admin",
            role_label: "Agency Admin",
            module_keys: [],
            source_scope: "agency",
            is_inherited: false,
            first_name: "Ana",
            last_name: "Ionescu",
            email: "ana@example.com",
            phone: "",
            extension: "",
          },
        });
      }
      if (path === "/team/members/103") {
        return Promise.resolve({
          item: {
            membership_id: 103,
            user_id: 203,
            scope_type: "subaccount",
            subaccount_id: 2,
            subaccount_name: "Client Alpha",
            role_key: "subaccount_user",
            role_label: "Subaccount User",
            module_keys: ["dashboard", "creative"],
            source_scope: "subaccount",
            is_inherited: false,
            first_name: "Mihai",
            last_name: "Pop",
            email: "mihai@example.com",
            phone: "0700",
            extension: "12",
          },
        });
      }
      if (path === "/team/members/104") {
        return Promise.resolve({
          item: {
            membership_id: 104,
            user_id: 204,
            scope_type: "subaccount",
            subaccount_id: 3,
            subaccount_name: "Client Beta",
            role_key: "subaccount_user",
            role_label: "Subaccount User",
            module_keys: ["dashboard"],
            source_scope: "subaccount",
            is_inherited: true,
            first_name: "Inh",
            last_name: "User",
            email: "inh@example.com",
            phone: "",
            extension: "",
          },
        });
      }
      if (path === "/team/members" && options?.method === "POST") {
        return Promise.resolve({ item: { id: 1001, membership_id: 777 } });
      }
      return Promise.reject(new Error(`Unexpected path: ${path}`));
    });

    render(<SettingsTeamPage />);

    fireEvent.click(screen.getByRole("button", { name: /Adaugă Utilizator/i }));
    fireEvent.change(screen.getByRole("textbox", { name: "Prenume" }), { target: { value: "Mara" } });
    fireEvent.change(screen.getByRole("textbox", { name: "Nume" }), { target: { value: "Pop" } });
    fireEvent.change(screen.getByRole("textbox", { name: /Email/i }), { target: { value: "mara@example.com" } });
    fireEvent.click(screen.getByRole("checkbox", { name: "Trimite invitație imediat după creare" }));

    fireEvent.click(screen.getByRole("button", { name: "Pasul Următor" }));
    fireEvent.click(screen.getByRole("button", { name: "Creează utilizator" }));

    await waitFor(() => expect(inviteTeamMemberMock).toHaveBeenCalledWith(777));
    expect(await screen.findByText("Utilizatorul a fost creat și invitația a fost trimisă")).toBeInTheDocument();

    expect(screen.getByRole("button", { name: /Adaugă Utilizator/i })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /Adaugă Utilizator/i }));
    expect(await screen.findByRole("checkbox", { name: "Trimite invitație imediat după creare" })).not.toBeChecked();
  });

  it("create success + invite 503 shows partial success message", async () => {
    inviteTeamMemberMock.mockRejectedValueOnce(new ApiRequestError("temporarily unavailable", 503));

    apiRequestMock.mockImplementation((path: string, options?: { method?: string; body?: string }) => {
      if (path.startsWith("/team/members?")) {
        return Promise.resolve({ items: [], total: 0, page: 1, page_size: 10 });
      }
      if (path === "/team/subaccount-options") return Promise.resolve({ items: [] });
      if (path === "/team/module-catalog?scope=subaccount") return Promise.resolve({ items: [] });
      if (path === "/team/module-catalog?scope=agency") return Promise.resolve({ items: [] });

      if (path === "/team/members/101") {
        return Promise.resolve({
          item: {
            membership_id: 101,
            user_id: 201,
            scope_type: "agency",
            subaccount_id: null,
            subaccount_name: "Toate",
            role_key: "agency_admin",
            role_label: "Agency Admin",
            module_keys: [],
            source_scope: "agency",
            is_inherited: false,
            first_name: "Ana",
            last_name: "Ionescu",
            email: "ana@example.com",
            phone: "",
            extension: "",
          },
        });
      }
      if (path === "/team/members/103") {
        return Promise.resolve({
          item: {
            membership_id: 103,
            user_id: 203,
            scope_type: "subaccount",
            subaccount_id: 2,
            subaccount_name: "Client Alpha",
            role_key: "subaccount_user",
            role_label: "Subaccount User",
            module_keys: ["dashboard", "creative"],
            source_scope: "subaccount",
            is_inherited: false,
            first_name: "Mihai",
            last_name: "Pop",
            email: "mihai@example.com",
            phone: "0700",
            extension: "12",
          },
        });
      }
      if (path === "/team/members/104") {
        return Promise.resolve({
          item: {
            membership_id: 104,
            user_id: 204,
            scope_type: "subaccount",
            subaccount_id: 3,
            subaccount_name: "Client Beta",
            role_key: "subaccount_user",
            role_label: "Subaccount User",
            module_keys: ["dashboard"],
            source_scope: "subaccount",
            is_inherited: true,
            first_name: "Inh",
            last_name: "User",
            email: "inh@example.com",
            phone: "",
            extension: "",
          },
        });
      }
      if (path === "/team/members" && options?.method === "POST") {
        return Promise.resolve({ item: { id: 1002, membership_id: 778 } });
      }
      return Promise.reject(new Error(`Unexpected path: ${path}`));
    });

    render(<SettingsTeamPage />);

    fireEvent.click(screen.getByRole("button", { name: /Adaugă Utilizator/i }));
    fireEvent.change(screen.getByRole("textbox", { name: "Prenume" }), { target: { value: "Dana" } });
    fireEvent.change(screen.getByRole("textbox", { name: "Nume" }), { target: { value: "Iacob" } });
    fireEvent.change(screen.getByRole("textbox", { name: /Email/i }), { target: { value: "dana@example.com" } });
    fireEvent.click(screen.getByRole("checkbox", { name: "Trimite invitație imediat după creare" }));

    fireEvent.click(screen.getByRole("button", { name: "Pasul Următor" }));
    fireEvent.click(screen.getByRole("button", { name: "Creează utilizator" }));

    expect(await screen.findByText(/Utilizatorul a fost creat, dar invitația nu a putut fi trimisă\./i)).toBeInTheDocument();
    expect(screen.getByText(/Invitațiile sunt indisponibile temporar/i)).toBeInTheDocument();
  });

  it("create failure does not call invite", async () => {
    apiRequestMock.mockImplementation((path: string, options?: { method?: string; body?: string }) => {
      if (path.startsWith("/team/members?")) {
        return Promise.resolve({ items: [], total: 0, page: 1, page_size: 10 });
      }
      if (path === "/team/subaccount-options") return Promise.resolve({ items: [] });
      if (path === "/team/module-catalog?scope=subaccount") return Promise.resolve({ items: [] });
      if (path === "/team/module-catalog?scope=agency") return Promise.resolve({ items: [] });

      if (path === "/team/members/101") {
        return Promise.resolve({
          item: {
            membership_id: 101,
            user_id: 201,
            scope_type: "agency",
            subaccount_id: null,
            subaccount_name: "Toate",
            role_key: "agency_admin",
            role_label: "Agency Admin",
            module_keys: [],
            source_scope: "agency",
            is_inherited: false,
            first_name: "Ana",
            last_name: "Ionescu",
            email: "ana@example.com",
            phone: "",
            extension: "",
          },
        });
      }
      if (path === "/team/members/103") {
        return Promise.resolve({
          item: {
            membership_id: 103,
            user_id: 203,
            scope_type: "subaccount",
            subaccount_id: 2,
            subaccount_name: "Client Alpha",
            role_key: "subaccount_user",
            role_label: "Subaccount User",
            module_keys: ["dashboard", "creative"],
            source_scope: "subaccount",
            is_inherited: false,
            first_name: "Mihai",
            last_name: "Pop",
            email: "mihai@example.com",
            phone: "0700",
            extension: "12",
          },
        });
      }
      if (path === "/team/members/104") {
        return Promise.resolve({
          item: {
            membership_id: 104,
            user_id: 204,
            scope_type: "subaccount",
            subaccount_id: 3,
            subaccount_name: "Client Beta",
            role_key: "subaccount_user",
            role_label: "Subaccount User",
            module_keys: ["dashboard"],
            source_scope: "subaccount",
            is_inherited: true,
            first_name: "Inh",
            last_name: "User",
            email: "inh@example.com",
            phone: "",
            extension: "",
          },
        });
      }
      if (path === "/team/members" && options?.method === "POST") {
        return Promise.reject(new Error("Nu am putut adăuga utilizatorul."));
      }
      return Promise.reject(new Error(`Unexpected path: ${path}`));
    });

    render(<SettingsTeamPage />);

    fireEvent.click(screen.getByRole("button", { name: /Adaugă Utilizator/i }));
    fireEvent.change(screen.getByRole("textbox", { name: "Prenume" }), { target: { value: "Paul" } });
    fireEvent.change(screen.getByRole("textbox", { name: "Nume" }), { target: { value: "Enache" } });
    fireEvent.change(screen.getByRole("textbox", { name: /Email/i }), { target: { value: "paul@example.com" } });
    fireEvent.click(screen.getByRole("checkbox", { name: "Trimite invitație imediat după creare" }));

    fireEvent.click(screen.getByRole("button", { name: "Pasul Următor" }));
    fireEvent.click(screen.getByRole("button", { name: "Creează utilizator" }));

    expect(await screen.findByText("Nu am putut adăuga utilizatorul.")).toBeInTheDocument();
    expect(inviteTeamMemberMock).not.toHaveBeenCalled();
  });


  it("loads agency + subaccount catalogs and switches permissions by user type", async () => {
    render(<SettingsTeamPage />);

    await waitFor(() => expect(apiRequestMock).toHaveBeenCalledWith("/team/module-catalog?scope=subaccount"));
    await waitFor(() => expect(apiRequestMock).toHaveBeenCalledWith("/team/module-catalog?scope=agency"));

    fireEvent.click(screen.getByRole("button", { name: /Adaugă Utilizator/i }));
    await openPermissionsTab();

    expect(await screen.findByLabelText("Dashboard")).toBeChecked();
    fireEvent.click(screen.getByRole("button", { name: /^Settings/i }));
    const settingsParent = getCheckboxByLabelText("Settings");
    expect(settingsParent).toBeChecked();

    fireEvent.click(screen.getByRole("button", { name: "Informații Utilizator" }));
    fireEvent.change(screen.getByLabelText("Tip Utilizator"), { target: { value: "client" } });
    await openPermissionsTab();
    expect(screen.getByLabelText("Dashboard")).toBeChecked();
    expect(screen.getByLabelText("Recommendations")).toBeChecked();
  });

  it("updates module state when toggling checkboxes", async () => {
    render(<SettingsTeamPage />);

    fireEvent.click(screen.getByRole("button", { name: /Adaugă Utilizator/i }));
    fireEvent.change(screen.getByLabelText("Tip Utilizator"), { target: { value: "client" } });
    const subaccountSelect = screen.getByLabelText("Sub-cont") as HTMLSelectElement;
    await waitFor(() => expect(subaccountSelect.disabled).toBe(false));
    fireEvent.change(subaccountSelect, { target: { value: "2" } });
    await openPermissionsTab();

    const dashboard = await screen.findByLabelText("Dashboard");
    expect(dashboard).toBeChecked();
    fireEvent.click(dashboard);
    expect(dashboard).not.toBeChecked();
  });

  it("syncs settings parent and children coherently for agency catalog", async () => {
    render(<SettingsTeamPage />);

    fireEvent.click(screen.getByRole("button", { name: /Adaugă Utilizator/i }));
    await openPermissionsTab();
    fireEvent.click(await screen.findByRole("button", { name: /^Settings/i }));
    await screen.findByLabelText("My Team");

    const settingsParent = getCheckboxByLabelText("Settings");
    const settingsChild = getCheckboxByLabelText("My Team");
    expect(settingsParent).toBeChecked();
    expect(settingsChild).toBeChecked();

    fireEvent.click(settingsParent);
    expect(settingsParent).not.toBeChecked();
    expect(settingsChild).not.toBeChecked();

    fireEvent.click(settingsChild);
    expect(settingsParent).toBeChecked();
    expect(settingsChild).toBeChecked();

    fireEvent.click(settingsChild);
    expect(settingsParent).not.toBeChecked();
    expect(settingsChild).not.toBeChecked();
  });

  it("supports permissions search in shared editor", async () => {
    render(<SettingsTeamPage />);

    fireEvent.click(screen.getByRole("button", { name: /Adaugă Utilizator/i }));
    await openPermissionsTab();
    await screen.findByLabelText("Dashboard");
    fireEvent.change(screen.getByPlaceholderText("Caută după label, key sau grup"), { target: { value: "my team" } });
    fireEvent.click(await screen.findByRole("button", { name: /^Settings/i }));

    expect(await screen.findByLabelText("My Team")).toBeInTheDocument();
    expect(screen.queryByLabelText("Dashboard")).not.toBeInTheDocument();
  });

  it("renders permissions only in dedicated tab and preserves checkbox state across tab switches", async () => {
    render(<SettingsTeamPage />);

    fireEvent.click(screen.getByRole("button", { name: /Adaugă Utilizator/i }));
    expect(screen.queryByPlaceholderText("Caută după label, key sau grup")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Setări Avansate" })).toBeInTheDocument();

    await openPermissionsTab();
    const dashboard = await screen.findByLabelText("Dashboard");
    expect(dashboard).toBeChecked();
    fireEvent.click(dashboard);
    expect(dashboard).not.toBeChecked();

    fireEvent.click(screen.getByRole("button", { name: "Informații Utilizator" }));
    expect(screen.queryByPlaceholderText("Caută după label, key sau grup")).not.toBeInTheDocument();

    await openPermissionsTab();
    expect(screen.getByLabelText("Dashboard")).not.toBeChecked();
  }, 10000);

  it("subaccount create sends module_keys and blocks submit when none selected", async () => {
    render(<SettingsTeamPage />);

    fireEvent.click(screen.getByRole("button", { name: /Adaugă Utilizator/i }));
    fireEvent.change(screen.getByLabelText("Tip Utilizator"), { target: { value: "client" } });
    const subaccountSelect = screen.getByLabelText("Sub-cont") as HTMLSelectElement;
    await waitFor(() => expect(subaccountSelect.disabled).toBe(false));
    fireEvent.change(subaccountSelect, { target: { value: "2" } });
    fireEvent.change(screen.getByRole("textbox", { name: "Prenume" }), { target: { value: "Ana" } });
    fireEvent.change(screen.getByRole("textbox", { name: "Nume" }), { target: { value: "Ionescu" } });
    fireEvent.change(screen.getByRole("textbox", { name: /Email/i }), { target: { value: "ana@example.com" } });
    await openPermissionsTab();

    for (const label of ["Dashboard", "Campaigns", "Rules", "Creative", "Recommendations"]) {
      const checkbox = await screen.findByLabelText(label);
      if ((checkbox as HTMLInputElement).checked) fireEvent.click(checkbox);
    }

    fireEvent.click(screen.getByRole("button", { name: "Creează utilizator" }));
    expect(await screen.findByText(/Selectează cel puțin o permisiune de navigare/i)).toBeInTheDocument();

    fireEvent.click(screen.getByLabelText("Dashboard"));
    fireEvent.click(screen.getByRole("button", { name: "Creează utilizator" }));

    await waitFor(() => {
      const postCall = apiRequestMock.mock.calls.find((call) => call[0] === "/team/members" && call[1]?.method === "POST");
      expect(postCall).toBeTruthy();
      const body = JSON.parse(String(postCall?.[1]?.body ?? "{}"));
      expect(body.module_keys).toEqual(["dashboard"]);
    });
  });

  it("agency create sends agency module_keys", async () => {
    render(<SettingsTeamPage />);

    fireEvent.click(screen.getByRole("button", { name: /Adaugă Utilizator/i }));
    fireEvent.change(screen.getByRole("textbox", { name: "Prenume" }), { target: { value: "Ana" } });
    fireEvent.change(screen.getByRole("textbox", { name: "Nume" }), { target: { value: "Ionescu" } });
    fireEvent.change(screen.getByRole("textbox", { name: /Email/i }), { target: { value: "ana@example.com" } });
    await openPermissionsTab();
    await screen.findByLabelText("Dashboard");
    fireEvent.click(screen.getByRole("button", { name: "Creează utilizator" }));

    await waitFor(() => {
      const postCall = apiRequestMock.mock.calls.find((call) => call[0] === "/team/members" && call[1]?.method === "POST");
      expect(postCall).toBeTruthy();
      const body = JSON.parse(String(postCall?.[1]?.body ?? "{}"));
      expect(Array.isArray(body.module_keys)).toBe(true);
      expect(body.module_keys).toContain("agency_dashboard");
    });
  });

  it("shows backend module permission errors clearly", async () => {
    apiRequestMock.mockImplementation((path: string, options?: { method?: string; body?: string }) => {
      if (path.startsWith("/team/members?")) return Promise.resolve({ items: [], total: 0, page: 1, page_size: 10 });
      if (path === "/team/subaccount-options") return Promise.resolve({ items: [{ id: 2, name: "Client Alpha", label: "#11 — Client Alpha" }] });
      if (path === "/team/module-catalog?scope=subaccount") return Promise.resolve({ items: [{ key: "dashboard", label: "Dashboard", order: 1, scope: "subaccount", group_key: "main_nav", group_label: "Main Navigation" }] });
      if (path === "/team/module-catalog?scope=agency") return Promise.resolve({ items: [{ key: "agency_dashboard", label: "Dashboard", order: 1, scope: "agency", group_key: "main_nav", group_label: "Main Navigation" }] });
      if (path === "/team/members" && options?.method === "POST") return Promise.reject(new ApiRequestError("module_keys este permis doar pentru membership-uri de sub-account", 400));
      return Promise.reject(new Error(`Unexpected path: ${path}`));
    });

    render(<SettingsTeamPage />);

    fireEvent.click(screen.getByRole("button", { name: /Adaugă Utilizator/i }));
    fireEvent.change(screen.getByRole("textbox", { name: "Prenume" }), { target: { value: "Ana" } });
    fireEvent.change(screen.getByRole("textbox", { name: "Nume" }), { target: { value: "Ionescu" } });
    fireEvent.change(screen.getByRole("textbox", { name: /Email/i }), { target: { value: "ana@example.com" } });
    fireEvent.click(screen.getByRole("button", { name: "Pasul Următor" }));
    fireEvent.click(screen.getByRole("button", { name: "Creează utilizator" }));

    expect(await screen.findByText(/module_keys este permis doar/i)).toBeInTheDocument();
  });



  it("opens edit mode and fetches membership detail by membership_id", async () => {
    render(<SettingsTeamPage />);

    const editButtons = await screen.findAllByRole("button", { name: "Editează" });
    fireEvent.click(editButtons[0]);

    await waitFor(() => {
      expect(apiRequestMock).toHaveBeenCalledWith("/team/members/101");
    });

    expect(screen.getByRole("button", { name: "Salvează" })).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: "Prenume" })).toBeDisabled();
    expect(screen.getByRole("textbox", { name: "Nume" })).toBeDisabled();
    expect(screen.getByRole("textbox", { name: /Email/i })).toBeDisabled();
  });

  it("renders subaccount edit with preselected modules and sends PATCH user_role + module_keys", async () => {
    apiRequestMock.mockImplementation((path: string, options?: { method?: string; body?: string }) => {
      if (path.startsWith("/team/members?")) {
        return Promise.resolve({
          items: [{ id: 103, membership_id: 103, user_id: 203, first_name: "Mihai", last_name: "Pop", email: "mihai@example.com", phone: "", extension: "", user_type: "client", user_role: "member", location: "România", subaccount: "Client Alpha" }],
          total: 1,
          page: 1,
          page_size: 10,
        });
      }
      if (path === "/team/subaccount-options") return Promise.resolve({ items: [{ id: 2, name: "Client Alpha", label: "#11 — Client Alpha" }] });
      if (path === "/team/module-catalog?scope=subaccount") return Promise.resolve({ items: [
        { key: "dashboard", label: "Dashboard", order: 1, scope: "subaccount", group_key: "main_nav", group_label: "Main Navigation" },
        { key: "creative", label: "Creative", order: 4, scope: "subaccount", group_key: "main_nav", group_label: "Main Navigation" },
        { key: "rules", label: "Rules", order: 3, scope: "subaccount", group_key: "main_nav", group_label: "Main Navigation" },
      ]});
      if (path === "/team/module-catalog?scope=agency") return Promise.resolve({ items: [{ key: "agency_dashboard", label: "Dashboard", order: 1, scope: "agency", group_key: "main_nav", group_label: "Main Navigation" }] });
      if (path === "/team/members/103") return Promise.resolve({ item: {
        membership_id: 103, user_id: 203, scope_type: "subaccount", subaccount_id: 2, subaccount_name: "Client Alpha", role_key: "subaccount_user", role_label: "Subaccount User", module_keys: ["dashboard", "creative"], source_scope: "subaccount", is_inherited: false, first_name: "Mihai", last_name: "Pop", email: "mihai@example.com", phone: "", extension: "",
      }});
      if (path === "/team/members/103" && options?.method === "PATCH") {
        return Promise.resolve({ item: {
          membership_id: 103, user_id: 203, scope_type: "subaccount", subaccount_id: 2, subaccount_name: "Client Alpha", role_key: "subaccount_viewer", role_label: "Subaccount Viewer", module_keys: ["dashboard"], source_scope: "subaccount", is_inherited: false, first_name: "Mihai", last_name: "Pop", email: "mihai@example.com", phone: "", extension: "",
        }});
      }
      return Promise.reject(new Error(`Unexpected path: ${path}`));
    });

    render(<SettingsTeamPage />);
    const editButton = await screen.findByRole("button", { name: "Editează" });
    fireEvent.click(editButton);
    await openPermissionsTab();

    const creative = await screen.findByLabelText("Creative");

    fireEvent.click(creative);
    fireEvent.click(screen.getByRole("button", { name: "Informații Utilizator" }));
    fireEvent.change(screen.getByRole("combobox", { name: "Rol Utilizator" }), { target: { value: "viewer" } });
    fireEvent.click(screen.getByRole("button", { name: "Salvează" }));

    await waitFor(() => {
      const patchCall = apiRequestMock.mock.calls.find((call) => call[0] === "/team/members/103" && call[1]?.method === "PATCH");
      expect(patchCall).toBeTruthy();
      const body = JSON.parse(String(patchCall?.[1]?.body ?? "{}"));
      expect(body.user_role).toBe("subaccount_viewer");
      expect(body.module_keys).toEqual(["dashboard"]);
    });
  });

  it("blocks inherited membership edit and handles 409 clearly", async () => {
    apiRequestMock.mockImplementation((path: string, options?: { method?: string; body?: string }) => {
      if (path.startsWith("/team/members?")) {
        return Promise.resolve({
          items: [{ id: 104, membership_id: 104, user_id: 204, first_name: "Inh", last_name: "User", email: "inh@example.com", phone: "", extension: "", user_type: "client", user_role: "member", location: "România", subaccount: "Client Beta" }],
          total: 1,
          page: 1,
          page_size: 10,
        });
      }
      if (path === "/team/subaccount-options") return Promise.resolve({ items: [{ id: 3, name: "Client Beta", label: "Client Beta" }] });
      if (path === "/team/module-catalog?scope=subaccount") return Promise.resolve({ items: [{ key: "dashboard", label: "Dashboard", order: 1, scope: "subaccount", group_key: "main_nav", group_label: "Main Navigation" }] });
      if (path === "/team/module-catalog?scope=agency") return Promise.resolve({ items: [{ key: "agency_dashboard", label: "Dashboard", order: 1, scope: "agency", group_key: "main_nav", group_label: "Main Navigation" }] });
      if (path === "/team/members/104") return Promise.resolve({ item: {
        membership_id: 104, user_id: 204, scope_type: "subaccount", subaccount_id: 3, subaccount_name: "Client Beta", role_key: "subaccount_user", role_label: "Subaccount User", module_keys: ["dashboard"], source_scope: "subaccount", is_inherited: true, first_name: "Inh", last_name: "User", email: "inh@example.com", phone: "", extension: "",
      }});
      if (path === "/team/members/104" && options?.method === "PATCH") {
        return Promise.reject(new ApiRequestError("Access moștenit: acest membership nu poate fi editat local", 409));
      }
      return Promise.reject(new Error(`Unexpected path: ${path}`));
    });

    render(<SettingsTeamPage />);
    const editButton = await screen.findByRole("button", { name: "Editează" });
    fireEvent.click(editButton);

    expect(await screen.findByText(/nu poate fi editat aici/i)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Salvează" }));
    expect(apiRequestMock.mock.calls.some((call) => call[0] === "/team/members/104" && call[1]?.method === "PATCH")).toBe(false);
  });

  it("renders invite action and sends invite with membership id", async () => {
    render(<SettingsTeamPage />);

    const buttons = await screen.findAllByRole("button", { name: "Trimite invitație" });
    expect(buttons.length).toBeGreaterThan(0);

    fireEvent.click(buttons[0]);

    await waitFor(() => {
      expect(inviteTeamMemberMock).toHaveBeenCalledWith(101);
    });

    expect(await screen.findByText(/Invitația a fost trimisă/i)).toBeInTheDocument();
  });

  it("shows clear message for 403 and 503 and disables ineligible row action", async () => {
    inviteTeamMemberMock
      .mockRejectedValueOnce(new ApiRequestError("forbidden", 403))
      .mockRejectedValueOnce(new ApiRequestError("temporarily unavailable", 503));

    render(<SettingsTeamPage />);

    const buttons = await screen.findAllByRole("button", { name: "Trimite invitație" });
    expect(buttons[1]).toBeDisabled();

    fireEvent.click(buttons[0]);
    expect(await screen.findByText("Nu ai permisiunea să trimiți invitații pentru acest utilizator")).toBeInTheDocument();

    fireEvent.click(buttons[0]);
    expect(await screen.findByText(/Invitațiile sunt indisponibile temporar/i)).toBeInTheDocument();
  });

  it("renders membership status badges and lifecycle actions for active vs inactive rows", async () => {
    render(<SettingsTeamPage />);

    expect(await screen.findByText("Activ")).toBeInTheDocument();
    expect(await screen.findByText("Inactiv")).toBeInTheDocument();

    expect(screen.getByRole("button", { name: "Dezactivează" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Reactivează" })).toBeInTheDocument();
  });

  it("deactivates active membership, shows success message, and refetches list", async () => {
    render(<SettingsTeamPage />);

    fireEvent.click(await screen.findByRole("button", { name: "Dezactivează" }));

    await waitFor(() => {
      expect(apiRequestMock.mock.calls.some((call) => call[0] === "/team/members/101/deactivate" && call[1]?.method === "POST")).toBe(true);
    });

    await waitFor(() => {
      const memberListCalls = apiRequestMock.mock.calls.filter((call) => String(call[0]).startsWith("/team/members?"));
      expect(memberListCalls.length).toBeGreaterThan(1);
    });
    expect(await screen.findByText(/Accesul a fost dezactivat/i)).toBeInTheDocument();
  });

  it("reactivates inactive membership and refetches list", async () => {
    render(<SettingsTeamPage />);

    fireEvent.click(await screen.findByRole("button", { name: "Reactivează" }));

    await waitFor(() => {
      expect(apiRequestMock.mock.calls.some((call) => call[0] === "/team/members/102/reactivate" && call[1]?.method === "POST")).toBe(true);
    });

    expect(await screen.findByText(/Accesul a fost reactivat/i)).toBeInTheDocument();
  });

  it("shows lifecycle loading per-row and handles 403/404/409 errors", async () => {
    apiRequestMock.mockImplementation((path: string, options?: { method?: string; body?: string }) => {
      if (path.startsWith("/team/members?")) {
        return Promise.resolve({
          items: [
            { id: 201, membership_id: 201, user_id: 301, first_name: "A", last_name: "One", email: "a@example.com", phone: "", extension: "", user_type: "agency", user_role: "admin", location: "RO", subaccount: "Toate", membership_status: "active" },
            { id: 202, membership_id: 202, user_id: 302, first_name: "B", last_name: "Two", email: "b@example.com", phone: "", extension: "", user_type: "agency", user_role: "member", location: "RO", subaccount: "Toate", membership_status: "active" },
            { id: 203, membership_id: 203, user_id: 303, first_name: "C", last_name: "Three", email: "c@example.com", phone: "", extension: "", user_type: "agency", user_role: "member", location: "RO", subaccount: "Toate", membership_status: "active" },
          ], total: 3, page: 1, page_size: 10,
        });
      }
      if (path === "/team/subaccount-options") return Promise.resolve({ items: [] });
      if (path === "/team/module-catalog?scope=subaccount") return Promise.resolve({ items: [] });
      if (path === "/team/module-catalog?scope=agency") return Promise.resolve({ items: [] });
      if (path === "/team/members/201/deactivate" && options?.method === "POST") return new Promise(() => {});
      if (path === "/team/members/202/deactivate" && options?.method === "POST") return Promise.reject(new ApiRequestError("forbidden", 403));
      if (path === "/team/members/203/deactivate" && options?.method === "POST") return Promise.reject(new ApiRequestError("conflict", 409));
      return Promise.reject(new Error(`Unexpected path: ${path}`));
    });

    render(<SettingsTeamPage />);

    const buttons = await screen.findAllByRole("button", { name: "Dezactivează" });
    fireEvent.click(buttons[0]);

    fireEvent.click(buttons[1]);
    expect(await screen.findByText(/permisiuni suficiente/i)).toBeInTheDocument();

    fireEvent.click(buttons[2]);
    expect(await screen.findByText(/moștenit/i)).toBeInTheDocument();
  });

  it("renders delete user action and confirms hard delete message", async () => {
    render(<SettingsTeamPage />);

    const deleteButtons = await screen.findAllByRole("button", { name: "Șterge utilizator" });
    expect(deleteButtons.length).toBeGreaterThan(0);

    fireEvent.click(deleteButtons[0]);

    await waitFor(() => {
      expect(window.confirm).toHaveBeenCalledWith(
        "Sigur vrei să ștergi complet acest utilizator din sistem? Acțiunea elimină utilizatorul din users, toate memberships, permisiunile și tokenurile asociate.",
      );
    });
  });

  it("does not call hard delete endpoint when confirmation is cancelled", async () => {
    vi.spyOn(window, "confirm").mockReturnValueOnce(false);
    render(<SettingsTeamPage />);

    const deleteButtons = await screen.findAllByRole("button", { name: "Șterge utilizator" });
    fireEvent.click(deleteButtons[0]);

    await waitFor(() => {
      expect(deleteTeamUserMock).not.toHaveBeenCalled();
    });
  });

  it("hard deletes user on success and refetches list", async () => {
    render(<SettingsTeamPage />);

    const deleteButtons = await screen.findAllByRole("button", { name: "Șterge utilizator" });
    fireEvent.click(deleteButtons[0]);

    await waitFor(() => {
      expect(deleteTeamUserMock).toHaveBeenCalledWith(201);
    });

    await waitFor(() => {
      const memberListCalls = apiRequestMock.mock.calls.filter((call) => String(call[0]).startsWith("/team/members?"));
      expect(memberListCalls.length).toBeGreaterThan(1);
    });

    expect(await screen.findByText(/Utilizator șters complet din sistem/i)).toBeInTheDocument();
  });

  it("handles hard delete 403 and 404 with clear feedback", async () => {
    apiRequestMock.mockImplementation((path: string, options?: { method?: string; body?: string }) => {
      if (path.startsWith("/team/members?")) {
        return Promise.resolve({
          items: [
            { id: 401, membership_id: 401, user_id: 501, first_name: "A", last_name: "One", email: "a@example.com", phone: "", extension: "", user_type: "agency", user_role: "admin", location: "RO", subaccount: "Toate", membership_status: "active" },
            { id: 402, membership_id: 402, user_id: 502, first_name: "B", last_name: "Two", email: "b@example.com", phone: "", extension: "", user_type: "agency", user_role: "member", location: "RO", subaccount: "Toate", membership_status: "active" },
          ],
          total: 2,
          page: 1,
          page_size: 10,
        });
      }
      if (path === "/team/subaccount-options") return Promise.resolve({ items: [] });
      if (path === "/team/module-catalog?scope=subaccount") return Promise.resolve({ items: [] });
      if (path === "/team/module-catalog?scope=agency") return Promise.resolve({ items: [] });
      return Promise.reject(new Error(`Unexpected path: ${path}`));
    });
    deleteTeamUserMock
      .mockRejectedValueOnce(new ApiRequestError("forbidden", 403))
      .mockRejectedValueOnce(new ApiRequestError("Utilizator inexistent", 404));

    render(<SettingsTeamPage />);

    const deleteButtons = await screen.findAllByRole("button", { name: "Șterge utilizator" });
    fireEvent.click(deleteButtons[0]);
    expect(await screen.findByText(/permisiuni suficiente pentru a șterge acest utilizator/i)).toBeInTheDocument();

    fireEvent.click(deleteButtons[1]);
    expect(await screen.findByText(/Utilizator inexistent/i)).toBeInTheDocument();
  });

  it("handles hard delete 409 self-delete conflict with clear feedback", async () => {
    apiRequestMock.mockImplementation((path: string, options?: { method?: string; body?: string }) => {
      if (path.startsWith("/team/members?")) {
        return Promise.resolve({
          items: [
            { id: 403, membership_id: 403, user_id: 503, first_name: "C", last_name: "Three", email: "c@example.com", phone: "", extension: "", user_type: "agency", user_role: "member", location: "RO", subaccount: "Toate", membership_status: "active" },
          ],
          total: 1,
          page: 1,
          page_size: 10,
        });
      }
      if (path === "/team/subaccount-options") return Promise.resolve({ items: [] });
      if (path === "/team/module-catalog?scope=subaccount") return Promise.resolve({ items: [] });
      if (path === "/team/module-catalog?scope=agency") return Promise.resolve({ items: [] });
      return Promise.reject(new Error(`Unexpected path: ${path}`));
    });
    deleteTeamUserMock.mockRejectedValueOnce(new ApiRequestError("Nu îți poți șterge propriul utilizator din sesiunea curentă", 409));

    render(<SettingsTeamPage />);

    const deleteButtons = await screen.findAllByRole("button", { name: "Șterge utilizator" });
    fireEvent.click(deleteButtons[0]);
    expect(await screen.findByText(/Nu îți poți șterge propriul utilizator din această sesiune/i)).toBeInTheDocument();
  });


  it("handles lifecycle 404 with clear message", async () => {
    apiRequestMock.mockImplementation((path: string, options?: { method?: string; body?: string }) => {
      if (path.startsWith("/team/members?")) {
        return Promise.resolve({
          items: [{ id: 301, membership_id: 301, user_id: 401, first_name: "A", last_name: "One", email: "a@example.com", phone: "", extension: "", user_type: "agency", user_role: "admin", location: "RO", subaccount: "Toate", membership_status: "active" }],
          total: 1, page: 1, page_size: 10,
        });
      }
      if (path === "/team/subaccount-options") return Promise.resolve({ items: [] });
      if (path === "/team/module-catalog?scope=subaccount") return Promise.resolve({ items: [] });
      if (path === "/team/module-catalog?scope=agency") return Promise.resolve({ items: [] });
      if (path === "/team/members/301/deactivate" && options?.method === "POST") return Promise.reject(new ApiRequestError("gone", 404));
      return Promise.reject(new Error(`Unexpected path: ${path}`));
    });

    render(<SettingsTeamPage />);
    fireEvent.click(await screen.findByRole("button", { name: "Dezactivează" }));
    expect(await screen.findByText(/Membership inexistent sau inaccesibil/i)).toBeInTheDocument();
  });

});
