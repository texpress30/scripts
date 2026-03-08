import React from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import { MetaAgencyAccountsPanel } from "./MetaAgencyAccountsPanel";

const apiMock = vi.hoisted(() => ({ apiRequest: vi.fn() }));

vi.mock("@/lib/api", () => ({ apiRequest: apiMock.apiRequest }));

const clients = [
  { id: 11, name: "Client A", display_id: 1 },
  { id: 12, name: "Client B", display_id: 2 },
];

describe("MetaAgencyAccountsPanel", () => {
  beforeEach(() => {
    apiMock.apiRequest.mockReset();
  });

  it("loads and renders attached vs unattached accounts", async () => {
    apiMock.apiRequest.mockImplementation((path: string) => {
      if (path === "/clients/accounts/meta_ads") {
        return Promise.resolve({
          items: [
            { id: "act_1", name: "Meta One", attached_client_id: 11, attached_client_name: "Client A", status: "ACTIVE", currency: "USD", timezone: "UTC" },
            { id: "act_2", name: "Meta Two", attached_client_id: null, attached_client_name: null },
          ],
        });
      }
      return Promise.resolve({});
    });

    render(<MetaAgencyAccountsPanel clients={clients} />);

    expect(await screen.findByText("Meta One")).toBeInTheDocument();
    expect(screen.getByText("Client: Client A")).toBeInTheDocument();
    expect(screen.getByLabelText("client-select-act_2")).toBeInTheDocument();
  });

  it("attaches a meta account and reloads data", async () => {
    let loadCalls = 0;
    apiMock.apiRequest.mockImplementation((path: string, options?: { method?: string; body?: string }) => {
      if (path === "/clients/accounts/meta_ads") {
        loadCalls += 1;
        return Promise.resolve({ items: [{ id: "act_2", name: "Meta Two", attached_client_id: null }] });
      }
      if (path === "/clients/11/attach-account") {
        expect(options).toEqual({ method: "POST", body: JSON.stringify({ platform: "meta_ads", account_id: "act_2" }) });
        return Promise.resolve({ status: "ok" });
      }
      return Promise.resolve({});
    });

    render(<MetaAgencyAccountsPanel clients={clients} />);

    fireEvent.change(await screen.findByLabelText("client-select-act_2"), { target: { value: "11" } });
    fireEvent.click(screen.getByRole("button", { name: "Attach" }));

    await waitFor(() => {
      expect(apiMock.apiRequest).toHaveBeenCalledWith("/clients/11/attach-account", {
        method: "POST",
        body: JSON.stringify({ platform: "meta_ads", account_id: "act_2" }),
      });
    });
    expect(loadCalls).toBeGreaterThanOrEqual(2);
  });

  it("detaches a meta account and reloads data", async () => {
    let loadCalls = 0;
    apiMock.apiRequest.mockImplementation((path: string, options?: { method?: string; body?: string }) => {
      if (path === "/clients/accounts/meta_ads") {
        loadCalls += 1;
        return Promise.resolve({ items: [{ id: "act_1", name: "Meta One", attached_client_id: 11, attached_client_name: "Client A" }] });
      }
      if (path === "/clients/11/detach-account") {
        expect(options).toEqual({ method: "POST", body: JSON.stringify({ platform: "meta_ads", account_id: "act_1" }) });
        return Promise.resolve({ status: "ok" });
      }
      return Promise.resolve({});
    });

    render(<MetaAgencyAccountsPanel clients={clients} />);

    fireEvent.click(await screen.findByRole("button", { name: "Detach" }));

    await waitFor(() => {
      expect(apiMock.apiRequest).toHaveBeenCalledWith("/clients/11/detach-account", {
        method: "POST",
        body: JSON.stringify({ platform: "meta_ads", account_id: "act_1" }),
      });
    });
    expect(loadCalls).toBeGreaterThanOrEqual(2);
  });

  it("shows attach/detach error state", async () => {
    apiMock.apiRequest.mockImplementation((path: string) => {
      if (path === "/clients/accounts/meta_ads") {
        return Promise.resolve({ items: [{ id: "act_2", name: "Meta Two", attached_client_id: null }] });
      }
      if (path === "/clients/11/attach-account") {
        return Promise.reject(new Error("Attach failed"));
      }
      return Promise.resolve({});
    });

    render(<MetaAgencyAccountsPanel clients={clients} />);

    fireEvent.change(await screen.findByLabelText("client-select-act_2"), { target: { value: "11" } });
    fireEvent.click(screen.getByRole("button", { name: "Attach" }));

    expect(await screen.findByText("Attach failed")).toBeInTheDocument();
  });

  it("shows empty state when no meta accounts are imported", async () => {
    apiMock.apiRequest.mockImplementation((path: string) => {
      if (path === "/clients/accounts/meta_ads") {
        return Promise.resolve({ items: [] });
      }
      return Promise.resolve({});
    });

    render(<MetaAgencyAccountsPanel clients={clients} />);

    expect(await screen.findByText(/Nu există conturi Meta importate/i)).toBeInTheDocument();
  });
});
