import React from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, within } from "@testing-library/react";

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

describe("AgencyAccountsPage TikTok unified workspace", () => {
  beforeEach(() => {
    apiMock.apiRequest.mockReset();
    apiMock.postAccountSyncProgressBatch.mockReset();
    apiMock.postAccountSyncProgressBatch.mockResolvedValue({ platform: "google_ads", requested_count: 0, results: [] });

    apiMock.apiRequest.mockImplementation((path: string) => {
      if (path === "/clients") {
        return Promise.resolve({ items: [{ id: 1, name: "Client A", owner_email: "a@x.com" }] });
      }
      if (path === "/clients/accounts/summary") {
        return Promise.resolve({
          items: [
            { platform: "google_ads", connected_count: 2, last_import_at: null },
            { platform: "tiktok_ads", connected_count: 1, last_import_at: null },
          ],
        });
      }
      if (path === "/clients/accounts/google") {
        return Promise.resolve({ items: [], count: 0 });
      }
      if (path === "/clients/accounts/tiktok_ads") {
        return Promise.resolve({ count: 1, items: [{ id: "tt_1", name: "TikTok One", attached_client_id: null }] });
      }
      return Promise.resolve({});
    });
  });

  it("renders TikTok in same shell/table layout used by Google", async () => {
    render(<AgencyAccountsPage />);

    const tiktokButton = await screen.findByRole("button", { name: /TikTok Ads/i });
    fireEvent.click(tiktokButton);

    expect(await screen.findByTestId("platform-workspace-tiktok_ads")).toBeInTheDocument();
    expect(screen.getByTestId("provider-unified-table-shell")).toBeInTheDocument();
    expect(screen.getAllByText("Selecție").length).toBeGreaterThan(0);
  });

  it("renders attached client when payload uses client_id/client_name", async () => {
    apiMock.apiRequest.mockImplementation((path: string) => {
      if (path === "/clients") {
        return Promise.resolve({ items: [{ id: 1, name: "Client A", owner_email: "a@x.com" }] });
      }
      if (path === "/clients/accounts/summary") {
        return Promise.resolve({ items: [{ platform: "google_ads", connected_count: 0, last_import_at: null }, { platform: "tiktok_ads", connected_count: 1, last_import_at: null }] });
      }
      if (path === "/clients/accounts/google") {
        return Promise.resolve({ items: [], count: 0 });
      }
      if (path === "/clients/accounts/tiktok_ads") {
        return Promise.resolve({ items: [{ id: "tt_1", name: "TikTok One", client_id: 1, client_name: "Client A" }], count: 1 });
      }
      return Promise.resolve({});
    });

    render(<AgencyAccountsPage />);
    fireEvent.click(await screen.findByRole("button", { name: /TikTok Ads/i }));

    expect(await screen.findByText("Client A")).toBeInTheDocument();
    expect(screen.queryByText("Neatașat la client")).not.toBeInTheDocument();
  });

  it("renders attached client when payload uses attached_client_id/attached_client_name", async () => {
    apiMock.apiRequest.mockImplementation((path: string) => {
      if (path === "/clients") {
        return Promise.resolve({ items: [{ id: 1, name: "Client A", owner_email: "a@x.com" }] });
      }
      if (path === "/clients/accounts/summary") {
        return Promise.resolve({ items: [{ platform: "google_ads", connected_count: 0, last_import_at: null }, { platform: "tiktok_ads", connected_count: 1, last_import_at: null }] });
      }
      if (path === "/clients/accounts/google") {
        return Promise.resolve({ items: [], count: 0 });
      }
      if (path === "/clients/accounts/tiktok_ads") {
        return Promise.resolve({ items: [{ id: "tt_1", name: "TikTok One", attached_client_id: 1, attached_client_name: "Client A" }], count: 1 });
      }
      return Promise.resolve({});
    });

    render(<AgencyAccountsPage />);
    fireEvent.click(await screen.findByRole("button", { name: /TikTok Ads/i }));

    expect(await screen.findByText("Client A")).toBeInTheDocument();
    expect(screen.queryByText("Neatașat la client")).not.toBeInTheDocument();
  });

  it("keeps unattached row rendering when no client mapping exists", async () => {
    render(<AgencyAccountsPage />);
    fireEvent.click(await screen.findByRole("button", { name: /TikTok Ads/i }));
    expect(await screen.findByText("Neatașat la client")).toBeInTheDocument();
  });

  it("attach success + reload renders attached client", async () => {
    let reloadCount = 0;
    apiMock.apiRequest.mockImplementation((path: string, options?: { method?: string; body?: string }) => {
      if (path === "/clients") {
        return Promise.resolve({ items: [{ id: 1, name: "Client A", owner_email: "a@x.com", display_id: 1 }] });
      }
      if (path === "/clients/accounts/summary") {
        return Promise.resolve({ items: [{ platform: "google_ads", connected_count: 0, last_import_at: null }, { platform: "tiktok_ads", connected_count: 1, last_import_at: null }] });
      }
      if (path === "/clients/accounts/google") {
        return Promise.resolve({ items: [], count: 0 });
      }
      if (path === "/clients/accounts/tiktok_ads") {
        reloadCount += 1;
        if (reloadCount === 1) {
          return Promise.resolve({ items: [{ id: "tt_1", name: "TikTok One", attached_client_id: null }], count: 1 });
        }
        return Promise.resolve({ items: [{ id: "tt_1", name: "TikTok One", client_id: 1, client_name: "Client A" }], count: 1 });
      }
      if (path === "/clients/1/attach-account") {
        expect(options?.method).toBe("POST");
        expect(options?.body).toContain('"platform":"tiktok_ads"');
        expect(options?.body).toContain('"account_id":"tt_1"');
        return Promise.resolve({ status: "ok" });
      }
      return Promise.resolve({});
    });

    render(<AgencyAccountsPage />);
    fireEvent.click(await screen.findByRole("button", { name: /TikTok Ads/i }));

    await screen.findByText("Neatașat la client");
    const selects = await screen.findAllByRole("combobox");
    const attachSelect = selects.find((element) => within(element).queryByText("Atașează la client..."));
    expect(attachSelect).toBeTruthy();
    fireEvent.change(attachSelect!, { target: { value: "1" } });
    fireEvent.click(screen.getByRole("button", { name: "Attach" }));

    expect(await screen.findByText("Client A")).toBeInTheDocument();
    expect(screen.queryByText("Neatașat la client")).not.toBeInTheDocument();
  });

  it("shows TikTok empty state in unified table container", async () => {
    apiMock.apiRequest.mockImplementation((path: string) => {
      if (path === "/clients") {
        return Promise.resolve({ items: [{ id: 1, name: "Client A", owner_email: "a@x.com" }] });
      }
      if (path === "/clients/accounts/summary") {
        return Promise.resolve({
          items: [
            { platform: "google_ads", connected_count: 0, last_import_at: null },
            { platform: "tiktok_ads", connected_count: 0, last_import_at: null },
          ],
        });
      }
      if (path === "/clients/accounts/google") {
        return Promise.resolve({ items: [], count: 0 });
      }
      if (path === "/clients/accounts/tiktok_ads") {
        return Promise.resolve({ items: [], count: 0 });
      }
      return Promise.resolve({});
    });

    render(<AgencyAccountsPage />);
    fireEvent.click(await screen.findByRole("button", { name: /TikTok Ads/i }));
    expect(await screen.findByTestId("provider-unified-empty-state")).toBeInTheDocument();
  });
});
