import React from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import { MetaIntegrationCard } from "./MetaIntegrationCard";

const apiMock = vi.hoisted(() => ({ apiRequest: vi.fn() }));

vi.mock("@/lib/api", () => ({ apiRequest: apiMock.apiRequest }));

describe("MetaIntegrationCard", () => {
  beforeEach(() => {
    apiMock.apiRequest.mockReset();
  });

  it("loads status on mount and shows connect/import actions", async () => {
    apiMock.apiRequest.mockResolvedValueOnce({
      provider: "meta_ads",
      status: "connected",
      message: "Meta OAuth token is available.",
      token_source: "database",
      token_updated_at: "2026-03-08T10:00:00Z",
      oauth_configured: true,
      has_usable_token: true,
    });

    render(<MetaIntegrationCard />);

    expect(await screen.findByText("Meta OAuth token is available.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Connect Meta" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Import Accounts" })).toBeInTheDocument();
  });

  it("starts connect flow and redirects to authorize_url", async () => {
    apiMock.apiRequest
      .mockResolvedValueOnce({ status: "pending", oauth_configured: true, has_usable_token: false })
      .mockResolvedValueOnce({ authorize_url: "https://meta.example/auth", state: "abc" });

    render(<MetaIntegrationCard />);
    await screen.findByText(/Finalizează connect OAuth/i);

    fireEvent.click(screen.getByRole("button", { name: "Connect Meta" }));

    await waitFor(() => {
      expect(apiMock.apiRequest).toHaveBeenCalledWith("/integrations/meta-ads/connect");
    });
  });

  it("imports accounts and renders success summary", async () => {
    apiMock.apiRequest
      .mockResolvedValueOnce({ status: "connected", oauth_configured: true, has_usable_token: true, message: "ready" })
      .mockResolvedValueOnce({
        status: "ok",
        message: "Meta advertiser accounts imported into platform registry.",
        provider: "meta_ads",
        token_source: "database",
        accounts_discovered: 3,
        imported: 2,
        updated: 1,
        unchanged: 0,
      })
      .mockResolvedValueOnce({ status: "connected", oauth_configured: true, has_usable_token: true, message: "ready" });

    render(<MetaIntegrationCard />);
    await screen.findByText("ready");

    fireEvent.click(screen.getByRole("button", { name: "Import Accounts" }));

    expect(await screen.findByText("Import summary")).toBeInTheDocument();
    expect(screen.getByText("accounts_discovered: 3")).toBeInTheDocument();
    expect(screen.getByText("imported: 2")).toBeInTheDocument();
    expect(screen.getByText("updated: 1")).toBeInTheDocument();
    expect(screen.getByText("unchanged: 0")).toBeInTheDocument();
  });
});
