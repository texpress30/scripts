import React from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import SubAccountSettingsPage from "./page";
import { apiRequest } from "@/lib/api";
import { completeDirectUpload, getMediaAccessUrl, initDirectUpload, uploadFileToPresignedUrl } from "@/lib/storage-client";

vi.mock("next/navigation", () => ({ useParams: () => ({ id: "96" }) }));
vi.mock("@/lib/api", () => ({ apiRequest: vi.fn() }));
vi.mock("@/lib/storage-client", () => ({
  initDirectUpload: vi.fn(),
  uploadFileToPresignedUrl: vi.fn(),
  completeDirectUpload: vi.fn(),
  getMediaAccessUrl: vi.fn(),
}));
vi.mock("@/components/ProtectedPage", () => ({ ProtectedPage: ({ children }: { children: React.ReactNode }) => <>{children}</> }));
vi.mock("@/components/AppShell", () => ({
  AppShell: ({ children, title }: { children: React.ReactNode; title: React.ReactNode }) => (
    <div>
      <div data-testid="app-shell-title">{String(title ?? "")}</div>
      {children}
    </div>
  ),
}));

type Store = {
  client_id: number;
  general: Record<string, unknown>;
  business: Record<string, unknown>;
  address: Record<string, unknown>;
  representative: Record<string, unknown>;
  logo_url: string;
  logo_media_id: string | null;
};

