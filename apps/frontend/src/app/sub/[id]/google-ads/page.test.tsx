import React from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import SubGoogleAdsPage from "./page";

const apiMock = vi.hoisted(() => ({ apiRequest: vi.fn() }));

vi.mock("@/lib/api", () => ({ apiRequest: apiMock.apiRequest }));
vi.mock("next/navigation", () => ({ useParams: () => ({ id: "96" }) }));
vi.mock("@/components/ProtectedPage", () => ({ ProtectedPage: ({ children }: { children: React.ReactNode }) => <>{children}</> }));
vi.mock("@/components/AppShell", () => ({
  AppShell: ({ children, title }: { children: React.ReactNode; title: React.ReactNode }) => (
    <div>
      <div data-testid="app-shell-title">{title === null ? "" : String(title ?? "")}</div>
      {children}
    </div>
  ),
}));

describe("Sub Google Ads details table", () => {
  beforeEach(() => {
    apiMock.apiRequest.mockReset();
    window.localStorage.clear();

    apiMock.apiRequest.mockImplementation((path: string) => {
      if (path === "/clients") return Promise.resolve({ items: [{ id: 96, display_id: 1096, name: "Active Life Therapy" }] });
      if (path === "/clients/display/1096") {
        return Promise.resolve({
          client: { id: 96, display_id: 1096, name: "Active Life Therapy" },
          platforms: [
            {
              platform: "google_ads",
              enabled: true,
              accounts: [
                { id: "123-111-0001", name: "Google Main RO" },
                { id: "123-111-0002", name: "Google Prospecting RO" },
              ],
            },
          ],
        });
      }
      return Promise.reject(new Error(`Unexpected path: ${path}`));
    });
  });

  it("renders Google Ads performance table instead of Coming Soon", async () => {
    render(<SubGoogleAdsPage />);

    expect(screen.queryByText("Coming Soon")).not.toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "Google Ads - Active Life Therapy" })).toBeInTheDocument();
    expect(screen.getByText("Cost")).toBeInTheDocument();
    expect(screen.getByText("Rev (∞d)")).toBeInTheDocument();
    expect(screen.getByText("ROAS (∞d)")).toBeInTheDocument();
    expect(screen.getByText("Google Main RO")).toBeInTheDocument();
  });

  it("supports dynamic columns selector with persistence", async () => {
    render(<SubGoogleAdsPage />);
    await screen.findByText("Google Main RO");

    fireEvent.click(screen.getByRole("button", { name: /Columns/i }));
    fireEvent.click(screen.getByLabelText("Visits"));
    fireEvent.click(screen.getByRole("button", { name: /Columns/i }));

    await waitFor(() => expect(screen.queryByRole("columnheader", { name: /^Visits$/i })).not.toBeInTheDocument());

    const stored = window.localStorage.getItem("sub-google-ads-visible-columns-v1");
    expect(stored).toBeTruthy();
    const storedColumns = JSON.parse(String(stored)) as string[];
    expect(storedColumns.includes("visits")).toBe(false);
  });
});
