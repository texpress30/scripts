import React from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

const confirmResetPasswordMock = vi.fn();

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    confirmResetPassword: (...args: unknown[]) => confirmResetPasswordMock(...args),
  };
});

import ResetPasswordPage from "./page";

describe("Reset password page", () => {
  it("reads token from query string", () => {
    window.history.pushState({}, "", "/reset-password?token=query-token");
    render(<ResetPasswordPage />);
    expect(screen.queryByText(/Tokenul de resetare lipsește/i)).not.toBeInTheDocument();
  });

  it("blocks submit when passwords do not match", async () => {
    window.history.pushState({}, "", "/reset-password?token=abc123");
    render(<ResetPasswordPage />);

    fireEvent.change(screen.getByLabelText("Parolă nouă"), { target: { value: "new-password-123" } });
    fireEvent.change(screen.getByLabelText("Confirmă parola nouă"), { target: { value: "other-password-123" } });
    fireEvent.click(screen.getByRole("button", { name: "Resetează parola" }));

    expect(await screen.findByText("Parolele nu coincid.")).toBeInTheDocument();
    expect(confirmResetPasswordMock).not.toHaveBeenCalled();
  });

  it("sends correct request and shows success", async () => {
    window.history.pushState({}, "", "/reset-password?token=token-ok");
    confirmResetPasswordMock.mockResolvedValueOnce({ message: "Parola a fost resetată cu succes" });

    render(<ResetPasswordPage />);

    fireEvent.change(screen.getByLabelText("Parolă nouă"), { target: { value: "new-password-123" } });
    fireEvent.change(screen.getByLabelText("Confirmă parola nouă"), { target: { value: "new-password-123" } });
    fireEvent.click(screen.getByRole("button", { name: "Resetează parola" }));

    await waitFor(() => {
      expect(confirmResetPasswordMock).toHaveBeenCalledWith("token-ok", "new-password-123");
    });
    expect(await screen.findByText(/resetată cu succes/i)).toBeInTheDocument();
  });

  it("shows clear backend error for invalid token", async () => {
    window.history.pushState({}, "", "/reset-password?token=bad-token");
    const { ApiRequestError } = await import("@/lib/api");
    confirmResetPasswordMock.mockRejectedValueOnce(new ApiRequestError("Token invalid", 400));

    render(<ResetPasswordPage />);

    fireEvent.change(screen.getByLabelText("Parolă nouă"), { target: { value: "new-password-123" } });
    fireEvent.change(screen.getByLabelText("Confirmă parola nouă"), { target: { value: "new-password-123" } });
    fireEvent.click(screen.getByRole("button", { name: "Resetează parola" }));

    expect(await screen.findByText("Token invalid. Verifică linkul primit pe email.")).toBeInTheDocument();
  });

  it("shows clear message when token is missing", () => {
    window.history.pushState({}, "", "/reset-password");
    render(<ResetPasswordPage />);
    expect(screen.getByText("Tokenul de resetare lipsește din link.")).toBeInTheDocument();
  });
});
