import React from "react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import { MetaIntegrationCard } from "./MetaIntegrationCard";

const apiMock = vi.hoisted(() => ({
  apiRequest: vi.fn(),
}));

vi.mock("@/lib/api", () => ({
  apiRequest: apiMock.apiRequest,
}));

describe("MetaIntegrationCard", () => {
  beforeEach(() => {
    apiMock.apiRequest.mockReset();
  });

  it("loads and renders Meta status", async () => {
    apiMock.apiRequest.mockImplementation((path: string) => {
      if (path === "/integrations/meta-ads/status") {
        return Promise.resolve({ provider: "meta_ads", status: "connected", message: "Meta ready", oauth_configured: true, token_source: "database" });
      }
      return Promise.resolve({});
    });

    render(<MetaIntegrationCard />);

    expect(await screen.findByText("Meta ready")).toBeInTheDocument();
    expect(screen.getByText(/Sursă token: database/i)).toBeInTheDocument();
  });

  it("keeps Connect Meta flow working", async () => {
    apiMock.apiRequest.mockImplementation((path: string) => {
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

    render(<MetaIntegrationCard />);

    const connectButton = await screen.findByRole("button", { name: "Connect Meta Ads" });
    fireEvent.click(connectButton);

    await waitFor(() => {
      expect(apiMock.apiRequest).toHaveBeenCalledWith("/integrations/meta-ads/connect");
      expect(window.location.href).toBe("https://facebook.com/dialog/oauth");
    });

    window.location = originalLocation;
  });

  it("supports Import Accounts and displays success summary", async () => {
    let statusCalls = 0;
    apiMock.apiRequest.mockImplementation((path: string, options?: { method?: string }) => {
      if (path === "/integrations/meta-ads/status") {
        statusCalls += 1;
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

    render(<MetaIntegrationCard />);

    fireEvent.click(await screen.findByRole("button", { name: "Import Accounts" }));

    await waitFor(() => {
      expect(screen.getByText("Ultimul import Meta")).toBeInTheDocument();
      expect(screen.getByText("Meta Ads accounts import completed.")).toBeInTheDocument();
      expect(screen.getByText(/Descoperite: 12/)).toBeInTheDocument();
      expect(screen.getByText(/Imported: 3/)).toBeInTheDocument();
      expect(screen.getByText(/Updated: 2/)).toBeInTheDocument();
      expect(screen.getByText(/Unchanged: 7/)).toBeInTheDocument();
    });
    expect(statusCalls).toBeGreaterThanOrEqual(2);
  });

  it("shows error state when status load fails", async () => {
    apiMock.apiRequest.mockImplementation((path: string) => {
      if (path === "/integrations/meta-ads/status") {
        return Promise.reject(new Error("Meta status unavailable"));
      }
      return Promise.resolve({});
    });

    render(<MetaIntegrationCard />);

    expect(await screen.findByText("Meta status unavailable")).toBeInTheDocument();
  });

  it("shows error state when import fails", async () => {
    apiMock.apiRequest.mockImplementation((path: string) => {
      if (path === "/integrations/meta-ads/status") {
        return Promise.resolve({ provider: "meta_ads", status: "connected", message: "Meta ready", oauth_configured: true, token_source: "database" });
      }
      if (path === "/integrations/meta-ads/import-accounts") {
        return Promise.reject(new Error("Meta import unavailable"));
      }
      return Promise.resolve({});
    });

    render(<MetaIntegrationCard />);

    fireEvent.click(await screen.findByRole("button", { name: "Import Accounts" }));
    await waitFor(() => {
      expect(screen.getByText("Meta import unavailable")).toBeInTheDocument();
    });
  });
});
