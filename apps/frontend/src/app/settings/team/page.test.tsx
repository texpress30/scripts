import React from "react";
import { describe, expect, it, vi, beforeEach } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import SettingsTeamPage from "./page";

const apiRequestMock = vi.fn();

vi.mock("@/lib/api", () => ({
  apiRequest: (...args: unknown[]) => apiRequestMock(...args),
}));

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
    apiRequestMock.mockImplementation((path: string, options?: { method?: string; body?: string }) => {
      if (path.startsWith("/team/members?")) {
        return Promise.resolve({ items: [], total: 0, page: 1, page_size: 10 });
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
});
