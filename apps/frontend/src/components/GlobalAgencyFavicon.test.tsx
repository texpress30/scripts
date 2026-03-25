import React from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, waitFor } from "@testing-library/react";

import { GlobalAgencyFavicon } from "./GlobalAgencyFavicon";
import { apiRequest } from "@/lib/api";

const globalFaviconSpy = vi.fn();

vi.mock("@/lib/api", () => ({
  apiRequest: vi.fn(),
}));

vi.mock("@/components/GlobalFavicon", () => ({
  GlobalFavicon: ({ agencyLogoUrl, refreshKey }: { agencyLogoUrl?: string | null; refreshKey?: number }) => {
    globalFaviconSpy({ agencyLogoUrl, refreshKey });
    return null;
  },
}));

describe("GlobalAgencyFavicon", () => {
  beforeEach(() => {
    globalFaviconSpy.mockReset();
    vi.mocked(apiRequest).mockReset();
  });

  it("loads agency logo_url and feeds the same global favicon mechanism used in app shell routes", async () => {
    vi.mocked(apiRequest).mockResolvedValue({ logo_url: "https://cdn.example/agency.png" });

    render(<GlobalAgencyFavicon />);

    await waitFor(() => {
      expect(apiRequest).toHaveBeenCalledWith("/company/settings", { requireAuth: true });
      expect(globalFaviconSpy).toHaveBeenLastCalledWith({ agencyLogoUrl: "https://cdn.example/agency.png", refreshKey: 1 });
    });
  });

  it("falls back to default path input when company logo is missing", async () => {
    vi.mocked(apiRequest).mockResolvedValue({ logo_url: "   " });

    render(<GlobalAgencyFavicon />);

    await waitFor(() => {
      expect(globalFaviconSpy).toHaveBeenLastCalledWith({ agencyLogoUrl: "", refreshKey: 1 });
    });
  });

  it("falls back cleanly when load fails (invalid/missing logo source)", async () => {
    vi.mocked(apiRequest).mockRejectedValue(new Error("unauthorized"));

    render(<GlobalAgencyFavicon />);

    await waitFor(() => {
      expect(globalFaviconSpy).toHaveBeenLastCalledWith({ agencyLogoUrl: "", refreshKey: 1 });
    });
  });

  it("refreshes favicon source after company-settings-updated so landing/app stay consistent", async () => {
    vi.mocked(apiRequest)
      .mockResolvedValueOnce({ logo_url: "https://cdn.example/old.png" })
      .mockResolvedValueOnce({ logo_url: "https://cdn.example/new.png" });

    render(<GlobalAgencyFavicon />);

    await waitFor(() => {
      expect(globalFaviconSpy).toHaveBeenLastCalledWith({ agencyLogoUrl: "https://cdn.example/old.png", refreshKey: 1 });
    });

    window.dispatchEvent(new CustomEvent("company-settings-updated"));

    await waitFor(() => {
      expect(globalFaviconSpy).toHaveBeenLastCalledWith({ agencyLogoUrl: "https://cdn.example/new.png", refreshKey: 2 });
    });
  });

  it("keeps agency logo mechanism through rerender/navigation-like transitions", async () => {
    vi.mocked(apiRequest).mockResolvedValue({ logo_url: "https://cdn.example/agency.png" });

    const { rerender } = render(<GlobalAgencyFavicon />);
    rerender(<GlobalAgencyFavicon />);

    await waitFor(() => {
      expect(globalFaviconSpy).toHaveBeenLastCalledWith({ agencyLogoUrl: "https://cdn.example/agency.png", refreshKey: 1 });
    });
  });
});
