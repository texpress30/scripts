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

describe("AgencyAccountsPage Meta panel composition", () => {
  beforeEach(() => {
    apiMock.apiRequest.mockReset();
    apiMock.postAccountSyncProgressBatch.mockReset();
    apiMock.postAccountSyncProgressBatch.mockResolvedValue({ platform: "google_ads", requested_count: 0, results: [] });

    apiMock.apiRequest.mockImplementation((path: string) => {
      if (path === "/clients") {
        return Promise.resolve({
          items: [{ id: 11, name: "Client A", owner_email: "a@example.com", display_id: 1 }],
        });
      }
      if (path === "/clients/accounts/summary") {
        return Promise.resolve({
          items: [
            { platform: "google_ads", connected_count: 2, last_import_at: null },
            { platform: "meta_ads", connected_count: 1, last_import_at: null },
          ],
        });
      }
      if (path === "/clients/accounts/google") {
        return Promise.resolve({ count: 1, items: [{ id: "1001", name: "G1", attached_client_id: 11, attached_client_name: "Client A" }] });
      }
      if (path === "/clients/accounts/meta_ads") {
        return Promise.resolve({ count: 1, items: [{ id: "act_2001", name: "Meta One", attached_client_id: null }] });
      }
      return Promise.resolve({});
    });
  });

  it("renders Meta panel when selecting Meta Ads card", async () => {
    render(<AgencyAccountsPage />);

    fireEvent.click(await screen.findByRole("button", { name: /Meta Ads/i }));

    expect(await screen.findByRole("heading", { name: "Meta Ads Accounts" })).toBeInTheDocument();
  });
});
