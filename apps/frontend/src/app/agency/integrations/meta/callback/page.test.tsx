import React from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";

import MetaOAuthCallbackPage from "./page";

const apiMock = vi.hoisted(() => ({ apiRequest: vi.fn() }));
const navState = vi.hoisted(() => ({
  params: new URLSearchParams(),
  replace: vi.fn(),
}));

vi.mock("@/lib/api", () => ({ apiRequest: apiMock.apiRequest }));
vi.mock("@/components/ProtectedPage", () => ({ ProtectedPage: ({ children }: { children: React.ReactNode }) => <>{children}</> }));
vi.mock("@/components/AppShell", () => ({ AppShell: ({ children }: { children: React.ReactNode }) => <>{children}</> }));
vi.mock("next/navigation", () => ({
  useSearchParams: () => navState.params,
  useRouter: () => ({ replace: navState.replace }),
}));

describe("MetaOAuthCallbackPage", () => {
  beforeEach(() => {
    apiMock.apiRequest.mockReset();
    navState.replace.mockReset();
    navState.params = new URLSearchParams();
  });

  it("shows provider error without calling backend", async () => {
    navState.params = new URLSearchParams("error=access_denied&error_reason=user_denied&error_description=Denied");

    render(<MetaOAuthCallbackPage />);

    expect(await screen.findByText(/Meta OAuth error/i)).toBeInTheDocument();
    expect(apiMock.apiRequest).not.toHaveBeenCalled();
  });

  it("shows missing code/state error", async () => {
    navState.params = new URLSearchParams("state=only-state");

    render(<MetaOAuthCallbackPage />);

    expect(await screen.findByText(/lipsesc code\/state/i)).toBeInTheDocument();
    expect(apiMock.apiRequest).not.toHaveBeenCalled();
  });

  it("performs successful oauth exchange flow", async () => {
    navState.params = new URLSearchParams("code=abc&state=state-1");
    apiMock.apiRequest.mockResolvedValue({ status: "connected", message: "Meta connected", token_source: "database" });

    render(<MetaOAuthCallbackPage />);

    await waitFor(() => {
      expect(apiMock.apiRequest).toHaveBeenCalledWith("/integrations/meta-ads/oauth/exchange", {
        method: "POST",
        body: JSON.stringify({ code: "abc", state: "state-1" }),
      });
    });
    await waitFor(() => {
      expect(navState.replace).toHaveBeenCalledWith("/agency/integrations?meta_connected=1");
    }, { timeout: 2500 });
  });
});
