import React from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";

import MetaOAuthCallbackPage from "./page";

const apiMock = vi.hoisted(() => ({ apiRequest: vi.fn() }));
const navMock = vi.hoisted(() => ({
  query: "",
  replace: vi.fn(),
}));

vi.mock("@/lib/api", () => ({ apiRequest: apiMock.apiRequest }));
vi.mock("@/components/ProtectedPage", () => ({ ProtectedPage: ({ children }: { children: React.ReactNode }) => <>{children}</> }));
vi.mock("@/components/AppShell", () => ({ AppShell: ({ children }: { children: React.ReactNode }) => <>{children}</> }));
vi.mock("next/navigation", () => ({
  useSearchParams: () => new URLSearchParams(navMock.query),
  useRouter: () => ({ replace: navMock.replace }),
}));

describe("MetaOAuthCallbackPage", () => {
  beforeEach(() => {
    apiMock.apiRequest.mockReset();
    navMock.replace.mockReset();
    navMock.query = "";
    vi.useRealTimers();
  });

  it("shows provider error without calling backend exchange", async () => {
    navMock.query = "error=access_denied&error_reason=user_denied&error_description=User%20cancelled";

    render(<MetaOAuthCallbackPage />);

    expect(await screen.findByText(/Meta OAuth returned an error/i)).toBeInTheDocument();
    expect(apiMock.apiRequest).not.toHaveBeenCalled();
  });

  it("shows missing code/state error", async () => {
    navMock.query = "state=only-state";

    render(<MetaOAuthCallbackPage />);

    expect(await screen.findByText("Missing code/state in Meta OAuth callback.")).toBeInTheDocument();
    expect(apiMock.apiRequest).not.toHaveBeenCalled();
  });

  it("exchanges code/state successfully and redirects to integrations", async () => {
    navMock.query = "code=oauth-code&state=oauth-state";
    apiMock.apiRequest.mockResolvedValue({ status: "connected", message: "Meta OAuth connected." });

    render(<MetaOAuthCallbackPage />);

    expect(await screen.findByText("Meta OAuth connected.")).toBeInTheDocument();
    await waitFor(() => {
      expect(apiMock.apiRequest).toHaveBeenCalledWith("/integrations/meta-ads/oauth/exchange", {
        method: "POST",
        body: JSON.stringify({ code: "oauth-code", state: "oauth-state" }),
      });
    });

    await waitFor(() => {
      expect(navMock.replace).toHaveBeenCalledWith("/agency/integrations?meta_connected=1");
    });
  });
});
