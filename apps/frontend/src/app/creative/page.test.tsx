import React from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";

import CreativePage from "./page";
import { apiRequest } from "@/lib/api";

vi.mock("@/lib/api", () => ({ apiRequest: vi.fn() }));
vi.mock("@/components/ProtectedPage", () => ({ ProtectedPage: ({ children }: { children: React.ReactNode }) => <>{children}</> }));
vi.mock("@/components/AppShell", () => ({ AppShell: ({ children }: { children: React.ReactNode }) => <div>{children}</div> }));
vi.mock("@/components/CreativeMediaLibrary", () => ({
  CreativeMediaLibrary: ({ clientId, onSelectMedia }: { clientId: number | null; onSelectMedia?: (media: { media_id: string } | null) => void }) => {
    React.useEffect(() => {
      onSelectMedia?.(clientId ? { media_id: `mock-${clientId}` } : null);
    }, [clientId, onSelectMedia]);
    return <div data-testid="creative-media-library-mock">library for {clientId ?? "none"}</div>;
  },
}));

describe("CreativePage", () => {
  beforeEach(() => {
    vi.mocked(apiRequest).mockReset();
  });

  it("keeps existing asset list visible while adding media library foundation", async () => {
    vi.mocked(apiRequest).mockResolvedValue({ items: [{ id: 10, name: "Client 10" }] });

    render(<CreativePage />);

    expect(screen.getByText(/Banner campanie vara 2025/i)).toBeInTheDocument();
    expect(screen.getByText(/Video promo produs nou/i)).toBeInTheDocument();
    expect(await screen.findByTestId("creative-media-library-mock")).toBeInTheDocument();
    expect(screen.getByTestId("creative-selected-media-hint")).toBeInTheDocument();
  });

  it("renders graceful fallback when clients list for media library cannot be loaded", async () => {
    vi.mocked(apiRequest).mockRejectedValue(new Error("boom"));

    render(<CreativePage />);

    await waitFor(() => {
      expect(screen.getByTestId("creative-media-client-select")).toBeInTheDocument();
      expect(screen.getByRole("option", { name: "Niciun client" })).toBeInTheDocument();
    });
    expect(screen.getByTestId("creative-selected-media-hint")).toHaveTextContent("Nu ai selectat încă media");
  });
});
