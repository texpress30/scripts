import React from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import AgencyAccountsPage from "./page";

const apiMock = vi.hoisted(() => ({ apiRequest: vi.fn() }));

vi.mock("@/lib/api", () => ({ apiRequest: apiMock.apiRequest }));
vi.mock("@/components/ProtectedPage", () => ({ ProtectedPage: ({ children }: { children: React.ReactNode }) => <>{children}</> }));
vi.mock("@/components/AppShell", () => ({ AppShell: ({ children }: { children: React.ReactNode }) => <>{children}</> }));
vi.mock("next/link", () => ({
  default: ({ href, children, className }: { href: string; children: React.ReactNode; className?: string }) => (
    <a href={href} className={className}>
      {children}
    </a>
  ),
}));

function mockBasePayloads() {
  apiMock.apiRequest.mockImplementation((path: string) => {
    if (path === "/clients") {
      return Promise.resolve({ items: [{ id: 11, name: "Client A", owner_email: "a@x.com", display_id: 1 }] });
    }
    if (path === "/clients/accounts/summary") {
      return Promise.resolve({ items: [{ platform: "google_ads", connected_count: 2, last_import_at: null }] });
    }
    if (path === "/clients/accounts/google") {
      return Promise.resolve({
        count: 2,
        items: [
          {
            id: "1001",
            name: "Account One",
            attached_client_id: 11,
            attached_client_name: "Client A",
            last_run_status: "running",
            has_active_sync: true,
            backfill_completed_through: "2026-01-10",
          },
          {
            id: "1002",
            name: "Account Two",
            attached_client_id: null,
            attached_client_name: null,
            last_run_status: "done",
            backfill_completed_through: null,
          },
        ],
      });
    }
    return Promise.resolve({});
  });
}

describe("AgencyAccountsPage list redesign", () => {
  beforeEach(() => {
    apiMock.apiRequest.mockReset();
    mockBasePayloads();
  });

  it("renders column headers and preserves account detail link + core actions", async () => {
    render(<AgencyAccountsPage />);

    expect((await screen.findAllByText("Selecție")).length).toBeGreaterThan(0);
    expect((screen.getAllByText("Cont")).length).toBeGreaterThan(0);
    expect((screen.getAllByText("Sync progress")).length).toBeGreaterThan(0);
    expect((screen.getAllByText("Client atașat")).length).toBeGreaterThan(0);
    expect((screen.getAllByText("Acțiuni")).length).toBeGreaterThan(0);
    expect((screen.getAllByText("Detach")).length).toBeGreaterThan(0);

    const accountLink = screen.getByRole("link", { name: "Account One" });
    expect(accountLink).toHaveAttribute("href", "/agency-accounts/google_ads/1001");

    expect(screen.getByRole("button", { name: /Refresh names/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Download historical/i })).toBeInTheDocument();
  });

  it("filters rows by attached client name and shows empty state", async () => {
    render(<AgencyAccountsPage />);
    await screen.findByText("Account One");

    fireEvent.change(screen.getByLabelText("Filtru client"), { target: { value: "client a" } });
    expect(screen.getByText("Account One")).toBeInTheDocument();
    expect(screen.queryByText("Account Two")).not.toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Filtru client"), { target: { value: "does-not-exist" } });
    await waitFor(() => {
      expect(screen.getByText("Nu există conturi care să corespundă filtrului de client.")).toBeInTheDocument();
    });
  });

  it("keeps sync progress visible and detach action separated", async () => {
    render(<AgencyAccountsPage />);

    expect(await screen.findByText("Status: running")).toBeInTheDocument();
    expect((screen.getAllByText("Sync progress")).length).toBeGreaterThan(0);
    expect((screen.getAllByText("Detach")).length).toBeGreaterThan(0);
    expect(screen.getAllByRole("button", { name: "Detach" }).length).toBeGreaterThanOrEqual(1);
  });
});
