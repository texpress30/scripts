import React from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import { TikTokIntegrationCard } from "./TikTokIntegrationCard";

const apiMock = vi.hoisted(() => ({ apiRequest: vi.fn() }));

vi.mock("@/lib/api", () => ({ apiRequest: apiMock.apiRequest }));
vi.mock("next/navigation", () => ({
  useSearchParams: () => new URLSearchParams(""),
}));

describe("TikTokIntegrationCard", () => {
  beforeEach(() => {
    apiMock.apiRequest.mockReset();
  });

  it("loads status on mount", async () => {
    apiMock.apiRequest.mockResolvedValueOnce({
      provider: "tiktok_ads",
      status: "connected",
      message: "TikTok OAuth token is available.",
      token_source: "database",
      token_updated_at: "2026-03-08T10:00:00Z",
      token_expires_at: "2026-03-09T10:00:00Z",
      oauth_configured: true,
      has_usable_token: true,
    });

    render(<TikTokIntegrationCard />);

    expect(await screen.findByText("TikTok OAuth token is available.")).toBeInTheDocument();
    expect(screen.getByText("Token source: database")).toBeInTheDocument();
  });

  it("starts connect flow and redirects to authorize_url", async () => {
    apiMock.apiRequest
      .mockResolvedValueOnce({ status: "pending", oauth_configured: true, has_usable_token: false })
      .mockResolvedValueOnce({ authorize_url: "https://tiktok.example/auth", state: "abc" });

    render(<TikTokIntegrationCard />);
    await screen.findByText(/Finalizează connect OAuth/i);

    fireEvent.click(screen.getByRole("button", { name: "Connect TikTok" }));

    await waitFor(() => {
      expect(apiMock.apiRequest).toHaveBeenCalledWith("/integrations/tiktok-ads/connect");
    });
  });

  it("imports accounts and renders success summary", async () => {
    apiMock.apiRequest
      .mockResolvedValueOnce({ status: "connected", oauth_configured: true, has_usable_token: true, message: "ready" })
      .mockResolvedValueOnce({
        status: "ok",
        message: "TikTok advertiser accounts imported into platform registry.",
        platform: "tiktok_ads",
        token_source: "database",
        accounts_discovered: 3,
        imported: 2,
        updated: 1,
        unchanged: 0,
      })
      .mockResolvedValueOnce({ status: "connected", oauth_configured: true, has_usable_token: true, message: "ready" });

    render(<TikTokIntegrationCard />);
    await screen.findByText("ready");

    fireEvent.click(screen.getByRole("button", { name: "Import Accounts" }));

    expect(await screen.findByText("Import summary")).toBeInTheDocument();
    expect(screen.getByText("accounts_discovered: 3")).toBeInTheDocument();
    expect(screen.getByText("imported: 2")).toBeInTheDocument();
    expect(screen.getByText("updated: 1")).toBeInTheDocument();
    expect(screen.getByText("unchanged: 0")).toBeInTheDocument();
  });

  it("shows error state when import fails", async () => {
    apiMock.apiRequest
      .mockResolvedValueOnce({ status: "connected", oauth_configured: true, has_usable_token: true, message: "ready" })
      .mockRejectedValueOnce(new Error("TikTok import failed"));

    render(<TikTokIntegrationCard />);
    await screen.findByText("ready");

    fireEvent.click(screen.getByRole("button", { name: "Import Accounts" }));

    expect(await screen.findByText("TikTok import failed")).toBeInTheDocument();
  });
});
