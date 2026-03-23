import React from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import CreativePage from "./page";
import { apiRequest } from "@/lib/api";
import { getMediaAccessUrl } from "@/lib/storage-client";

vi.mock("@/lib/api", () => ({ apiRequest: vi.fn() }));
vi.mock("@/lib/storage-client", () => ({ getMediaAccessUrl: vi.fn() }));
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

function listPayloadWithVariants() {
  return {
    items: [
      {
        id: 201,
        client_id: 10,
        name: "Asset nou",
        metadata: { format: "image", platform_fit: ["meta"], approval_status: "draft" },
        creative_variants: [
          { id: 901, headline: "Image variant", body: "Body", cta: "CTA", media: "image.png", media_id: "m_img", approval_status: "approved" },
          { id: 902, headline: "Video variant", body: "Body", cta: "CTA", media: "clip.mp4", media_id: "m_vid", approval_status: "in_review" },
          { id: 903, headline: "Legacy only", body: "Body", cta: "CTA", media: "legacy-only", media_id: null },
        ],
      },
    ],
  };
}

describe("CreativePage asset detail + existing asset add variant", () => {
  beforeEach(() => {
    vi.mocked(apiRequest).mockReset();
    vi.mocked(getMediaAccessUrl).mockReset();
  });

  function setupBaseApi() {
    let listCalls = 0;
    vi.mocked(apiRequest).mockImplementation(async (path: string, options?: RequestInit) => {
      if (path === "/clients") return { items: [{ id: 10, name: "Client 10" }] };
      if (path.startsWith("/creative/library/assets?client_id=10")) {
        listCalls += 1;
        return listPayloadWithVariants();
      }
      if (path === "/creative/library/assets/201/variants" && options?.method === "POST") {
        return { id: 999, asset_id: 201, media_id: "m_selected", media: "picked.png" };
      }
      throw new Error(`Unexpected ${path}`);
    });
    return { getListCalls: () => listCalls };
  }

  it("selecting an asset loads detail and variants list", async () => {
    setupBaseApi();
    render(<CreativePage />);

    fireEvent.click(await screen.findByTestId("select-asset-201"));
    expect(await screen.findByText(/Asset selectat:/i)).toBeInTheDocument();
    expect(screen.getByTestId("asset-variants-list")).toBeInTheDocument();
    expect(screen.getByTestId("asset-variant-901")).toBeInTheDocument();
    expect(screen.getByText(/Approval: approved/i)).toBeInTheDocument();
  });

  it("renders image preview for variant with media_id", async () => {
    setupBaseApi();
    vi.mocked(getMediaAccessUrl).mockResolvedValue({
      media_id: "m_img",
      status: "ready",
      mime_type: "image/png",
      method: "GET",
      url: "https://cdn.example/preview.png",
      expires_in: 900,
      disposition: "inline",
      filename: "preview.png",
    });

    render(<CreativePage />);
    fireEvent.click(await screen.findByTestId("asset-variant-901"));

    expect(await screen.findByTestId("variant-preview-image")).toHaveAttribute("src", "https://cdn.example/preview.png");
  });

  it("renders video preview for variant with media_id", async () => {
    setupBaseApi();
    vi.mocked(getMediaAccessUrl).mockResolvedValue({
      media_id: "m_vid",
      status: "ready",
      mime_type: "video/mp4",
      method: "GET",
      url: "https://cdn.example/preview.mp4",
      expires_in: 900,
      disposition: "inline",
      filename: "preview.mp4",
    });

    render(<CreativePage />);
    fireEvent.click(await screen.findByTestId("asset-variant-902"));

    expect(await screen.findByTestId("variant-preview-video")).toHaveAttribute("src", "https://cdn.example/preview.mp4");
  });

  it("shows fallback for variant without media_id without crashing", async () => {
    setupBaseApi();
    render(<CreativePage />);

    fireEvent.click(await screen.findByTestId("asset-variant-903"));
    expect(await screen.findByText(/Varianta are doar media legacy/i)).toBeInTheDocument();
  });

  it("blocks add variant action when no asset is selected", async () => {
    vi.mocked(apiRequest).mockImplementation(async (path: string) => {
      if (path === "/clients") return { items: [{ id: 10, name: "Client 10" }] };
      if (path.startsWith("/creative/library/assets?client_id=10")) return { items: [] };
      throw new Error(`Unexpected ${path}`);
    });

    render(<CreativePage />);

    const button = await screen.findByTestId("add-variant-button");
    expect(button).toBeDisabled();
  });

  it("blocks add variant action when no media is selected", async () => {
    setupBaseApi();
    render(<CreativePage />);

    fireEvent.click(await screen.findByTestId("select-asset-201"));
    fireEvent.click(screen.getByText("clear-media"));

    expect(screen.getByTestId("add-variant-button")).toBeDisabled();
  });

  it("sends media_id and media legacy when adding variant on selected asset", async () => {
    setupBaseApi();
    render(<CreativePage />);

    fireEvent.click(await screen.findByTestId("select-asset-201"));
    fireEvent.click(screen.getByText("select-media"));
    fireEvent.click(screen.getByTestId("add-variant-button"));

    await waitFor(() => {
      const call = vi.mocked(apiRequest).mock.calls.find((entry) => entry[0] === "/creative/library/assets/201/variants" && entry[1]?.method === "POST");
      expect(call).toBeTruthy();
      const body = JSON.parse(String(call?.[1]?.body ?? "{}"));
      expect(body.media_id).toBe("m_selected");
      expect(body.media).toBe("picked.png");
    });
  });

  it("reloads selected asset detail after successful add variant and keeps context stable", async () => {
    const tracker = setupBaseApi();
    render(<CreativePage />);

    fireEvent.click(await screen.findByTestId("select-asset-201"));
    fireEvent.click(screen.getByText("select-media"));
    fireEvent.click(screen.getByTestId("add-variant-button"));

    expect(await screen.findByText(/Varianta #999 a fost adăugată/i)).toBeInTheDocument();
    expect(tracker.getListCalls()).toBeGreaterThan(1);
    expect(screen.getByText(/Asset selectat:/i)).toBeInTheDocument();
  });

  it("keeps UI stable when backend add-variant fails", async () => {
    vi.mocked(apiRequest).mockImplementation(async (path: string, options?: RequestInit) => {
      if (path === "/clients") return { items: [{ id: 10, name: "Client 10" }] };
      if (path.startsWith("/creative/library/assets?client_id=10")) return listPayloadWithVariants();
      if (path === "/creative/library/assets/201/variants" && options?.method === "POST") throw new Error("media_id client mismatch");
      throw new Error(`Unexpected ${path}`);
    });

    render(<CreativePage />);
    fireEvent.click(await screen.findByTestId("select-asset-201"));
    fireEvent.click(screen.getByText("select-media"));
    fireEvent.click(screen.getByTestId("add-variant-button"));

    expect(await screen.findByText(/media_id client mismatch/i)).toBeInTheDocument();
    expect(screen.getByTestId("creative-asset-detail")).toBeInTheDocument();
    expect(screen.getByTestId("creative-media-library-mock")).toBeInTheDocument();
  });
});
