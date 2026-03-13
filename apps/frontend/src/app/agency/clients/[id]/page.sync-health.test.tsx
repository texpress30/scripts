import React from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";

import AgencyClientDetailsPage from "./page";

const apiMock = vi.hoisted(() => ({
  apiRequest: vi.fn(),
}));

vi.mock("@/lib/api", () => ({
  apiRequest: apiMock.apiRequest,
}));
vi.mock("@/components/ProtectedPage", () => ({ ProtectedPage: ({ children }: { children: React.ReactNode }) => <>{children}</> }));
vi.mock("@/components/AppShell", () => ({ AppShell: ({ children }: { children: React.ReactNode }) => <>{children}</> }));
vi.mock("next/navigation", () => ({ useParams: () => ({ id: "1" }) }));
vi.mock("next/link", () => ({
  default: ({ href, children, className }: { href: string; children: React.ReactNode; className?: string }) => (
    <a href={href} className={className}>
      {children}
    </a>
  ),
}));

describe("Agency client detail sync health UI", () => {
  beforeEach(() => {
    apiMock.apiRequest.mockReset();
    apiMock.apiRequest.mockResolvedValue({
      client: { id: 1, display_id: 1, name: "Client A", owner_email: "owner@example.com" },
      platforms: [
        {
          platform: "meta_ads",
          enabled: true,
          count: 4,
          accounts: [
            { id: "act_failed", name: "Meta Failed", coverage_status: "failed_request_coverage", last_error_summary: "all chunks failed" },
            { id: "act_partial", name: "Meta Partial", coverage_status: "partial_request_coverage", failed_chunk_count: 1 },
            { id: "act_full", name: "Meta Full", coverage_status: "full_request_coverage" },
            { id: "act_empty", name: "Meta Empty", coverage_status: "empty_success" },
          ],
        },
        {
          platform: "tiktok_ads",
          enabled: true,
          count: 2,
          accounts: [
            { id: "tt_warn", name: "TikTok Warn", last_error_summary: "token warning" },
            { id: "tt_unknown", name: "TikTok Unknown" },
          ],
        },
      ],
    });
  });

  it("renders per-account status badges and section-level warning/error counters", async () => {
    render(<AgencyClientDetailsPage />);

    await screen.findByText("Client A");

    expect(screen.getByText("1 error • 1 warning")).toBeInTheDocument();
    expect(screen.getByText("1 warning")).toBeInTheDocument();

    expect(screen.getAllByText("Error").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Warning").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Healthy").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Unknown").length).toBeGreaterThan(0);
  });

  it("shows concise detail panel on toggle", async () => {
    render(<AgencyClientDetailsPage />);

    await screen.findByText("Meta Failed");

    fireEvent.click(screen.getAllByRole("button", { name: "Details" })[0]);
    expect(screen.getByText("Coverage")).toBeInTheDocument();
  });
});
