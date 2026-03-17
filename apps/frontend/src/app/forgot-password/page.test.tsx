import React from "react";
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import ForgotPasswordPage from "./page";

const forgotPasswordMock = vi.fn();

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    forgotPassword: (...args: unknown[]) => forgotPasswordMock(...args),
  };
});

describe("Forgot password page", () => {
  it("sends correct request and shows generic success", async () => {
    forgotPasswordMock.mockResolvedValueOnce({
      message: "Dacă există un cont pentru această adresă, am trimis instrucțiunile de resetare.",
    });

    render(<ForgotPasswordPage />);

    fireEvent.change(screen.getByLabelText("Email"), { target: { value: "user@example.com" } });
    const submitButton = screen.getByRole("button", { name: "Trimite link de resetare" });
    fireEvent.submit(submitButton.closest("form") as HTMLFormElement);

    expect(await screen.findByText(/Dacă există un cont/)).toBeInTheDocument();
    expect(forgotPasswordMock).toHaveBeenCalledWith("user@example.com");
  });

  it("shows unavailable message when backend is temporarily unavailable", async () => {
    const { ApiRequestError } = await import("@/lib/api");
    forgotPasswordMock.mockRejectedValueOnce(new ApiRequestError("Reset password nu este disponibil momentan", 503));

    render(<ForgotPasswordPage />);

    fireEvent.change(screen.getByLabelText("Email"), { target: { value: "user@example.com" } });
    fireEvent.click(screen.getByRole("button", { name: "Trimite link de resetare" }));

    expect(await screen.findByText(/indisponibil momentan/i)).toBeInTheDocument();
  });
});
