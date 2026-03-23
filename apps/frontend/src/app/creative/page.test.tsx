import React from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import CreativePage from "./page";
import { apiRequest } from "@/lib/api";

vi.mock("@/lib/api", () => ({ apiRequest: vi.fn() }));
vi.mock("@/components/ProtectedPage", () => ({ ProtectedPage: ({ children }: { children: React.ReactNode }) => <>{children}</> }));
vi.mock("@/components/AppShell", () => ({ AppShell: ({ children }: { children: React.ReactNode }) => <div>{children}</div> }));
vi.mock("@/components/CreativeMediaLibrary", () => ({
  CreativeMediaLibrary: ({ onSelectMedia }: { onSelectMedia?: (media: unknown) => void }) => (
    <div data-testid="creative-media-library-mock">
      <button
        type="button"
        onClick={() =>
          onSelectMedia?.({
            media_id: "m_selected",
            client_id: 10,
            kind: "image",
            source: "upload",
            status: "ready",
            original_filename: "picked.png",
            mime_type: "image/png",
            size_bytes: 123,
            created_at: null,
            uploaded_at: null,
          })
        }
      >
        select-media
      </button>
      <button type="button" onClick={() => onSelectMedia?.(null)}>
        clear-media
      </button>
    </div>
  ),
}));

describe("CreativePage create asset + first variant integration", () => {
  beforeEach(() => {
    vi.mocked(apiRequest).mockReset();
  });

  function setupApiSuccess() {
    let assetsListCalls = 0;
    vi.mocked(apiRequest).mockImplementation(async (path: string, options?: RequestInit) => {
      if (path === "/clients") return { items: [{ id: 10, name: "Client 10" }] };
      if (path.startsWith("/creative/library/assets?client_id=10")) {
        assetsListCalls += 1;
        return {
          items:
            assetsListCalls > 1
              ? [
                  {
                    id: 201,
                    client_id: 10,
                    name: "Asset nou",
                    metadata: { format: "image", platform_fit: ["meta"] },
                    approval_status: "draft",
                  },
                ]
              : [],
        };
      }
      if (path === "/creative/library/assets" && options?.method === "POST") {
        return { id: 201, client_id: 10, name: "Asset nou" };
      }
      if (path === "/creative/library/assets/201/variants" && options?.method === "POST") {
        return { id: 301, asset_id: 201, media_id: "m_selected", media: "picked.png" };
      }
      throw new Error(`Unexpected ${path}`);
    });
    return { getAssetsListCalls: () => assetsListCalls };
  }

  it("keeps existing asset list + library visible", async () => {
    vi.mocked(apiRequest).mockImplementation(async (path: string) => {
      if (path === "/clients") return { items: [{ id: 10, name: "Client 10" }] };
      if (path.startsWith("/creative/library/assets?client_id=10")) return { items: [] };
      throw new Error("Unexpected path");
    });

    render(<CreativePage />);

    expect(screen.getByText(/Banner campanie vara 2025/i)).toBeInTheDocument();
    expect(await screen.findByTestId("creative-media-library-mock")).toBeInTheDocument();
    expect(screen.getByTestId("creative-assets-table")).toBeInTheDocument();
  });

  it("blocks create+variant action when media is not selected", async () => {
    setupApiSuccess();
    render(<CreativePage />);

    await screen.findByRole("option", { name: "Client 10" });
    fireEvent.click(screen.getByText("clear-media"));
    fireEvent.change(screen.getByTestId("creative-create-name"), { target: { value: "Asset nou" } });
    fireEvent.click(screen.getByTestId("creative-create-with-media-button"));

    expect(await screen.findByText(/Selectează mai întâi un media item/i)).toBeInTheDocument();
  });

  it("uses selected media in real flow and sends media_id + legacy media", async () => {
    setupApiSuccess();
    render(<CreativePage />);

    fireEvent.click(await screen.findByText("select-media"));
    fireEvent.change(screen.getByTestId("creative-create-name"), { target: { value: "Asset nou" } });
    fireEvent.click(screen.getByTestId("creative-create-with-media-button"));

    await waitFor(() => {
      const variantCall = vi.mocked(apiRequest).mock.calls.find(
        (call) => call[0] === "/creative/library/assets/201/variants" && call[1]?.method === "POST",
      );
      expect(variantCall).toBeTruthy();
      const body = JSON.parse(String(variantCall?.[1]?.body ?? "{}"));
      expect(body.media_id).toBe("m_selected");
      expect(body.media).toBe("picked.png");
    });

    expect(await screen.findByText(/prima variantă au fost create/i)).toBeInTheDocument();
  });

  it("reloads assets list after successful create+variant", async () => {
    const tracker = setupApiSuccess();
    render(<CreativePage />);

    fireEvent.click(await screen.findByText("select-media"));
    fireEvent.change(screen.getByTestId("creative-create-name"), { target: { value: "Asset nou" } });
    fireEvent.click(screen.getByTestId("creative-create-with-media-button"));

    await screen.findByText(/prima variantă au fost create/i);
    expect(tracker.getAssetsListCalls()).toBeGreaterThan(1);
  });

  it("shows clear error when asset is created but add variant fails", async () => {
    vi.mocked(apiRequest).mockImplementation(async (path: string, options?: RequestInit) => {
      if (path === "/clients") return { items: [{ id: 10, name: "Client 10" }] };
      if (path.startsWith("/creative/library/assets?client_id=10")) return { items: [] };
      if (path === "/creative/library/assets" && options?.method === "POST") return { id: 444, client_id: 10, name: "Asset nou" };
      if (path === "/creative/library/assets/444/variants" && options?.method === "POST") throw new Error("media_id is not ready");
      throw new Error(`Unexpected ${path}`);
    });

    render(<CreativePage />);
    fireEvent.click(await screen.findByText("select-media"));
    fireEvent.change(screen.getByTestId("creative-create-name"), { target: { value: "Asset nou" } });
    fireEvent.click(screen.getByTestId("creative-create-with-media-button"));

    expect(await screen.findByText(/Asset #444 a fost creat, dar add variant a eșuat/i)).toBeInTheDocument();
    expect(screen.getByText(/media_id is not ready/i)).toBeInTheDocument();
  });

  it("handles backend media_id validation error without breaking UI", async () => {
    vi.mocked(apiRequest).mockImplementation(async (path: string, options?: RequestInit) => {
      if (path === "/clients") return { items: [{ id: 10, name: "Client 10" }] };
      if (path.startsWith("/creative/library/assets?client_id=10")) return { items: [] };
      if (path === "/creative/library/assets" && options?.method === "POST") return { id: 333, client_id: 10, name: "Asset nou" };
      if (path === "/creative/library/assets/333/variants" && options?.method === "POST") throw new Error("media_id client mismatch");
      throw new Error(`Unexpected ${path}`);
    });

    render(<CreativePage />);
    fireEvent.click(await screen.findByText("select-media"));
    fireEvent.change(screen.getByTestId("creative-create-name"), { target: { value: "Asset nou" } });
    fireEvent.click(screen.getByTestId("creative-create-with-media-button"));

    expect(await screen.findByText(/media_id client mismatch/i)).toBeInTheDocument();
    expect(screen.getByTestId("creative-create-first-variant-flow")).toBeInTheDocument();
    expect(screen.getByTestId("creative-media-library-mock")).toBeInTheDocument();
  });
});
