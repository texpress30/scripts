import React from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";

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
