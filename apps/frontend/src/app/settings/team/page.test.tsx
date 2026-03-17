import React from "react";
import { describe, expect, it, vi, beforeEach } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import SettingsTeamPage from "./page";

const apiRequestMock = vi.fn();
const inviteTeamMemberMock = vi.fn();

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    apiRequest: (...args: unknown[]) => apiRequestMock(...args),
    inviteTeamMember: (...args: unknown[]) => inviteTeamMemberMock(...args),
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
  beforeEach(() => {
    apiRequestMock.mockReset();
    inviteTeamMemberMock.mockReset();
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
      if (path === "/team/members" && options?.method === "POST") {
        return Promise.resolve({ item: { id: 1 } });
      }
      return Promise.reject(new Error(`Unexpected path: ${path}`));
    });
    inviteTeamMemberMock.mockResolvedValue({ message: "Invitația a fost trimisă" });
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

  it("requires a real subaccount only for client users and submits selected id as string", async () => {
    render(<SettingsTeamPage />);

    fireEvent.click(screen.getByRole("button", { name: /Adaugă Utilizator/i }));

    const subaccountSelect = await screen.findByRole("combobox", { name: "Sub-cont" });
    expect(subaccountSelect).toBeDisabled();

    fireEvent.change(screen.getByRole("combobox", { name: "Tip Utilizator" }), { target: { value: "client" } });
    expect(subaccountSelect).not.toBeDisabled();

    fireEvent.change(screen.getByRole("textbox", { name: "Prenume" }), { target: { value: "Ana" } });
    fireEvent.change(screen.getByRole("textbox", { name: "Nume" }), { target: { value: "Ionescu" } });
    fireEvent.change(screen.getByRole("textbox", { name: /Email/i }), { target: { value: "ana@example.com" } });

    fireEvent.click(screen.getByRole("button", { name: "Pasul Următor" }));
    expect(screen.getByText(/Selectarea unui sub-cont este obligatorie/i)).toBeInTheDocument();

    fireEvent.change(subaccountSelect, { target: { value: "2" } });
    fireEvent.click(screen.getByRole("button", { name: "Pasul Următor" }));

    await waitFor(() => {
      const postCall = apiRequestMock.mock.calls.find((call) => call[0] === "/team/members" && call[1]?.method === "POST");
      expect(postCall).toBeTruthy();
      const body = JSON.parse(String(postCall?.[1]?.body ?? "{}"));
      expect(body.user_type).toBe("client");
      expect(body.subaccount).toBe("2");
    });
  });


  it("renders auto-invite checkbox in create form and keeps default unchecked", async () => {
    render(<SettingsTeamPage />);

    fireEvent.click(screen.getByRole("button", { name: /Adaugă Utilizator/i }));

    const checkbox = await screen.findByRole("checkbox", { name: "Trimite invitație imediat după creare" });
    expect(checkbox).not.toBeChecked();
  });

  it("create without auto-invite does not call invite endpoint", async () => {
    render(<SettingsTeamPage />);

    fireEvent.click(screen.getByRole("button", { name: /Adaugă Utilizator/i }));
    fireEvent.change(screen.getByRole("textbox", { name: "Prenume" }), { target: { value: "Ana" } });
    fireEvent.change(screen.getByRole("textbox", { name: "Nume" }), { target: { value: "Ionescu" } });
    fireEvent.change(screen.getByRole("textbox", { name: /Email/i }), { target: { value: "ana@example.com" } });

    fireEvent.click(screen.getByRole("button", { name: "Pasul Următor" }));

    await waitFor(() => {
      const postCall = apiRequestMock.mock.calls.find((call) => call[0] === "/team/members" && call[1]?.method === "POST");
      expect(postCall).toBeTruthy();
    });

    expect(inviteTeamMemberMock).not.toHaveBeenCalled();
    expect(await screen.findByText("Utilizator adăugat cu succes.")).toBeInTheDocument();
  });

  it("create with auto-invite checked calls invite with created membership id", async () => {
    apiRequestMock.mockImplementation((path: string, options?: { method?: string; body?: string }) => {
      if (path.startsWith("/team/members?")) {
        return Promise.resolve({ items: [], total: 0, page: 1, page_size: 10 });
      }
      if (path === "/team/subaccount-options") return Promise.resolve({ items: [] });
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

    await waitFor(() => expect(inviteTeamMemberMock).toHaveBeenCalledWith(777));
    expect(await screen.findByText("Utilizatorul a fost creat și invitația a fost trimisă")).toBeInTheDocument();

    expect(screen.getByRole("button", { name: /Adaugă Utilizator/i })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /Adaugă Utilizator/i }));
    expect(await screen.findByRole("checkbox", { name: "Trimite invitație imediat după creare" })).not.toBeChecked();
  });

  it("create success + invite 503 shows partial success message", async () => {
    const { ApiRequestError } = await import("@/lib/api");
    inviteTeamMemberMock.mockRejectedValueOnce(new ApiRequestError("temporarily unavailable", 503));

    apiRequestMock.mockImplementation((path: string, options?: { method?: string; body?: string }) => {
      if (path.startsWith("/team/members?")) {
        return Promise.resolve({ items: [], total: 0, page: 1, page_size: 10 });
      }
      if (path === "/team/subaccount-options") return Promise.resolve({ items: [] });
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

    expect(await screen.findByText(/Utilizatorul a fost creat, dar invitația nu a putut fi trimisă\./i)).toBeInTheDocument();
    expect(screen.getByText(/Invitațiile sunt indisponibile temporar/i)).toBeInTheDocument();
  });

  it("create failure does not call invite", async () => {
    apiRequestMock.mockImplementation((path: string, options?: { method?: string; body?: string }) => {
      if (path.startsWith("/team/members?")) {
        return Promise.resolve({ items: [], total: 0, page: 1, page_size: 10 });
      }
      if (path === "/team/subaccount-options") return Promise.resolve({ items: [] });
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

    expect(await screen.findByText("Nu am putut adăuga utilizatorul.")).toBeInTheDocument();
    expect(inviteTeamMemberMock).not.toHaveBeenCalled();
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
    const { ApiRequestError } = await import("@/lib/api");
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
});
