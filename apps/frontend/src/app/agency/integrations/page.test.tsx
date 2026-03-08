import React from "react";
import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";

import AgencyIntegrationsPage from "./page";

vi.mock("@/components/ProtectedPage", () => ({ ProtectedPage: ({ children }: { children: React.ReactNode }) => <>{children}</> }));
vi.mock("@/components/AppShell", () => ({ AppShell: ({ children }: { children: React.ReactNode }) => <>{children}</> }));
vi.mock("@/lib/api", () => ({ apiRequest: vi.fn(async () => ({ status: "pending", message: "ok", mode: "production" })) }));
vi.mock("./TikTokIntegrationCard", () => ({
  TikTokIntegrationCard: () => <div data-testid="tiktok-card">TikTok Integration Card</div>,
}));

describe("AgencyIntegrationsPage", () => {
  it("renders integrations page and includes TikTok integration card component", async () => {
    render(<AgencyIntegrationsPage />);

    expect(screen.getByText("Google Ads (Production Ready)")).toBeInTheDocument();
    expect(screen.getByTestId("tiktok-card")).toBeInTheDocument();
    expect(screen.getByText("TikTok Integration Card")).toBeInTheDocument();
  });
});
