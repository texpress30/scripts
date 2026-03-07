import React from "react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

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

  it("shows Meta connect button enabled when oauth_configured is true", async () => {
    apiMock.apiRequest.mockImplementation((path: string) => {
      if (path === "/integrations/google-ads/status") {
        return Promise.resolve({ status: "connected", message: "ok", mode: "oauth", connected_accounts_count: 2 });
      }
      if (path === "/integrations/meta-ads/status") {
        return Promise.resolve({ provider: "meta_ads", status: "pending", message: "setup", oauth_configured: true });
      }
      if (path === "/integrations/meta-ads/connect") {
        return Promise.resolve({ authorize_url: "https://facebook.com/dialog/oauth", state: "meta-state" });
      }
      return Promise.resolve({});
    });

    const originalLocation = window.location;
    // @ts-expect-error test override
    delete window.location;
    // @ts-expect-error test override
    window.location = { href: "http://localhost/agency/integrations" };

    render(<AgencyIntegrationsPage />);

    const button = await screen.findByRole("button", { name: "Connect Meta Ads" });
    expect(button).toBeEnabled();

    fireEvent.click(button);

    await waitFor(() => {
      expect(apiMock.apiRequest).toHaveBeenCalledWith("/integrations/meta-ads/connect");
      expect(window.location.href).toBe("https://facebook.com/dialog/oauth");
    });

    window.location = originalLocation;
  });

  it("disables Meta connect button when oauth_configured is false", async () => {
    apiMock.apiRequest.mockImplementation((path: string) => {
      if (path === "/integrations/google-ads/status") {
        return Promise.resolve({ status: "connected", message: "ok", mode: "oauth", connected_accounts_count: 2 });
      }
      if (path === "/integrations/meta-ads/status") {
        return Promise.resolve({ provider: "meta_ads", status: "pending", message: "missing config", oauth_configured: false });
      }
      return Promise.resolve({});
    });

    render(<AgencyIntegrationsPage />);

    const button = await screen.findByRole("button", { name: "Connect Meta Ads" });
    expect(button).toBeDisabled();
    expect(await screen.findByText(/Meta OAuth nu este configurat complet/i)).toBeInTheDocument();
  });

  it("shows Meta connect error when connect request fails", async () => {
    apiMock.apiRequest.mockImplementation((path: string) => {
      if (path === "/integrations/google-ads/status") {
        return Promise.resolve({ status: "connected", message: "ok", mode: "oauth", connected_accounts_count: 2 });
      }
      if (path === "/integrations/meta-ads/status") {
        return Promise.resolve({ provider: "meta_ads", status: "pending", message: "setup", oauth_configured: true });
      }
      if (path === "/integrations/meta-ads/connect") {
        return Promise.reject(new Error("Meta connect unavailable"));
      }
      return Promise.resolve({});
    });

    render(<AgencyIntegrationsPage />);

    const button = await screen.findByRole("button", { name: "Connect Meta Ads" });
    fireEvent.click(button);

    await waitFor(() => {
      expect(screen.getByText("Meta connect unavailable")).toBeInTheDocument();
    });
  });
});
