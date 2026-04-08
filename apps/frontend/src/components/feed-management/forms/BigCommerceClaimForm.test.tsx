import React from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { BigCommerceClaimForm } from "./BigCommerceClaimForm";

const fetchAvailableMock = vi.fn();
const testConnectionMock = vi.fn();

vi.mock("@/lib/hooks/useBigCommerceSource", () => ({
  fetchAvailableBigCommerceStores: (...args: unknown[]) =>
    fetchAvailableMock(...args),
  testBigCommerceConnectionByStoreHash: (...args: unknown[]) =>
    testConnectionMock(...args),
}));

// NOTE: this test file uses ``React.createElement`` instead of JSX syntax to
// dodge a known parse failure in the locked vitest 4.1.3 + rolldown rc.13
// combo (the same parser bug that prevents ``PermissionsEditor.test.tsx``
// from running locally on this branch). The behaviour under test is the
// same — only the syntax differs.

function renderForm(busy = false) {
  const onClaim = vi.fn();
  const onCancel = vi.fn();
  render(
    React.createElement(BigCommerceClaimForm, { onClaim, onCancel, busy }),
  );
  return { onClaim, onCancel };
}

describe("BigCommerceClaimForm", () => {
  beforeEach(() => {
    fetchAvailableMock.mockReset();
    testConnectionMock.mockReset();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("renders the list of available stores from the API", async () => {
    fetchAvailableMock.mockResolvedValueOnce({
      total: 2,
      stores: [
        {
          store_hash: "abc123",
          installed_at: "2026-04-08T10:00:00Z",
          user_email: "owner@a.com",
          scope: "store_v2_products_read_only",
        },
        {
          store_hash: "def456",
          installed_at: "2026-04-08T11:00:00Z",
          user_email: "owner@b.com",
          scope: null,
        },
      ],
    });

    renderForm();

    await waitFor(() =>
      expect(screen.getByText("stores/abc123")).toBeInTheDocument(),
    );
    expect(screen.getByText("stores/def456")).toBeInTheDocument();
    expect(screen.getByText(/2 magazine disponibile/)).toBeInTheDocument();
    expect(fetchAvailableMock).toHaveBeenCalledTimes(1);
  });

  it("shows the empty state when no stores are installed", async () => {
    fetchAvailableMock.mockResolvedValueOnce({ total: 0, stores: [] });

    renderForm();

    await waitFor(() =>
      expect(screen.getByTestId("bc-empty-state")).toBeInTheDocument(),
    );
    expect(
      screen.getByText(
        /Nu există magazine BigCommerce disponibile pentru revendicare/,
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /Reîncarcă acum/ }),
    ).toBeInTheDocument();
  });

  it("enables the claim button only after a store is selected", async () => {
    fetchAvailableMock.mockResolvedValueOnce({
      total: 1,
      stores: [
        {
          store_hash: "abc123",
          installed_at: null,
          user_email: null,
          scope: null,
        },
      ],
    });

    renderForm();

    const claimButton = await screen.findByRole("button", {
      name: /Revendică/,
    });
    expect(claimButton).toBeDisabled();

    fireEvent.click(screen.getByRole("radio"));

    await waitFor(() => expect(claimButton).not.toBeDisabled());
  });

  it("auto-populates the source name when a store is selected", async () => {
    fetchAvailableMock.mockResolvedValueOnce({
      total: 1,
      stores: [
        {
          store_hash: "abc123",
          installed_at: null,
          user_email: null,
          scope: null,
        },
      ],
    });

    renderForm();
    await screen.findByText("stores/abc123");
    fireEvent.click(screen.getByRole("radio"));

    const nameInput = (await screen.findByLabelText(
      "Nume sursă",
    )) as HTMLInputElement;
    expect(nameInput.value).toBe("BigCommerce store abc123");
  });

  it("calls testConnection with the selected store_hash", async () => {
    fetchAvailableMock.mockResolvedValueOnce({
      total: 1,
      stores: [
        {
          store_hash: "abc123",
          installed_at: null,
          user_email: null,
          scope: null,
        },
      ],
    });
    testConnectionMock.mockResolvedValueOnce({
      success: true,
      store_name: "Acme BC",
      domain: "acme.example.com",
      secure_url: "https://acme.example.com",
      currency: "EUR",
      error: null,
    });

    renderForm();
    await screen.findByText("stores/abc123");
    fireEvent.click(screen.getByRole("radio"));

    fireEvent.click(
      screen.getByRole("button", { name: /Testează conexiunea/ }),
    );

    await waitFor(() =>
      expect(testConnectionMock).toHaveBeenCalledWith("abc123"),
    );
    await waitFor(() =>
      expect(screen.getByText(/Conectat: Acme BC/)).toBeInTheDocument(),
    );
    expect(screen.getByText(/acme.example.com/)).toBeInTheDocument();
    expect(screen.getByText(/EUR/)).toBeInTheDocument();
  });

  it("shows a friendly error when test connection fails", async () => {
    fetchAvailableMock.mockResolvedValueOnce({
      total: 1,
      stores: [
        {
          store_hash: "abc123",
          installed_at: null,
          user_email: null,
          scope: null,
        },
      ],
    });
    testConnectionMock.mockResolvedValueOnce({
      success: false,
      store_name: null,
      domain: null,
      secure_url: null,
      currency: null,
      error: "Invalid credentials",
    });

    renderForm();
    await screen.findByText("stores/abc123");
    fireEvent.click(screen.getByRole("radio"));
    fireEvent.click(
      screen.getByRole("button", { name: /Testează conexiunea/ }),
    );

    await waitFor(() =>
      expect(screen.getByText("Invalid credentials")).toBeInTheDocument(),
    );
  });

  it("calls onClaim with store_hash + source_name on submit", async () => {
    fetchAvailableMock.mockResolvedValueOnce({
      total: 1,
      stores: [
        {
          store_hash: "abc123",
          installed_at: null,
          user_email: null,
          scope: null,
        },
      ],
    });

    const { onClaim } = renderForm();
    await screen.findByText("stores/abc123");
    fireEvent.click(screen.getByRole("radio"));

    const nameInput = await screen.findByLabelText("Nume sursă");
    fireEvent.change(nameInput, { target: { value: "My Custom Name" } });

    fireEvent.click(screen.getByRole("button", { name: /Revendică/ }));

    expect(onClaim).toHaveBeenCalledTimes(1);
    expect(onClaim).toHaveBeenCalledWith({
      store_hash: "abc123",
      source_name: "My Custom Name",
    });
  });

  it("blocks submission when the source name is empty", async () => {
    fetchAvailableMock.mockResolvedValueOnce({
      total: 1,
      stores: [
        {
          store_hash: "abc123",
          installed_at: null,
          user_email: null,
          scope: null,
        },
      ],
    });

    const { onClaim } = renderForm();
    await screen.findByText("stores/abc123");
    fireEvent.click(screen.getByRole("radio"));

    const nameInput = await screen.findByLabelText("Nume sursă");
    fireEvent.change(nameInput, { target: { value: "   " } });

    fireEvent.click(screen.getByRole("button", { name: /Revendică/ }));

    expect(onClaim).not.toHaveBeenCalled();
    expect(
      screen.getByText("Numele sursei este obligatoriu."),
    ).toBeInTheDocument();
  });

  it("calls onCancel when the cancel button is clicked", async () => {
    fetchAvailableMock.mockResolvedValueOnce({ total: 0, stores: [] });
    const { onCancel } = renderForm();

    await screen.findByTestId("bc-empty-state");
    fireEvent.click(screen.getByRole("button", { name: "Anulează" }));
    expect(onCancel).toHaveBeenCalledTimes(1);
  });

  it("renders the error state and recovers via retry", async () => {
    fetchAvailableMock
      .mockRejectedValueOnce(new Error("Network down"))
      .mockResolvedValueOnce({
        total: 1,
        stores: [
          {
            store_hash: "abc123",
            installed_at: null,
            user_email: null,
            scope: null,
          },
        ],
      });

    renderForm();

    await waitFor(() =>
      expect(
        screen.getByText(/Nu s-au putut încărca magazinele/),
      ).toBeInTheDocument(),
    );
    expect(screen.getByText("Network down")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /Reîncearcă/ }));

    await waitFor(() =>
      expect(screen.getByText("stores/abc123")).toBeInTheDocument(),
    );
    expect(fetchAvailableMock).toHaveBeenCalledTimes(2);
  });
});
