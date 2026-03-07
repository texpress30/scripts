import React from "react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";

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

  it("shows Meta import button and enables it when token source is usable", async () => {
    apiMock.apiRequest.mockImplementation((path: string) => {
      if (path === "/integrations/google-ads/status") {
        return Promise.resolve({ status: "connected", message: "ok", mode: "oauth", connected_accounts_count: 2 });
      }
      if (path === "/integrations/meta-ads/status") {
        return Promise.resolve({ provider: "meta_ads", status: "pending", message: "setup", oauth_configured: false, token_source: "env_fallback" });
      }
      return Promise.resolve({});
    });

    render(<AgencyIntegrationsPage />);

    const metaHeading = await screen.findByRole("heading", { name: "Meta Ads" });
    const metaCard = metaHeading.closest("article") as HTMLElement;
    const importButton = within(metaCard).getByRole("button", { name: "Import Accounts" });
    expect(importButton).toBeEnabled();
  });

  it("disables Meta import button when token is missing", async () => {
    apiMock.apiRequest.mockImplementation((path: string) => {
      if (path === "/integrations/google-ads/status") {
        return Promise.resolve({ status: "connected", message: "ok", mode: "oauth", connected_accounts_count: 2 });
      }
      if (path === "/integrations/meta-ads/status") {
        return Promise.resolve({ provider: "meta_ads", status: "pending", message: "missing token", oauth_configured: true, token_source: "missing" });
      }
      return Promise.resolve({});
    });

    render(<AgencyIntegrationsPage />);

    const metaHeading = await screen.findByRole("heading", { name: "Meta Ads" });
    const metaCard = metaHeading.closest("article") as HTMLElement;
    const importButton = within(metaCard).getByRole("button", { name: "Import Accounts" });
    expect(importButton).toBeDisabled();
    expect(await screen.findByText(/Importul conturilor Meta necesită un token activ/i)).toBeInTheDocument();
  });

  it("shows Meta import summary on successful import", async () => {
    let metaStatusCalls = 0;
    apiMock.apiRequest.mockImplementation((path: string, options?: { method?: string }) => {
      if (path === "/integrations/google-ads/status") {
        return Promise.resolve({ status: "connected", message: "ok", mode: "oauth", connected_accounts_count: 2 });
      }
      if (path === "/integrations/meta-ads/status") {
        metaStatusCalls += 1;
        return Promise.resolve({ provider: "meta_ads", status: "connected", message: "Meta ready", oauth_configured: true, token_source: "database" });
      }
      if (path === "/integrations/meta-ads/import-accounts") {
        expect(options).toEqual({ method: "POST" });
        return Promise.resolve({
          status: "ok",
          message: "Meta Ads accounts import completed.",
          platform: "meta_ads",
          token_source: "database",
          accounts_discovered: 12,
          imported: 3,
          updated: 2,
          unchanged: 7,
        });
      }
      return Promise.resolve({});
    });

    render(<AgencyIntegrationsPage />);

    const metaHeading = await screen.findByRole("heading", { name: "Meta Ads" });
    const metaCard = metaHeading.closest("article") as HTMLElement;
    const importButton = within(metaCard).getByRole("button", { name: "Import Accounts" });
    fireEvent.click(importButton);

    await waitFor(() => {
      expect(screen.getByText("Ultimul import Meta")).toBeInTheDocument();
      expect(screen.getByText("Meta Ads accounts import completed.")).toBeInTheDocument();
      expect(screen.getByText(/Descoperite: 12/)).toBeInTheDocument();
      expect(screen.getByText(/Imported: 3/)).toBeInTheDocument();
      expect(screen.getByText(/Updated: 2/)).toBeInTheDocument();
      expect(screen.getByText(/Unchanged: 7/)).toBeInTheDocument();
    });
    expect(metaStatusCalls).toBeGreaterThanOrEqual(2);
  });

  it("shows Meta import error when import request fails", async () => {
    apiMock.apiRequest.mockImplementation((path: string) => {
      if (path === "/integrations/google-ads/status") {
        return Promise.resolve({ status: "connected", message: "ok", mode: "oauth", connected_accounts_count: 2 });
      }
      if (path === "/integrations/meta-ads/status") {
        return Promise.resolve({ provider: "meta_ads", status: "connected", message: "Meta ready", oauth_configured: true, token_source: "database" });
      }
      if (path === "/integrations/meta-ads/import-accounts") {
        return Promise.reject(new Error("Meta import unavailable"));
      }
      return Promise.resolve({});
    });

    render(<AgencyIntegrationsPage />);

    const metaHeading = await screen.findByRole("heading", { name: "Meta Ads" });
    const metaCard = metaHeading.closest("article") as HTMLElement;
    const importButton = within(metaCard).getByRole("button", { name: "Import Accounts" });
    fireEvent.click(importButton);

    await waitFor(() => {
      expect(screen.getByText("Meta import unavailable")).toBeInTheDocument();
    });
  });

  it("keeps existing Meta connect flow working", async () => {
    apiMock.apiRequest.mockImplementation((path: string) => {
      if (path === "/integrations/google-ads/status") {
        return Promise.resolve({ status: "connected", message: "ok", mode: "oauth", connected_accounts_count: 2 });
      }
      if (path === "/integrations/meta-ads/status") {
        return Promise.resolve({ provider: "meta_ads", status: "pending", message: "setup", oauth_configured: true, token_source: "missing" });
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

    const connectButton = await screen.findByRole("button", { name: "Connect Meta Ads" });
    expect(connectButton).toBeEnabled();
    fireEvent.click(connectButton);

    await waitFor(() => {
      expect(apiMock.apiRequest).toHaveBeenCalledWith("/integrations/meta-ads/connect");
      expect(window.location.href).toBe("https://facebook.com/dialog/oauth");
    });

    window.location = originalLocation;
  });
});
