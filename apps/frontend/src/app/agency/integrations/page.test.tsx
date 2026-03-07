import React from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";

import AgencyIntegrationsPage from "./page";

const apiMock = vi.hoisted(() => ({
  apiRequest: vi.fn(),
}));

vi.mock("@/lib/api", () => ({
  apiRequest: apiMock.apiRequest,
}));

vi.mock("@/components/ProtectedPage", () => ({ ProtectedPage: ({ children }: { children: React.ReactNode }) => <>{children}</> }));
vi.mock("@/components/AppShell", () => ({ AppShell: ({ children }: { children: React.ReactNode }) => <>{children}</> }));

describe("AgencyIntegrationsPage", () => {
  beforeEach(() => {
    apiMock.apiRequest.mockReset();
  });

  it("renders exactly one Meta integration card heading", async () => {
    apiMock.apiRequest.mockImplementation((path: string) => {
      if (path === "/integrations/google-ads/status") {
        return Promise.resolve({ status: "connected", message: "ok", mode: "oauth", connected_accounts_count: 2 });
      }
      if (path === "/integrations/meta-ads/status") {
        return Promise.resolve({ provider: "meta_ads", status: "connected", message: "Meta ready", oauth_configured: true, has_usable_token: true, token_source: "database" });
      }
      return Promise.resolve({});
    });

    render(<AgencyIntegrationsPage />);

    const headings = await screen.findAllByRole("heading", { name: "Meta Ads" });
    expect(headings).toHaveLength(1);
  });
});
