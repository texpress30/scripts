import React from "react";
import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";

import AgencyIntegrationsPage from "./page";

vi.mock("@/components/ProtectedPage", () => ({ ProtectedPage: ({ children }: { children: React.ReactNode }) => <>{children}</> }));
vi.mock("@/components/AppShell", () => ({ AppShell: ({ children }: { children: React.ReactNode }) => <>{children}</> }));
vi.mock("@/lib/api", () => ({ apiRequest: vi.fn(async () => ({ status: "pending", message: "ok", mode: "production" })) }));
vi.mock("./MetaIntegrationCard", () => ({
  MetaIntegrationCard: () => <div data-testid="meta-card">Meta Integration Card</div>,
}));
vi.mock("./TikTokIntegrationCard", () => ({
  TikTokIntegrationCard: () => <div data-testid="tiktok-card">TikTok Integration Card</div>,
}));
vi.mock("./MailgunIntegrationCard", () => ({
  MailgunIntegrationCard: () => <div data-testid="mailgun-card">Mailgun Integration Card</div>,
}));

describe("AgencyIntegrationsPage", () => {
  it("renders integrations page and includes exactly one Meta, TikTok, and Mailgun card component", async () => {
    render(<AgencyIntegrationsPage />);

    expect(screen.getByText("Google Ads (Production Ready)")).toBeInTheDocument();
    expect(screen.getAllByTestId("meta-card")).toHaveLength(1);
    expect(screen.getByText("Meta Integration Card")).toBeInTheDocument();
    expect(screen.getAllByTestId("tiktok-card")).toHaveLength(1);
    expect(screen.getByText("TikTok Integration Card")).toBeInTheDocument();
    expect(screen.getAllByTestId("mailgun-card")).toHaveLength(1);
    expect(screen.getByText("Mailgun Integration Card")).toBeInTheDocument();
  });
});
