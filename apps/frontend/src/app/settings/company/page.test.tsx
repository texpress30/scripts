import React from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import SettingsCompanyPage from "./page";
import { apiRequest } from "@/lib/api";
import { completeDirectUpload, getMediaAccessUrl, initDirectUpload, uploadFileToPresignedUrl } from "@/lib/storage-client";

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

type CompanySettingsPayload = {
  company_name: string;
  company_email: string;
  company_phone_prefix: string;
  company_phone: string;
  company_website: string;
  business_category: string;
  business_niche: string;
  platform_primary_use: string;
  address_line1: string;
  city: string;
  postal_code: string;
  region: string;
  country: string;
  timezone: string;
  logo_url: string;
  logo_media_id?: string | null;
  logo_storage_client_id?: number | null;
};

function defaultPayload(overrides?: Partial<CompanySettingsPayload>): CompanySettingsPayload {
  return {
    company_name: "Agency",
    company_email: "agency@example.com",
    company_phone_prefix: "+40",
    company_phone: "0700",
    company_website: "https://agency.example",
    business_category: "",
    business_niche: "",
    platform_primary_use: "",
    address_line1: "Street",
    city: "Cluj",
    postal_code: "400000",
    region: "CJ",
    country: "România",
    timezone: "Europe/Bucharest",
    logo_url: "",
    logo_media_id: null,
    logo_storage_client_id: 77,
    ...(overrides ?? {}),
  };
}

describe("SettingsCompanyPage", () => {
  beforeEach(() => {
    vi.mocked(apiRequest).mockReset();
    vi.mocked(initDirectUpload).mockReset();
    vi.mocked(uploadFileToPresignedUrl).mockReset();
    vi.mocked(completeDirectUpload).mockReset();
    vi.mocked(getMediaAccessUrl).mockReset();
  });

  it("uploads company logo through storage flow and saves logo_media_id", async () => {
    const db = defaultPayload();
    vi.mocked(apiRequest).mockImplementation(async (path: string, options?: RequestInit) => {
      if (path === "/company/settings" && (!options || !options.method || options.method === "GET")) return { ...db };
      if (path === "/company/settings" && options?.method === "PATCH") {
        const payload = JSON.parse(String(options.body ?? "{}"));
        Object.assign(db, payload);
        return { ...db, logo_url: "https://preview.example/logo.png" };
      }
      throw new Error(`Unexpected path ${path}`);
    });

    vi.mocked(initDirectUpload).mockResolvedValue({
      media_id: "m_company_logo",
      status: "draft",
      bucket: "assets",
      key: "clients/77/image/m_company_logo/logo.png",
      region: "eu-central-1",
      upload: { method: "PUT", url: "https://upload.local", expires_in: 900, headers: { "Content-Type": "image/png" } },
    });
    vi.mocked(uploadFileToPresignedUrl).mockResolvedValue();
    vi.mocked(completeDirectUpload).mockResolvedValue({
      media_id: "m_company_logo",
      status: "ready",
      bucket: "assets",
      key: "clients/77/image/m_company_logo/logo.png",
      region: "eu-central-1",
      mime_type: "image/png",
    });
    vi.mocked(getMediaAccessUrl).mockResolvedValue({
      media_id: "m_company_logo",
      status: "ready",
      mime_type: "image/png",
      method: "GET",
      url: "https://preview.example/logo.png",
      expires_in: 900,
      disposition: "inline",
      filename: "logo.png",
    });

    render(<SettingsCompanyPage />);
    await screen.findByTestId("app-shell-title");
    const dispatchSpy = vi.spyOn(window, "dispatchEvent");

    const fileInput = screen.getByTestId("company-logo-input") as HTMLInputElement;
    const file = new File(["logo"], "logo.png", { type: "image/png" });
    fireEvent.change(fileInput, { target: { files: [file] } });

    await waitFor(() => {
      expect(initDirectUpload).toHaveBeenCalledWith(
        expect.objectContaining({ clientId: 77, kind: "image", fileName: "logo.png", mimeType: "image/png" }),
      );
      expect(uploadFileToPresignedUrl).toHaveBeenCalled();
      expect(completeDirectUpload).toHaveBeenCalledWith({ clientId: 77, mediaId: "m_company_logo" });
    });

    fireEvent.click(screen.getByRole("button", { name: /Salvează Modificările/i }));
    await screen.findByText(/Setările companiei au fost salvate cu succes/i);

    const patchCall = vi.mocked(apiRequest).mock.calls.find((call) => call[0] === "/company/settings" && call[1]?.method === "PATCH");
    const patchBody = JSON.parse(String(patchCall?.[1]?.body ?? "{}"));
    expect(patchBody.logo_media_id).toBe("m_company_logo");
    expect(patchBody.logo_url).toBe("");
    expect(dispatchSpy).toHaveBeenCalledWith(expect.objectContaining({ type: "company-settings-updated" }));
  });

  it("remove logo clears logo_media_id and logo_url", async () => {
    const db = defaultPayload({ logo_url: "https://preview.example/old.png", logo_media_id: "m_old" });
    vi.mocked(apiRequest).mockImplementation(async (path: string, options?: RequestInit) => {
      if (path === "/company/settings" && (!options || !options.method || options.method === "GET")) return { ...db };
      if (path === "/company/settings" && options?.method === "PATCH") {
        const payload = JSON.parse(String(options.body ?? "{}"));
        Object.assign(db, payload);
        return { ...db };
      }
      throw new Error(`Unexpected path ${path}`);
    });

    render(<SettingsCompanyPage />);
    await screen.findByTestId("app-shell-title");

    fireEvent.click(screen.getByTestId("company-logo-remove"));
    fireEvent.click(screen.getByRole("button", { name: /Salvează Modificările/i }));
    await screen.findByText(/Setările companiei au fost salvate cu succes/i);

    const patchCall = vi.mocked(apiRequest).mock.calls.find((call) => call[0] === "/company/settings" && call[1]?.method === "PATCH");
    const patchBody = JSON.parse(String(patchCall?.[1]?.body ?? "{}"));
    expect(patchBody.logo_media_id).toBeNull();
    expect(patchBody.logo_url).toBe("");
  });

  it("shows clear validation errors for invalid type and oversized file", async () => {
    vi.mocked(apiRequest).mockResolvedValue(defaultPayload());

    render(<SettingsCompanyPage />);
    await screen.findByTestId("app-shell-title");

    const fileInput = screen.getByTestId("company-logo-input") as HTMLInputElement;
    fireEvent.change(fileInput, { target: { files: [new File(["x"], "bad.txt", { type: "text/plain" })] } });
    expect(await screen.findByText(/Tip de fișier invalid/i)).toBeInTheDocument();

    const big = new File([new Uint8Array(3 * 1024 * 1024)], "big.png", { type: "image/png" });
    fireEvent.change(fileInput, { target: { files: [big] } });
    expect(await screen.findByText(/depășește limita de 2.5 MB/i)).toBeInTheDocument();
  });
});
