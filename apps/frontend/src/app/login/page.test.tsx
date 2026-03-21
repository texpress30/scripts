import React from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import LoginPage from "./page";

const pushMock = vi.fn();
const loginWithPasswordMock = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: pushMock }),
}));

vi.mock("@/lib/api", () => ({
  loginWithPassword: (...args: unknown[]) => loginWithPasswordMock(...args),
}));

vi.mock("@/lib/session", () => ({
  getSessionAccessContextFromToken: () => ({
    role: "agency_admin",
    access_scope: "agency",
    allowed_subaccount_ids: [],
    primary_subaccount_id: null,
  }),
}));

describe("Login page", () => {
  it("renders forgot password link", () => {
    render(<LoginPage />);
    const link = screen.getByRole("link", { name: "Ai uitat parola?" });
    expect(link).toHaveAttribute("href", "/forgot-password");
  });

  it("does not render role selector", () => {
    render(<LoginPage />);
    expect(screen.queryByText("Rol")).not.toBeInTheDocument();
  });

  it("submits only email and password", async () => {
    loginWithPasswordMock.mockResolvedValue({ access_token: "header.payload.sig", token_type: "bearer" });
    render(<LoginPage />);

    fireEvent.change(screen.getByRole("textbox"), { target: { value: "user@example.com" } });
    fireEvent.change(screen.getByLabelText("Parola"), { target: { value: "secret123" } });
    fireEvent.click(screen.getByRole("button", { name: "Intră în platformă" }));

    await waitFor(() => {
      expect(loginWithPasswordMock).toHaveBeenCalledWith({
        email: "user@example.com",
        password: "secret123",
      });
    });
    expect(pushMock).toHaveBeenCalledWith("/agency/dashboard");
  });
});
