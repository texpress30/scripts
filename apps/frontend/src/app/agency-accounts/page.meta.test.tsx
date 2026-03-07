import React from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";

import AgencyAccountsPage from "./page";

const apiMock = vi.hoisted(() => ({
  apiRequest: vi.fn(),
  postAccountSyncProgressBatch: vi.fn(),
}));

vi.mock("@/lib/api", () => ({
  apiRequest: apiMock.apiRequest,
  postAccountSyncProgressBatch: apiMock.postAccountSyncProgressBatch,
}));
vi.mock("@/components/ProtectedPage", () => ({ ProtectedPage: ({ children }: { children: React.ReactNode }) => <>{children}</> }));
vi.mock("@/components/AppShell", () => ({ AppShell: ({ children }: { children: React.ReactNode }) => <>{children}</> }));
vi.mock("next/link", () => ({
  default: ({ href, children }: { href: string; children: React.ReactNode }) => <a href={href}>{children}</a>,
}));

describe("AgencyAccountsPage Meta mappings", () => {
  beforeEach(() => {
    apiMock.apiRequest.mockReset();
    apiMock.postAccountSyncProgressBatch.mockReset();
    apiMock.postAccountSyncProgressBatch.mockResolvedValue({ platform: "google_ads", requested_count: 0, results: [] });
  });

  function setupMetaMock(options?: { attachError?: string; detachError?: string; empty?: boolean }) {
    let metaState =
      options?.empty
        ? []
        : [
            {
              platform: "meta_ads",
              account_id: "act_100",
              account_name: "Meta One",
              client_id: null,
              client_name: null,
              is_attached: false,
              status: "ACTIVE",
              currency: "USD",
              timezone: "UTC",
            },
            {
              platform: "meta_ads",
              account_id: "act_200",
              account_name: "Meta Two",
              client_id: 11,
              client_name: "Client A",
              is_attached: true,
              status: "PAUSED",
              currency: "EUR",
              timezone: "Europe/Bucharest",
            },
          ];

    apiMock.apiRequest.mockImplementation((path: string, optionsArg?: { method?: string; body?: string }) => {
      if (path === "/clients") {
        return Promise.resolve({
          items: [
            { id: 11, name: "Client A", owner_email: "a@x.com", display_id: 1 },
            { id: 12, name: "Client B", owner_email: "b@x.com", display_id: 2 },
          ],
        });
      }
      if (path === "/clients/accounts/summary") {
        return Promise.resolve({
          items: [
            { platform: "google_ads", connected_count: 3, last_import_at: null },
            { platform: "meta_ads", connected_count: 2, last_import_at: "2026-03-07T10:00:00Z" },
          ],
        });
      }
      if (path === "/clients/accounts/google") {
        return Promise.resolve({ count: 1, items: [{ id: "1001", name: "Account One", attached_client_id: 11, attached_client_name: "Client A" }] });
      }
      if (path === "/clients/accounts/meta_ads") {
        return Promise.resolve({ platform: "meta_ads", count: metaState.length, items: metaState, last_import_at: "2026-03-07T10:00:00Z" });
      }
      if (path === "/clients/11/attach-account") {
        if (options?.attachError) return Promise.reject(new Error(options.attachError));
        expect(optionsArg).toEqual({ method: "POST", body: JSON.stringify({ platform: "meta_ads", account_id: "act_100" }) });
        metaState = metaState.map((item) => (item.account_id === "act_100" ? { ...item, client_id: 11, client_name: "Client A", is_attached: true } : item));
        return Promise.resolve({ status: "ok" });
      }
      if (path === "/clients/11/detach-account") {
        if (options?.detachError) return Promise.reject(new Error(options.detachError));
        expect(optionsArg).toEqual({ method: "POST", body: JSON.stringify({ platform: "meta_ads", account_id: "act_200" }) });
        metaState = metaState.map((item) => (item.account_id === "act_200" ? { ...item, client_id: null, client_name: null, is_attached: false } : item));
        return Promise.resolve({ status: "ok" });
      }
      return Promise.resolve({});
    });
  }

  it("loads and renders Meta accounts attached vs unattached", async () => {
    setupMetaMock();
    render(<AgencyAccountsPage />);

    fireEvent.click(await screen.findByRole("button", { name: /Meta Ads/i }));

    expect(await screen.findByText("Meta One")).toBeInTheDocument();
    expect(screen.getByText("Meta Two")).toBeInTheDocument();
    expect(screen.getAllByText("Atașat").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Neatașat").length).toBeGreaterThan(0);
    expect(screen.getByText(/Client: Client A #11/)).toBeInTheDocument();
  });

  it("attaches unattached Meta account and refreshes list", async () => {
    setupMetaMock();
    render(<AgencyAccountsPage />);
    fireEvent.click(await screen.findByRole("button", { name: /Meta Ads/i }));
    await screen.findByText("Meta One");

    fireEvent.change(screen.getByTestId("meta-client-select-act_100"), { target: { value: "11" } });
    fireEvent.click(screen.getByTestId("meta-attach-act_100"));

    await waitFor(() => {
      expect(screen.getByText(/a fost atașat clientului Client A/)).toBeInTheDocument();
      const attachedRow = screen.getByTestId("meta-row-act_100");
      expect(within(attachedRow).getByText(/Client: Client A #11/)).toBeInTheDocument();
    });
  });

  it("detaches attached Meta account and refreshes list", async () => {
    setupMetaMock();
    render(<AgencyAccountsPage />);
    fireEvent.click(await screen.findByRole("button", { name: /Meta Ads/i }));
    await screen.findByText("Meta Two");

    fireEvent.click(screen.getByTestId("meta-detach-act_200"));

    await waitFor(() => {
      expect(screen.getByText(/a fost detașat de la clientul Client A/)).toBeInTheDocument();
      const detachedRow = screen.getByTestId("meta-row-act_200");
      expect(within(detachedRow).getByText("Neatașat")).toBeInTheDocument();
    });
  });

  it("shows attach error message", async () => {
    setupMetaMock({ attachError: "Meta attach failed" });
    render(<AgencyAccountsPage />);
    fireEvent.click(await screen.findByRole("button", { name: /Meta Ads/i }));
    await screen.findByText("Meta One");

    fireEvent.change(screen.getByTestId("meta-client-select-act_100"), { target: { value: "11" } });
    fireEvent.click(screen.getByTestId("meta-attach-act_100"));

    expect(await screen.findByText("Meta attach failed")).toBeInTheDocument();
  });

  it("shows empty state when no Meta accounts imported", async () => {
    setupMetaMock({ empty: true });
    render(<AgencyAccountsPage />);
    fireEvent.click(await screen.findByRole("button", { name: /Meta Ads/i }));

    expect(await screen.findByText(/Nu există conturi Meta importate în registry/)).toBeInTheDocument();
  });
});
