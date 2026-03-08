import React from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import { TikTokAgencyAccountsPanel } from "./TikTokAgencyAccountsPanel";

const apiMock = vi.hoisted(() => ({ apiRequest: vi.fn() }));

vi.mock("@/lib/api", () => ({ apiRequest: apiMock.apiRequest }));

describe("TikTokAgencyAccountsPanel", () => {
  beforeEach(() => {
    apiMock.apiRequest.mockReset();
  });

  it("loads and renders attached vs unattached TikTok accounts", async () => {
    apiMock.apiRequest.mockImplementation((path: string) => {
      if (path === "/clients") return Promise.resolve({ items: [{ id: 1, name: "Client A" }] });
      if (path === "/clients/accounts/tiktok_ads") {
        return Promise.resolve({
          items: [
            { id: "111", name: "TT Attached", attached_client_id: 1, attached_client_name: "Client A", status: "ACTIVE", currency: "USD", timezone: "UTC" },
            { id: "222", name: "TT Unattached", attached_client_id: null, attached_client_name: null, status: "ACTIVE", currency: "EUR", timezone: "Europe/Bucharest" },
          ],
          count: 2,
        });
      }
      return Promise.resolve({});
    });

    render(<TikTokAgencyAccountsPanel />);

    expect(await screen.findByText("TT Attached")).toBeInTheDocument();
    expect(screen.getByText("Atașat la Client A")).toBeInTheDocument();
    expect(screen.getByText("TT Unattached")).toBeInTheDocument();
    expect(screen.getByText("Neatașat")).toBeInTheDocument();
  });

  it("attaches an unattached TikTok account and reloads list", async () => {
    let call = 0;
    apiMock.apiRequest.mockImplementation((path: string) => {
      if (path === "/clients") return Promise.resolve({ items: [{ id: 1, name: "Client A" }] });
      if (path === "/clients/accounts/tiktok_ads") {
        call += 1;
        if (call === 1) {
          return Promise.resolve({ items: [{ id: "222", name: "TT Unattached", attached_client_id: null, attached_client_name: null }] });
        }
        return Promise.resolve({ items: [{ id: "222", name: "TT Unattached", attached_client_id: 1, attached_client_name: "Client A" }] });
      }
      if (path === "/clients/1/attach-account") return Promise.resolve({ status: "ok" });
      return Promise.resolve({});
    });

    render(<TikTokAgencyAccountsPanel />);

    expect(await screen.findByText("TT Unattached")).toBeInTheDocument();
    fireEvent.change(screen.getByDisplayValue("Selectează client"), { target: { value: "1" } });
    fireEvent.click(screen.getByRole("button", { name: "Attach" }));

    expect(await screen.findByText("Contul 222 a fost atașat la Client A.")).toBeInTheDocument();
    expect(await screen.findByText("Atașat la Client A")).toBeInTheDocument();
  });

  it("detaches an attached TikTok account and reloads list", async () => {
    let call = 0;
    apiMock.apiRequest.mockImplementation((path: string) => {
      if (path === "/clients") return Promise.resolve({ items: [{ id: 1, name: "Client A" }] });
      if (path === "/clients/accounts/tiktok_ads") {
        call += 1;
        if (call === 1) {
          return Promise.resolve({ items: [{ id: "111", name: "TT Attached", attached_client_id: 1, attached_client_name: "Client A" }] });
        }
        return Promise.resolve({ items: [{ id: "111", name: "TT Attached", attached_client_id: null, attached_client_name: null }] });
      }
      if (path === "/clients/1/detach-account") return Promise.resolve({ status: "ok" });
      return Promise.resolve({});
    });

    render(<TikTokAgencyAccountsPanel />);

    expect(await screen.findByText("TT Attached")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Detach" }));

    expect(await screen.findByText("Contul 111 a fost detașat de la Client A.")).toBeInTheDocument();
    expect(await screen.findByText("Neatașat")).toBeInTheDocument();
  });

  it("shows attach and detach errors", async () => {
    apiMock.apiRequest.mockImplementation((path: string) => {
      if (path === "/clients") return Promise.resolve({ items: [{ id: 1, name: "Client A" }] });
      if (path === "/clients/accounts/tiktok_ads") {
        return Promise.resolve({
          items: [
            { id: "111", name: "TT Attached", attached_client_id: 1, attached_client_name: "Client A" },
            { id: "222", name: "TT Unattached", attached_client_id: null, attached_client_name: null },
          ],
        });
      }
      if (path === "/clients/1/attach-account") return Promise.reject(new Error("Attach failed"));
      if (path === "/clients/1/detach-account") return Promise.reject(new Error("Detach failed"));
      return Promise.resolve({});
    });

    render(<TikTokAgencyAccountsPanel />);

    expect(await screen.findByText("TT Attached")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Detach" }));
    expect(await screen.findByText("Detach failed")).toBeInTheDocument();

    fireEvent.change(screen.getByDisplayValue("Selectează client"), { target: { value: "1" } });
    fireEvent.click(screen.getByRole("button", { name: "Attach" }));
    expect(await screen.findByText("Attach failed")).toBeInTheDocument();
  });

  it("renders empty state when no TikTok accounts are imported", async () => {
    apiMock.apiRequest.mockImplementation((path: string) => {
      if (path === "/clients") return Promise.resolve({ items: [{ id: 1, name: "Client A" }] });
      if (path === "/clients/accounts/tiktok_ads") return Promise.resolve({ items: [], count: 0 });
      return Promise.resolve({});
    });

    render(<TikTokAgencyAccountsPanel />);

    expect(await screen.findByText(/Nu există conturi TikTok importate încă/i)).toBeInTheDocument();
  });

  it("shows robust unavailable message when TikTok integration endpoint fails", async () => {
    apiMock.apiRequest.mockImplementation((path: string) => {
      if (path === "/clients") return Promise.resolve({ items: [{ id: 1, name: "Client A" }] });
      if (path === "/clients/accounts/tiktok_ads") return Promise.reject(new Error("TikTok integration is disabled by feature flag."));
      return Promise.resolve({});
    });

    render(<TikTokAgencyAccountsPanel />);

    expect(await screen.findByText(/TikTok este momentan indisponibil/i)).toBeInTheDocument();
  });

  it("disables attach when client list is empty", async () => {
    apiMock.apiRequest.mockImplementation((path: string) => {
      if (path === "/clients") return Promise.resolve({ items: [] });
      if (path === "/clients/accounts/tiktok_ads") {
        return Promise.resolve({ items: [{ id: "222", name: "TT Unattached", attached_client_id: null, attached_client_name: null }] });
      }
      return Promise.resolve({});
    });

    render(<TikTokAgencyAccountsPanel />);

    expect(await screen.findByText("TT Unattached")).toBeInTheDocument();
    const attachButton = screen.getByRole("button", { name: "Attach" });
    await waitFor(() => expect(attachButton).toBeDisabled());
    expect(screen.getByText(/Attach indisponibil: lista de clienți este goală/i)).toBeInTheDocument();
  });
});
