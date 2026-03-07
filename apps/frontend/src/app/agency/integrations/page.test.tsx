import React from "react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";

import AgencyIntegrationsPage from "./page";

const apiMock = vi.hoisted(() => ({
  apiRequest: vi.fn(),
}));

vi.mock("@/lib/api", () => ({
  apiRequest: apiMock.apiRequest,
}));

vi.mock("@/components/ProtectedPage", () => ({ ProtectedPage: ({ children }: { children: React.ReactNode }) => <>{children}</> }));
vi.mock("@/components/AppShell", () => ({ AppShell: ({ children }: { children: React.ReactNode }) => <>{children}</> }));

describe("AgencyIntegrationsPage Meta card", () => {
  beforeEach(() => {
    apiMock.apiRequest.mockReset();
  });

  it("renders Google card and Meta card with connected Meta status from API", async () => {
    apiMock.apiRequest.mockImplementation((path: string) => {
      if (path === "/integrations/google-ads/status") {
        return Promise.resolve({ status: "connected", message: "ok", mode: "oauth", connected_accounts_count: 2 });
      }
      if (path === "/integrations/meta-ads/status") {
        return Promise.resolve({ provider: "meta_ads", status: "connected", message: "Meta Ads token is available." });
      }
      return Promise.resolve({});
    });

    render(<AgencyIntegrationsPage />);

    expect(await screen.findByText("Google Ads (Production Ready)")).toBeInTheDocument();
    expect(await screen.findByText("Meta Ads")).toBeInTheDocument();
    expect(await screen.findByText("Meta Ads token is available.")).toBeInTheDocument();
    expect(screen.getByText("Status raw: connected")).toBeInTheDocument();
  });

  it("keeps Meta card visible with degraded error when Meta status request fails", async () => {
    apiMock.apiRequest.mockImplementation((path: string) => {
      if (path === "/integrations/google-ads/status") {
        return Promise.resolve({ status: "connected", message: "ok", mode: "oauth", connected_accounts_count: 2 });
      }
      if (path === "/integrations/meta-ads/status") {
        return Promise.reject(new Error("Meta status unavailable"));
      }
      return Promise.resolve({});
    });

    render(<AgencyIntegrationsPage />);

    expect(await screen.findByText("Google Ads (Production Ready)")).toBeInTheDocument();
    expect(await screen.findByText("Meta Ads")).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByText("Meta status unavailable")).toBeInTheDocument();
    });
    expect(screen.getByText("Status Meta Ads indisponibil momentan.")).toBeInTheDocument();
  });
});
