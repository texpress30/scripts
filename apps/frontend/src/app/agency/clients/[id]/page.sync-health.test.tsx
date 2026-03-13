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

  it("renders and updates client currency without account scope", async () => {
    apiMock.apiRequest.mockReset();
    apiMock.apiRequest
      .mockResolvedValueOnce({
        client: { id: 1, display_id: 1, name: "Client A", owner_email: "owner@example.com", currency: "RON" },
        platforms: [
          {
            platform: "meta_ads",
            enabled: true,
            count: 1,
            accounts: [{ id: "act_1", name: "Meta One", currency: "USD" }],
          },
        ],
      })
      .mockResolvedValueOnce({
        client: { id: 1, display_id: 1, name: "Client A", owner_email: "owner@example.com", currency: "EUR" },
        platforms: [
          {
            platform: "meta_ads",
            enabled: true,
            count: 1,
            accounts: [{ id: "act_1", name: "Meta One", currency: "USD" }],
          },
        ],
      });

    render(<AgencyClientDetailsPage />);
    await screen.findByText("Client A");

    expect(screen.getByText("RON")).toBeInTheDocument();
    fireEvent.click(screen.getByTitle("Editează moneda clientului"));
    fireEvent.change(screen.getByDisplayValue("RON"), { target: { value: "EUR" } });

    expect(apiMock.apiRequest).toHaveBeenNthCalledWith(
      2,
      "/clients/display/1",
      expect.objectContaining({
        method: "PATCH",
        body: JSON.stringify({ currency: "EUR" }),
      }),
    );
    expect(screen.getByText("EUR")).toBeInTheDocument();
  });

  it("keeps account currency edits scoped to platform/account_id", async () => {
    apiMock.apiRequest.mockReset();
    apiMock.apiRequest
      .mockResolvedValueOnce({
        client: { id: 1, display_id: 1, name: "Client A", owner_email: "owner@example.com", currency: "RON" },
        platforms: [
          {
            platform: "meta_ads",
            enabled: true,
            count: 1,
            accounts: [{ id: "act_1", name: "Meta One", currency: "USD" }],
          },
        ],
      })
      .mockResolvedValueOnce({
        client: { id: 1, display_id: 1, name: "Client A", owner_email: "owner@example.com", currency: "RON" },
        platforms: [
          {
            platform: "meta_ads",
            enabled: true,
            count: 1,
            accounts: [{ id: "act_1", name: "Meta One", currency: "EUR" }],
          },
        ],
      });

    render(<AgencyClientDetailsPage />);
    await screen.findByText("Meta One");

    fireEvent.click(screen.getByTitle("Editează moneda contului"));
    fireEvent.change(screen.getByDisplayValue("USD"), { target: { value: "EUR" } });

    expect(apiMock.apiRequest).toHaveBeenNthCalledWith(
      2,
      "/clients/display/1",
      expect.objectContaining({
        method: "PATCH",
        body: JSON.stringify({ currency: "EUR", platform: "meta_ads", account_id: "act_1" }),
      }),
    );
  });
});
