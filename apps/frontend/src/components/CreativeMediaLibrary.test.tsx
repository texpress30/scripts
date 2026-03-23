import React from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import { CreativeMediaLibrary } from "./CreativeMediaLibrary";
import { apiRequest } from "@/lib/api";
import { completeDirectUpload, getMediaAccessUrl, initDirectUpload, uploadFileToPresignedUrl } from "@/lib/storage-client";

vi.mock("@/lib/api", () => ({ apiRequest: vi.fn() }));
vi.mock("@/lib/storage-client", () => ({
  initDirectUpload: vi.fn(),
  uploadFileToPresignedUrl: vi.fn(),
  completeDirectUpload: vi.fn(),
  getMediaAccessUrl: vi.fn(),
}));

type MediaItem = {
  media_id: string;
  client_id: number;
  kind: "image" | "video" | "document";
  source: string;
  status: string;
  original_filename: string;
  mime_type: string;
  size_bytes: number | null;
  created_at: string | null;
  uploaded_at: string | null;
};

function listPayload(items: MediaItem[]) {
  return { items, limit: 50, offset: 0, total: items.length };
}

describe("CreativeMediaLibrary", () => {
  beforeEach(() => {
    vi.mocked(apiRequest).mockReset();
    vi.mocked(initDirectUpload).mockReset();
    vi.mocked(uploadFileToPresignedUrl).mockReset();
    vi.mocked(completeDirectUpload).mockReset();
    vi.mocked(getMediaAccessUrl).mockReset();
  });

  it("shows loading then media list for current client", async () => {
    let resolveList: ((value: unknown) => void) | null = null;
    vi.mocked(apiRequest).mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveList = resolve;
        }) as Promise<never>,
    );

    render(<CreativeMediaLibrary clientId={77} />);
    expect(await screen.findByText(/Se încarcă media/i)).toBeInTheDocument();

    resolveList?.(
      listPayload([
        {
          media_id: "m1",
          client_id: 77,
          kind: "image",
          source: "upload",
          status: "ready",
          original_filename: "a.png",
          mime_type: "image/png",
          size_bytes: 1024,
          created_at: "2026-03-23T10:00:00Z",
          uploaded_at: "2026-03-23T10:01:00Z",
        },
      ]),
    );

    expect(await screen.findByTestId("media-item-m1")).toBeInTheDocument();
    expect(vi.mocked(apiRequest).mock.calls[0]?.[0]).toContain("client_id=77");
  });

  it("shows empty state when no media exists", async () => {
    vi.mocked(apiRequest).mockResolvedValue(listPayload([]));
    render(<CreativeMediaLibrary clientId={88} />);
    expect(await screen.findByText(/Nu există media pentru filtrul curent/i)).toBeInTheDocument();
  });

  it("selects media item locally and highlights it", async () => {
    vi.mocked(apiRequest).mockResolvedValue(
      listPayload([
        {
          media_id: "m2",
          client_id: 77,
          kind: "image",
          source: "upload",
          status: "ready",
          original_filename: "b.png",
          mime_type: "image/png",
          size_bytes: 2048,
          created_at: "2026-03-23T10:00:00Z",
          uploaded_at: "2026-03-23T10:01:00Z",
        },
      ]),
    );
    vi.mocked(getMediaAccessUrl).mockResolvedValue({
      media_id: "m2",
      status: "ready",
      mime_type: "image/png",
      method: "GET",
      url: "https://cdn.example/b.png",
      expires_in: 900,
      disposition: "inline",
      filename: "b.png",
    });

    render(<CreativeMediaLibrary clientId={77} />);
    const item = await screen.findByTestId("media-item-m2");
    fireEvent.click(item);
    await waitFor(() => {
      expect(item).toHaveAttribute("aria-pressed", "true");
      expect(screen.getByText(/Media ID pentru pasul următor: m2/i)).toBeInTheDocument();
    });
  });

  it("renders image preview when access URL exists", async () => {
    vi.mocked(apiRequest).mockResolvedValue(
      listPayload([
        {
          media_id: "img1",
          client_id: 77,
          kind: "image",
          source: "upload",
          status: "ready",
          original_filename: "preview.png",
          mime_type: "image/png",
          size_bytes: 1024,
          created_at: null,
          uploaded_at: null,
        },
      ]),
    );
    vi.mocked(getMediaAccessUrl).mockResolvedValue({
      media_id: "img1",
      status: "ready",
      mime_type: "image/png",
      method: "GET",
      url: "https://cdn.example/preview.png",
      expires_in: 900,
      disposition: "inline",
      filename: "preview.png",
    });

    render(<CreativeMediaLibrary clientId={77} />);
    fireEvent.click(await screen.findByTestId("media-item-img1"));
    expect(await screen.findByTestId("creative-media-preview-image")).toHaveAttribute("src", "https://cdn.example/preview.png");
  });

  it("renders video preview when access URL exists", async () => {
    vi.mocked(apiRequest).mockResolvedValue(
      listPayload([
        {
          media_id: "vid1",
          client_id: 77,
          kind: "video",
          source: "upload",
          status: "ready",
          original_filename: "preview.mp4",
          mime_type: "video/mp4",
          size_bytes: 999,
          created_at: null,
          uploaded_at: null,
        },
      ]),
    );
    vi.mocked(getMediaAccessUrl).mockResolvedValue({
      media_id: "vid1",
      status: "ready",
      mime_type: "video/mp4",
      method: "GET",
      url: "https://cdn.example/preview.mp4",
      expires_in: 900,
      disposition: "inline",
      filename: "preview.mp4",
    });

    render(<CreativeMediaLibrary clientId={77} />);
    fireEvent.click(await screen.findByTestId("media-item-vid1"));
    expect(await screen.findByTestId("creative-media-preview-video")).toHaveAttribute("src", "https://cdn.example/preview.mp4");
  });

  it("shows preview fallback when access-url fails", async () => {
    vi.mocked(apiRequest).mockResolvedValue(
      listPayload([
        {
          media_id: "img2",
          client_id: 77,
          kind: "image",
          source: "upload",
          status: "ready",
          original_filename: "broken.png",
          mime_type: "image/png",
          size_bytes: 111,
          created_at: null,
          uploaded_at: null,
        },
      ]),
    );
    vi.mocked(getMediaAccessUrl).mockRejectedValue(new Error("preview failed"));

    render(<CreativeMediaLibrary clientId={77} />);
    fireEvent.click(await screen.findByTestId("media-item-img2"));
    expect(await screen.findByText(/preview failed/i)).toBeInTheDocument();
  });

  it("runs upload flow init -> upload -> complete then refreshes list and auto-selects new media", async () => {
    vi.mocked(apiRequest)
      .mockResolvedValueOnce(listPayload([]))
      .mockResolvedValueOnce(
        listPayload([
          {
            media_id: "m_new",
            client_id: 77,
            kind: "image",
            source: "upload",
            status: "ready",
            original_filename: "new.png",
            mime_type: "image/png",
            size_bytes: 123,
            created_at: null,
            uploaded_at: null,
          },
        ]),
      );
    vi.mocked(initDirectUpload).mockResolvedValue({
      media_id: "m_new",
      status: "draft",
      bucket: "assets",
      key: "k",
      region: "eu",
      upload: { method: "PUT", url: "https://upload.local", expires_in: 900, headers: { "Content-Type": "image/png" } },
    });
    vi.mocked(uploadFileToPresignedUrl).mockResolvedValue();
    vi.mocked(completeDirectUpload).mockResolvedValue({
      media_id: "m_new",
      status: "ready",
      bucket: "assets",
      key: "k",
      region: "eu",
      mime_type: "image/png",
    });
    vi.mocked(getMediaAccessUrl).mockResolvedValue({
      media_id: "m_new",
      status: "ready",
      mime_type: "image/png",
      method: "GET",
      url: "https://cdn.example/new.png",
      expires_in: 900,
      disposition: "inline",
      filename: "new.png",
    });

    render(<CreativeMediaLibrary clientId={77} />);
    const input = screen.getByTestId("creative-media-upload-input") as HTMLInputElement;
    const file = new File(["content"], "new.png", { type: "image/png" });
    fireEvent.change(input, { target: { files: [file] } });

    await waitFor(() => {
      expect(initDirectUpload).toHaveBeenCalled();
      expect(uploadFileToPresignedUrl).toHaveBeenCalled();
      expect(completeDirectUpload).toHaveBeenCalledWith({ clientId: 77, mediaId: "m_new" });
    });

    expect(await screen.findByText(/Media ID pentru pasul următor: m_new/i)).toBeInTheDocument();
  });

  it("shows clear error for invalid file type", async () => {
    vi.mocked(apiRequest).mockResolvedValue(listPayload([]));
    render(<CreativeMediaLibrary clientId={77} />);

    const input = screen.getByTestId("creative-media-upload-input") as HTMLInputElement;
    const file = new File(["bad"], "bad.txt", { type: "text/plain" });
    fireEvent.change(input, { target: { files: [file] } });

    expect(await screen.findByText(/Acceptăm doar imagini sau video/i)).toBeInTheDocument();
  });

  it("shows upload error when storage flow fails", async () => {
    vi.mocked(apiRequest).mockResolvedValue(listPayload([]));
    vi.mocked(initDirectUpload).mockRejectedValue(new Error("init failed"));

    render(<CreativeMediaLibrary clientId={77} />);

    const input = screen.getByTestId("creative-media-upload-input") as HTMLInputElement;
    const file = new File(["img"], "x.png", { type: "image/png" });
    fireEvent.change(input, { target: { files: [file] } });

    expect(await screen.findByText(/init failed/i)).toBeInTheDocument();
  });
});
