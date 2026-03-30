import React from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const confirmResetPasswordMock = vi.fn();
const getResetPasswordTokenContextMock = vi.fn();

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    confirmResetPassword: (...args: unknown[]) => confirmResetPasswordMock(...args),
    getResetPasswordTokenContext: (...args: unknown[]) => getResetPasswordTokenContextMock(...args),
  };
});

import ResetPasswordPage from "./page";

describe("Reset password page", () => {
  beforeEach(() => {
    confirmResetPasswordMock.mockReset();
    getResetPasswordTokenContextMock.mockReset();
  });

  it("shows invite copy when token context is invite_user", async () => {
    window.history.pushState({}, "", "/reset-password?token=invite-token");
    getResetPasswordTokenContextMock.mockResolvedValueOnce({ valid: true, token_type: "invite_user" });

    render(<ResetPasswordPage />);
    expect(await screen.findByText("Setează parola contului")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Setează parola" })).toBeInTheDocument();
  });

  it("shows reset copy when token context is password_reset", async () => {
    window.history.pushState({}, "", "/reset-password?token=reset-token");
    getResetPasswordTokenContextMock.mockResolvedValueOnce({ valid: true, token_type: "password_reset" });

    render(<ResetPasswordPage />);
    expect(await screen.findByRole("heading", { name: "Resetează parola" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Resetează parola" })).toBeInTheDocument();
  });

  it("reads token from query string", () => {
    window.history.pushState({}, "", "/reset-password?token=query-token");
    getResetPasswordTokenContextMock.mockResolvedValueOnce({ valid: true, token_type: "password_reset" });
    render(<ResetPasswordPage />);
    expect(screen.queryByText(/Tokenul de resetare lipsește/i)).not.toBeInTheDocument();
  });

  it("blocks submit when passwords do not match", async () => {
    window.history.pushState({}, "", "/reset-password?token=abc123");
    getResetPasswordTokenContextMock.mockResolvedValueOnce({ valid: true, token_type: "password_reset" });
    render(<ResetPasswordPage />);

    fireEvent.change(screen.getByLabelText("Parolă nouă"), { target: { value: "new-password-123" } });
    fireEvent.change(screen.getByLabelText("Confirmă parola nouă"), { target: { value: "other-password-123" } });
    fireEvent.click(screen.getByRole("button", { name: "Resetează parola" }));

    expect(await screen.findByText("Parolele nu coincid.")).toBeInTheDocument();
    expect(confirmResetPasswordMock).not.toHaveBeenCalled();
  });

  it("sends correct request and shows success", async () => {
    window.history.pushState({}, "", "/reset-password?token=token-ok");
    getResetPasswordTokenContextMock.mockResolvedValueOnce({ valid: true, token_type: "password_reset" });
    confirmResetPasswordMock.mockResolvedValueOnce({ message: "Parola a fost resetată cu succes" });

    render(<ResetPasswordPage />);

    fireEvent.change(screen.getByLabelText("Parolă nouă"), { target: { value: "new-password-123" } });
    fireEvent.change(screen.getByLabelText("Confirmă parola nouă"), { target: { value: "new-password-123" } });
    fireEvent.click(screen.getByRole("button", { name: "Resetează parola" }));

    await waitFor(() => {
      expect(confirmResetPasswordMock).toHaveBeenCalledWith("token-ok", "new-password-123");
    });
    expect(await screen.findByText(/Te poți autentifica/i)).toBeInTheDocument();
  });

  it("shows invite-specific success state after confirm", async () => {
    window.history.pushState({}, "", "/reset-password?token=invite-success");
    getResetPasswordTokenContextMock.mockResolvedValueOnce({ valid: true, token_type: "invite_user" });
    confirmResetPasswordMock.mockResolvedValueOnce({ message: "ok" });

    render(<ResetPasswordPage />);
    expect(await screen.findByRole("heading", { name: "Setează parola contului" })).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Parolă nouă"), { target: { value: "new-password-123" } });
    fireEvent.change(screen.getByLabelText("Confirmă parola nouă"), { target: { value: "new-password-123" } });
    fireEvent.click(screen.getByRole("button", { name: "Setează parola" }));

    expect(await screen.findByText(/Contul a fost activat/i)).toBeInTheDocument();
  });

  it("shows clear backend error for invalid token", async () => {
    window.history.pushState({}, "", "/reset-password?token=bad-token");
    getResetPasswordTokenContextMock.mockResolvedValueOnce({ valid: true, token_type: "password_reset" });
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

  it("shows invalid-token state from context endpoint", async () => {
    window.history.pushState({}, "", "/reset-password?token=expired-token");
    getResetPasswordTokenContextMock.mockResolvedValueOnce({ valid: false, reason: "token_expired", token_type: null });

    render(<ResetPasswordPage />);
    expect(await screen.findByText(/a expirat/i)).toBeInTheDocument();
  });

  it("falls back safely when context request fails", async () => {
    window.history.pushState({}, "", "/reset-password?token=fallback-token");
    getResetPasswordTokenContextMock.mockRejectedValueOnce(new Error("network"));
    confirmResetPasswordMock.mockResolvedValueOnce({ message: "ok" });

    render(<ResetPasswordPage />);
    expect(await screen.findByText(/Nu am putut verifica tipul linkului acum/i)).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Parolă nouă"), { target: { value: "new-password-123" } });
    fireEvent.change(screen.getByLabelText("Confirmă parola nouă"), { target: { value: "new-password-123" } });
    fireEvent.click(screen.getByRole("button", { name: "Resetează parola" }));
    await waitFor(() => expect(confirmResetPasswordMock).toHaveBeenCalledWith("fallback-token", "new-password-123"));
  });
});
