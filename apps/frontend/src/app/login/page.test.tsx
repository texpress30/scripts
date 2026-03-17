import React from "react";
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import LoginPage from "./page";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
  useSearchParams: () => new URLSearchParams(""),
}));

describe("Login page", () => {
  it("renders forgot password link", () => {
    render(<LoginPage />);
    const link = screen.getByRole("link", { name: "Ai uitat parola?" });
    expect(link).toHaveAttribute("href", "/forgot-password");
  });
});
