import React from "react";
import { describe, expect, it, vi, beforeEach } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import AgencyEmailTemplatesPage from "./page";
import { ApiRequestError } from "@/lib/api";

const getAgencyEmailTemplatesMock = vi.fn();
const getAgencyEmailTemplateMock = vi.fn();
const saveAgencyEmailTemplateMock = vi.fn();
const resetAgencyEmailTemplateMock = vi.fn();

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    getAgencyEmailTemplates: (...args: unknown[]) => getAgencyEmailTemplatesMock(...args),
    getAgencyEmailTemplate: (...args: unknown[]) => getAgencyEmailTemplateMock(...args),
    saveAgencyEmailTemplate: (...args: unknown[]) => saveAgencyEmailTemplateMock(...args),
    resetAgencyEmailTemplate: (...args: unknown[]) => resetAgencyEmailTemplateMock(...args),
  };
});

vi.mock("@/components/ProtectedPage", () => ({
  ProtectedPage: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

vi.mock("@/components/AppShell", () => ({
  AppShell: ({ children, title }: { children: React.ReactNode; title: React.ReactNode }) => (
    <div>
      <div data-testid="app-shell-title">{String(title)}</div>
      {children}
    </div>
  ),
}));

describe("AgencyEmailTemplatesPage", () => {
  beforeEach(() => {
    getAgencyEmailTemplatesMock.mockReset();
    getAgencyEmailTemplateMock.mockReset();
    saveAgencyEmailTemplateMock.mockReset();
    resetAgencyEmailTemplateMock.mockReset();
    vi.spyOn(window, "confirm").mockReturnValue(true);

    getAgencyEmailTemplatesMock.mockResolvedValue({
      items: [
        {
          key: "auth_forgot_password",
          label: "Auth · Forgot Password",
          description: "Forgot template",
          scope: "agency",
          enabled: true,
          is_overridden: false,
          updated_at: null,
        },
        {
          key: "team_invite_user",
          label: "Team · Invite User",
          description: "Invite template",
          scope: "agency",
          enabled: true,
          is_overridden: true,
          updated_at: "2026-03-18T10:00:00+00:00",
        },
      ],
    });

    getAgencyEmailTemplateMock.mockImplementation(async (key: string) => ({
      key,
      label: key === "auth_forgot_password" ? "Auth · Forgot Password" : "Team · Invite User",
      description: key === "auth_forgot_password" ? "Forgot template" : "Invite template",
      subject: key === "auth_forgot_password" ? "Reset subject" : "Invite subject",
      text_body: key === "auth_forgot_password" ? "Reset text {{reset_link}}" : "Invite text {{invite_link}}",
      html_body: key === "auth_forgot_password" ? "<p>Reset html</p>" : "<p>Invite html</p>",
      available_variables: key === "auth_forgot_password" ? ["reset_link", "expires_minutes", "user_email"] : ["invite_link", "expires_minutes", "user_email"],
      scope: "agency",
      enabled: true,
      is_overridden: key !== "auth_forgot_password",
      updated_at: null,
    }));

    saveAgencyEmailTemplateMock.mockImplementation(async (key: string, payload: unknown) => ({
      key,
      label: "Saved",
      description: "Saved",
      ...(payload as object),
      available_variables: ["reset_link", "expires_minutes", "user_email"],
      scope: "agency",
      is_overridden: true,
      updated_at: "2026-03-18T12:00:00+00:00",
    }));

    resetAgencyEmailTemplateMock.mockResolvedValue({
      key: "auth_forgot_password",
      label: "Auth · Forgot Password",
      description: "Forgot template",
      subject: "Resetează parola",
      text_body: "Default text",
      html_body: "<p>Default html</p>",
      available_variables: ["reset_link", "expires_minutes", "user_email"],
      scope: "agency",
      enabled: true,
      is_overridden: false,
      updated_at: null,
    });
  });

  it("loads list via GET and loads detail for selected template", async () => {
    render(<AgencyEmailTemplatesPage />);

    expect(screen.getByTestId("app-shell-title")).toHaveTextContent("Email Templates");
    expect(getAgencyEmailTemplatesMock).toHaveBeenCalledTimes(1);

    expect(await screen.findByText("Auth · Forgot Password")).toBeInTheDocument();
    await waitFor(() => expect(getAgencyEmailTemplateMock).toHaveBeenCalledWith("auth_forgot_password"));

    fireEvent.click(screen.getByRole("button", { name: /Team · Invite User/i }));
    await waitFor(() => expect(getAgencyEmailTemplateMock).toHaveBeenCalledWith("team_invite_user"));
  });

  it("save sends PUT payload and shows success feedback", async () => {
    render(<AgencyEmailTemplatesPage />);

    await screen.findByDisplayValue("Reset subject");
    fireEvent.change(screen.getByLabelText("Subject"), { target: { value: "Updated subject" } });
    fireEvent.click(screen.getByRole("button", { name: "Save changes" }));

    await waitFor(() => {
      expect(saveAgencyEmailTemplateMock).toHaveBeenCalledWith("auth_forgot_password", {
        subject: "Updated subject",
        text_body: "Reset text {{reset_link}}",
        html_body: "<p>Reset html</p>",
        enabled: true,
      });
    });

    expect(await screen.findByText("Template salvat cu succes.")).toBeInTheDocument();
  });

  it("reset sends POST reset and shows success feedback", async () => {
    render(<AgencyEmailTemplatesPage />);

    await screen.findByDisplayValue("Reset subject");
    fireEvent.click(screen.getByRole("button", { name: "Reset to default" }));

    await waitFor(() => expect(resetAgencyEmailTemplateMock).toHaveBeenCalledWith("auth_forgot_password"));
    expect(await screen.findByText("Template resetat la valorile implicite.")).toBeInTheDocument();
  });

  it("shows loading states for list and detail", async () => {
    let resolveList: ((value: unknown) => void) | null = null;
    getAgencyEmailTemplatesMock.mockReturnValue(
      new Promise((resolve) => {
        resolveList = resolve;
      }),
    );

    render(<AgencyEmailTemplatesPage />);
    expect(screen.getByText("Se încarcă lista...")).toBeInTheDocument();

    resolveList?.({ items: [] });
    expect(await screen.findByText("Nu există template-uri disponibile.")).toBeInTheDocument();
  });

  it("handles 403 list error clearly", async () => {
    getAgencyEmailTemplatesMock.mockRejectedValueOnce(new ApiRequestError("forbidden", 403));
    render(<AgencyEmailTemplatesPage />);
    expect(await screen.findByText("Nu ai permisiunea necesară pentru Email Templates.")).toBeInTheDocument();
  });

  it("handles 404 detail error clearly", async () => {
    getAgencyEmailTemplatesMock.mockResolvedValueOnce({
      items: [
        {
          key: "auth_forgot_password",
          label: "Auth · Forgot Password",
          description: "Forgot template",
          scope: "agency",
          enabled: true,
          is_overridden: false,
          updated_at: null,
        },
      ],
    });
    getAgencyEmailTemplateMock.mockRejectedValueOnce(new ApiRequestError("missing", 404));

    render(<AgencyEmailTemplatesPage />);
    expect(await screen.findByText("Template-ul selectat nu a fost găsit.")).toBeInTheDocument();
  });

  it("handles 400 save validation error clearly", async () => {
    saveAgencyEmailTemplateMock.mockRejectedValueOnce(new ApiRequestError("subject este obligatoriu", 400));

    render(<AgencyEmailTemplatesPage />);
    await screen.findByDisplayValue("Reset subject");
    fireEvent.change(screen.getByLabelText("Subject"), { target: { value: "" } });
    fireEvent.click(screen.getByRole("button", { name: "Save changes" }));

    expect(await screen.findByText("subject este obligatoriu")).toBeInTheDocument();
  });
});