describe("SubAccount Business Profile settings page", () => {
  beforeEach(() => {
    vi.useRealTimers();
    window.localStorage.clear();
    vi.mocked(apiRequest).mockReset();
    vi.mocked(initDirectUpload).mockReset();
    vi.mocked(uploadFileToPresignedUrl).mockReset();
    vi.mocked(completeDirectUpload).mockReset();
    vi.mocked(getMediaAccessUrl).mockReset();
  });

  function setupApiMock(initial?: Partial<Store>) {
    const db: Store = {
      client_id: 1,
      general: {},
      business: {},
      address: {},
      representative: {},
      logo_url: "",
      logo_media_id: null,
      ...(initial ?? {}),
    };

    vi.mocked(apiRequest).mockImplementation(async (path: string, options?: RequestInit) => {
      if (path === "/clients/96/business-profile" && (!options || !options.method || options.method === "GET")) {
        return {
          client_name: "Client 96",
          client_id: db.client_id,
          display_id: 96,
          general: db.general,
          business: db.business,
          address: db.address,
          representative: db.representative,
          logo_url: db.logo_url,
          logo_media_id: db.logo_media_id,
        };
      }
      if (path === "/clients/96/business-profile" && options?.method === "PUT") {
        const payload = JSON.parse(String(options.body ?? "{}")) as Store;
        db.general = payload.general ?? {};
        db.business = payload.business ?? {};
        db.address = payload.address ?? {};
        db.representative = payload.representative ?? {};
        db.logo_url = String(payload.logo_url ?? "");
        db.logo_media_id = payload.logo_media_id ?? null;
        return {
          client_name: "Client 96",
          client_id: db.client_id,
          display_id: 96,
          general: db.general,
          business: db.business,
          address: db.address,
          representative: db.representative,
          logo_url: db.logo_url,
          logo_media_id: db.logo_media_id,
        };
      }
      throw new Error(`Unexpected path ${path}`);
    });
  }

  it("starts with empty form values when business profile is not saved, even if display data exists", async () => {
    setupApiMock();
    render(<SubAccountSettingsPage />);

    expect(await screen.findByTestId("app-shell-title")).toBeInTheDocument();
    expect(screen.getByLabelText(/Nume business \(friendly\)/i)).toHaveValue("");
    expect(screen.getByLabelText(/Email business/i)).toHaveValue("");
    expect(screen.getByLabelText(/Oraș/i)).toHaveValue("");
    expect(screen.queryByText("Logo salvat")).not.toBeInTheDocument();
    expect(screen.getByRole("option", { name: "Parc Auto" })).toBeInTheDocument();
  });

  it("saves profile explicitly and reloads saved values from business-profile endpoint", async () => {
    setupApiMock();
    const { unmount } = render(<SubAccountSettingsPage />);
    await screen.findByTestId("app-shell-title");

    fireEvent.change(screen.getByLabelText(/Nume business \(friendly\)/i), { target: { value: "ROC Auto" } });
    fireEvent.change(screen.getByLabelText(/Denumire legală business/i), { target: { value: "ROC Auto SRL" } });
    fireEvent.change(screen.getByLabelText(/Email business/i), { target: { value: "biz@roc.example" } });
    fireEvent.change(screen.getByLabelText(/Telefon business/i), { target: { value: "+40 700 111 222" } });
    fireEvent.change(screen.getByLabelText(/Website business/i), { target: { value: "https://roc.example" } });
    fireEvent.change(screen.getByLabelText(/Nișa business/i), { target: { value: "parc_auto" } });
    fireEvent.change(screen.getByLabelText(/Monedă business/i), { target: { value: "EUR" } });
    fireEvent.change(screen.getByLabelText(/Oraș/i), { target: { value: "Onești" } });
    fireEvent.click(screen.getAllByRole("button", { name: "Actualizează informațiile" })[0]);
    await screen.findByText("Informațiile generale au fost actualizate.");

    unmount();
    render(<SubAccountSettingsPage />);
    await screen.findByTestId("app-shell-title");

    expect(screen.getByLabelText(/Nume business \(friendly\)/i)).toHaveValue("ROC Auto");
    expect(screen.getByLabelText(/Email business/i)).toHaveValue("biz@roc.example");
    expect(screen.getByLabelText(/Oraș/i)).toHaveValue("Onești");
    expect(screen.getByLabelText(/Nișa business/i)).toHaveValue("parc_auto");
  });

  it("uses storage upload flow for logo and saves logo_media_id (not data URL)", async () => {
    setupApiMock();
    vi.mocked(initDirectUpload).mockResolvedValue({
      media_id: "m_logo_1",
      status: "draft",
      bucket: "assets",
      key: "clients/1/image/m_logo_1/logo.png",
      region: "eu-central-1",
      upload: { method: "PUT", url: "https://upload.local", expires_in: 900, headers: { "Content-Type": "image/png" } },
    });
    vi.mocked(uploadFileToPresignedUrl).mockResolvedValue();
    vi.mocked(completeDirectUpload).mockResolvedValue({
      media_id: "m_logo_1",
      status: "ready",
      bucket: "assets",
      key: "clients/1/image/m_logo_1/logo.png",
      region: "eu-central-1",
      mime_type: "image/png",
    });
    vi.mocked(getMediaAccessUrl).mockResolvedValue({
      media_id: "m_logo_1",
      status: "ready",
      mime_type: "image/png",
      method: "GET",
      url: "https://preview.local/logo.png",
      expires_in: 900,
      disposition: "inline",
      filename: "logo.png",
    });

    render(<SubAccountSettingsPage />);
    await screen.findByTestId("app-shell-title");

    const fileInput = screen.getByTestId("logo-input") as HTMLInputElement;
    const file = new File(["logo"], "logo.png", { type: "image/png" });
    fireEvent.change(fileInput, { target: { files: [file] } });

    await waitFor(() => {
      expect(initDirectUpload).toHaveBeenCalled();
      expect(uploadFileToPresignedUrl).toHaveBeenCalled();
      expect(completeDirectUpload).toHaveBeenCalledWith({ clientId: 1, mediaId: "m_logo_1" });
    });
    expect(await screen.findByAltText("Logo business")).toHaveAttribute("src", "https://preview.local/logo.png");

    fireEvent.change(screen.getByLabelText(/Nume business \(friendly\)/i), { target: { value: "Logo Biz" } });
    fireEvent.change(screen.getByLabelText(/Denumire legală business/i), { target: { value: "Logo Biz SRL" } });
    fireEvent.change(screen.getByLabelText(/Email business/i), { target: { value: "logo@biz.example" } });
    fireEvent.change(screen.getByLabelText(/Telefon business/i), { target: { value: "+40 700 111 333" } });
    fireEvent.change(screen.getByLabelText(/Website business/i), { target: { value: "https://logo.biz" } });
    fireEvent.change(screen.getByLabelText(/Nișa business/i), { target: { value: "parc_auto" } });
    fireEvent.change(screen.getByLabelText(/Monedă business/i), { target: { value: "EUR" } });
    fireEvent.click(screen.getAllByRole("button", { name: "Actualizează informațiile" })[0]);
    await screen.findByText("Informațiile generale au fost actualizate.");

    const putCall = vi.mocked(apiRequest).mock.calls.find((call) => call[0] === "/clients/96/business-profile" && call[1]?.method === "PUT");
    const putBody = JSON.parse(String(putCall?.[1]?.body ?? "{}"));
    expect(putBody.logo_media_id).toBe("m_logo_1");
    expect(putBody.logo_url).toBe("");
  });

  it("remove logo clears logo_media_id and logo_url in saved payload", async () => {
    setupApiMock({ logo_url: "https://preview.local/old.png", logo_media_id: "m_old" });
    render(<SubAccountSettingsPage />);
    await screen.findByTestId("app-shell-title");

    fireEvent.click(screen.getByRole("button", { name: /Remove/i }));
    fireEvent.change(screen.getByLabelText(/Nume business \(friendly\)/i), { target: { value: "Detach Biz" } });
    fireEvent.change(screen.getByLabelText(/Denumire legală business/i), { target: { value: "Detach Biz SRL" } });
    fireEvent.change(screen.getByLabelText(/Email business/i), { target: { value: "detach@biz.example" } });
    fireEvent.change(screen.getByLabelText(/Telefon business/i), { target: { value: "+40 700 111 444" } });
    fireEvent.change(screen.getByLabelText(/Website business/i), { target: { value: "https://detach.biz" } });
    fireEvent.change(screen.getByLabelText(/Nișa business/i), { target: { value: "parc_auto" } });
    fireEvent.change(screen.getByLabelText(/Monedă business/i), { target: { value: "EUR" } });
    fireEvent.click(screen.getAllByRole("button", { name: "Actualizează informațiile" })[0]);
    await screen.findByText("Informațiile generale au fost actualizate.");

    const putCall = vi.mocked(apiRequest).mock.calls.find((call) => call[0] === "/clients/96/business-profile" && call[1]?.method === "PUT");
    const putBody = JSON.parse(String(putCall?.[1]?.body ?? "{}"));
    expect(putBody.logo_media_id).toBeNull();
    expect(putBody.logo_url).toBe("");
  });

  it("shows clear error for invalid file type and oversized file", async () => {
    setupApiMock();
    render(<SubAccountSettingsPage />);
    await screen.findByTestId("app-shell-title");

    const fileInput = screen.getByTestId("logo-input") as HTMLInputElement;
    const badType = new File(["aaa"], "bad.txt", { type: "text/plain" });
    fireEvent.change(fileInput, { target: { files: [badType] } });
    expect(await screen.findByText(/Tip de fișier invalid/i)).toBeInTheDocument();

    const big = new File([new Uint8Array(3 * 1024 * 1024)], "big.png", { type: "image/png" });
    fireEvent.change(fileInput, { target: { files: [big] } });
    expect(await screen.findByText(/depășește limita de 2.5 MB/i)).toBeInTheDocument();
  });
});
