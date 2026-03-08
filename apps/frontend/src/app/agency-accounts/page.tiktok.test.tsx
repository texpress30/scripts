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
vi.mock("./TikTokAgencyAccountsPanel", () => ({
  TikTokAgencyAccountsPanel: () => <div data-testid="tiktok-agency-panel">TikTok Panel</div>,
}));

describe("AgencyAccountsPage TikTok composition", () => {
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
      return Promise.resolve({});
    });
  });

  it("renders page and includes TikTok panel when TikTok card is selected", async () => {
    render(<AgencyAccountsPage />);

    const tiktokButton = await screen.findByRole("button", { name: /TikTok Ads/i });
    fireEvent.click(tiktokButton);

    expect(await screen.findByTestId("tiktok-agency-panel")).toBeInTheDocument();
    expect(screen.getByText("TikTok Panel")).toBeInTheDocument();
  });
});
