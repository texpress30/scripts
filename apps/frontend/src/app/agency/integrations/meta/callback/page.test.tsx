import React from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";

import MetaOAuthCallbackPage from "./page";

const apiMock = vi.hoisted(() => ({
  apiRequest: vi.fn(),
}));

const navigationMock = vi.hoisted(() => ({
  searchParams: new URLSearchParams(),
  replace: vi.fn(),
}));

vi.mock("@/lib/api", () => ({
  apiRequest: apiMock.apiRequest,
}));

vi.mock("@/components/ProtectedPage", () => ({ ProtectedPage: ({ children }: { children: React.ReactNode }) => <>{children}</> }));
vi.mock("@/components/AppShell", () => ({ AppShell: ({ children }: { children: React.ReactNode }) => <>{children}</> }));
vi.mock("next/link", () => ({
  default: ({ href, children, className }: { href: string; children: React.ReactNode; className?: string }) => (
    <a href={href} className={className}>
      {children}
    </a>
  ),
}));
vi.mock("next/navigation", () => ({
  useSearchParams: () => navigationMock.searchParams,
  useRouter: () => ({ replace: navigationMock.replace }),
}));

describe("MetaOAuthCallbackPage", () => {
  beforeEach(() => {
    apiMock.apiRequest.mockReset();
    navigationMock.replace.mockReset();
    navigationMock.searchParams = new URLSearchParams();
  });

  it("shows success state after oauth exchange", async () => {
    navigationMock.searchParams = new URLSearchParams("code=abc123&state=st123");
    apiMock.apiRequest.mockResolvedValue({
      status: "connected",
      message: "Meta OAuth connected.",
      token_source: "database",
      token_updated_at: "2026-03-07T09:00:00+00:00",
      token_expires_at: "2026-05-07T09:00:00+00:00",
    });

    render(<MetaOAuthCallbackPage />);

    expect(await screen.findByText("Meta Ads conectat cu succes")).toBeInTheDocument();
    expect(screen.getByText("Meta OAuth connected.")).toBeInTheDocument();
    expect(apiMock.apiRequest).toHaveBeenCalledWith("/integrations/meta-ads/oauth/exchange", {
      method: "POST",
      body: JSON.stringify({ code: "abc123", state: "st123" }),
    });

    await waitFor(() => {
      expect(screen.getByRole("link", { name: "Înapoi la Integrations" })).toHaveAttribute("href", "/agency/integrations");
    });
  });

  it("shows provider error from query params without calling backend", async () => {
    navigationMock.searchParams = new URLSearchParams("error=access_denied&error_reason=user_denied&error_description=User%20denied");

    render(<MetaOAuthCallbackPage />);

    expect(await screen.findByText(/Meta OAuth error:/)).toBeInTheDocument();
    expect(apiMock.apiRequest).not.toHaveBeenCalled();
  });

  it("shows clear error when code/state are missing", async () => {
    navigationMock.searchParams = new URLSearchParams("");

    render(<MetaOAuthCallbackPage />);

    expect(await screen.findByText("Meta OAuth callback invalid: lipsesc parametrii code/state.")).toBeInTheDocument();
    expect(apiMock.apiRequest).not.toHaveBeenCalled();
  });
});
