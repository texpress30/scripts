import React from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import AgencyNotificationsPage from "./page";
import { ApiRequestError } from "@/lib/api";

const getAgencyEmailNotificationsMock = vi.fn();
const getAgencyEmailNotificationMock = vi.fn();
const saveAgencyEmailNotificationMock = vi.fn();
const resetAgencyEmailNotificationMock = vi.fn();
const previewAgencyEmailTemplateMock = vi.fn();
const sendAgencyEmailTemplateTestMock = vi.fn();
const getMailgunStatusMock = vi.fn();

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    getAgencyEmailNotifications: (...args: unknown[]) => getAgencyEmailNotificationsMock(...args),
    getAgencyEmailNotification: (...args: unknown[]) => getAgencyEmailNotificationMock(...args),
    saveAgencyEmailNotification: (...args: unknown[]) => saveAgencyEmailNotificationMock(...args),
    resetAgencyEmailNotification: (...args: unknown[]) => resetAgencyEmailNotificationMock(...args),
    previewAgencyEmailTemplate: (...args: unknown[]) => previewAgencyEmailTemplateMock(...args),
    sendAgencyEmailTemplateTest: (...args: unknown[]) => sendAgencyEmailTemplateTestMock(...args),
    getMailgunStatus: (...args: unknown[]) => getMailgunStatusMock(...args),
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

describe("AgencyNotificationsPage", () => {
  beforeEach(() => {
    getAgencyEmailNotificationsMock.mockReset();
    getAgencyEmailNotificationMock.mockReset();
    saveAgencyEmailNotificationMock.mockReset();
    resetAgencyEmailNotificationMock.mockReset();
    previewAgencyEmailTemplateMock.mockReset();
    sendAgencyEmailTemplateTestMock.mockReset();
    getMailgunStatusMock.mockReset();
    vi.spyOn(window, "confirm").mockReturnValue(true);

    getAgencyEmailNotificationsMock.mockResolvedValue({
      items: [
        {
          key: "auth_forgot_password",
          label: "Auth · Forgot Password",
          description: "desc forgot",
          channel: "email",
          scope: "agency",
          template_key: "auth_forgot_password",
          enabled: true,
          is_overridden: false,
          updated_at: null,
        },
        {
          key: "team_invite_user",
          label: "Team · Invite User",
          description: "desc invite",
          channel: "email",
          scope: "agency",
          template_key: "team_invite_user",
          enabled: false,
          is_overridden: true,
          updated_at: "2026-03-18T10:00:00+00:00",
        },
      ],
    });
    getAgencyEmailNotificationMock.mockImplementation(async (key: string) => ({
      key,
      label: key === "auth_forgot_password" ? "Auth · Forgot Password" : "Team · Invite User",
      description: key === "auth_forgot_password" ? "desc forgot" : "desc invite",
      channel: "email",
      scope: "agency",
      template_key: key,
      enabled: key === "auth_forgot_password",
      default_enabled: true,
      is_overridden: key !== "auth_forgot_password",
      updated_at: null,
    }));
    saveAgencyEmailNotificationMock.mockResolvedValue({});
    resetAgencyEmailNotificationMock.mockResolvedValue({});
    previewAgencyEmailTemplateMock.mockResolvedValue({
      key: "auth_forgot_password",
      rendered_subject: "Preview subject",
      rendered_text_body: "Preview text",
      rendered_html_body: "<p>Preview html</p>",
      sample_variables: {},
      is_overridden: false,
    });
    sendAgencyEmailTemplateTestMock.mockResolvedValue({
      key: "auth_forgot_password",
      to_email: "qa@example.com",
      accepted: true,
      delivery_status: "accepted",
      rendered_subject: "Preview subject",
      provider_message: "Queued. Thank you.",
      provider_id: "<mailgun-id>",
    });
    getMailgunStatusMock.mockResolvedValue({
      configured: true,
      enabled: true,
      config_source: "env",
      domain: "mg.env.example.com",
      base_url: "https://api.mailgun.net",
      from_email: "env@example.com",
      from_name: "Env Sender",
      reply_to: "",
      api_key_masked: "key***env",
    });
  });

  it("loads list and first detail", async () => {
    render(<AgencyNotificationsPage />);

    expect(screen.getByTestId("app-shell-title")).toHaveTextContent("Notifications");
    expect(await screen.findByText("Auth · Forgot Password")).toBeInTheDocument();
    await waitFor(() => expect(getAgencyEmailNotificationMock).toHaveBeenCalledWith("auth_forgot_password"));
    expect(screen.getByLabelText("Notifications overview list")).toBeInTheDocument();
    expect(screen.getByLabelText("Notification detail panel")).toBeInTheDocument();
  });

  it("selects item and loads detail", async () => {
    render(<AgencyNotificationsPage />);
    await screen.findByText("Auth · Forgot Password");

    fireEvent.click(screen.getByRole("button", { name: /Team · Invite User/i }));
    await waitFor(() => expect(getAgencyEmailNotificationMock).toHaveBeenCalledWith("team_invite_user"));
    expect(await screen.findByText("Template key:")).toBeInTheDocument();
    expect(screen.getByText(/fără parolă => email set-password/i)).toBeInTheDocument();
    expect(screen.getByText(/cu parolă => email account-ready\/login/i)).toBeInTheDocument();
  });

  it("renders badges and associated template link", async () => {
    render(<AgencyNotificationsPage />);
    expect(await screen.findByText("Default")).toBeInTheDocument();
    expect(screen.getByText("Overridden")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Edit associated template" })).toHaveAttribute("href", "/agency/email-templates?template=auth_forgot_password");
  });

  it("save sends PUT payload and refetches detail/list", async () => {
    render(<AgencyNotificationsPage />);
    await screen.findByText("Auth · Forgot Password");

    const enabledToggle = screen.getByRole("checkbox", { name: "Enabled" });
    fireEvent.click(enabledToggle);
    fireEvent.click(screen.getByRole("button", { name: "Save changes" }));

    await waitFor(() => expect(saveAgencyEmailNotificationMock).toHaveBeenCalledWith("auth_forgot_password", { enabled: false }));
    expect(getAgencyEmailNotificationsMock).toHaveBeenCalledTimes(2);
    expect(getAgencyEmailNotificationMock).toHaveBeenCalledTimes(2);
    expect(await screen.findByText("Notification salvată cu succes.")).toBeInTheDocument();
  });

  it("reset sends POST reset and refetches detail/list", async () => {
    render(<AgencyNotificationsPage />);
    await screen.findByText("Auth · Forgot Password");

    fireEvent.click(screen.getByRole("button", { name: "Reset to default" }));
    await waitFor(() => expect(resetAgencyEmailNotificationMock).toHaveBeenCalledWith("auth_forgot_password"));
    expect(getAgencyEmailNotificationsMock).toHaveBeenCalledTimes(2);
    expect(getAgencyEmailNotificationMock).toHaveBeenCalledTimes(2);
    expect(await screen.findByText("Notification resetată la valorile implicite.")).toBeInTheDocument();
  });

  it("shows list loading state", async () => {
    let resolveList: ((value: unknown) => void) | null = null;
    getAgencyEmailNotificationsMock.mockReturnValueOnce(
      new Promise((resolve) => {
        resolveList = resolve;
      }),
    );

    render(<AgencyNotificationsPage />);
    expect(screen.getByText("Se încarcă lista...")).toBeInTheDocument();

    resolveList?.({ items: [] });
    expect(await screen.findByText("Nu există notifications disponibile.")).toBeInTheDocument();
  });

  it("shows 403 list error", async () => {
    getAgencyEmailNotificationsMock.mockRejectedValueOnce(new ApiRequestError("forbidden", 403));
    render(<AgencyNotificationsPage />);
    expect(await screen.findByText("Nu ai permisiunea necesară pentru Notifications.")).toBeInTheDocument();
  });

  it("shows 404 detail error", async () => {
    getAgencyEmailNotificationMock.mockRejectedValueOnce(new ApiRequestError("missing", 404));
    render(<AgencyNotificationsPage />);
    expect(await screen.findByText("Notificarea selectată nu a fost găsită.")).toBeInTheDocument();
  });

  it("shows 400 save error", async () => {
    saveAgencyEmailNotificationMock.mockRejectedValueOnce(new ApiRequestError("enabled este obligatoriu", 400));
    render(<AgencyNotificationsPage />);
    await screen.findByText("Auth · Forgot Password");
    fireEvent.click(screen.getByRole("checkbox", { name: "Enabled" }));
    fireEvent.click(screen.getByRole("button", { name: "Save changes" }));
    expect(await screen.findByText("enabled este obligatoriu")).toBeInTheDocument();
  });

  it("previews associated template using template_key", async () => {
    render(<AgencyNotificationsPage />);
    await screen.findByText("Auth · Forgot Password");

    fireEvent.click(screen.getByRole("button", { name: "Preview template" }));
    await waitFor(() => expect(previewAgencyEmailTemplateMock).toHaveBeenCalledWith("auth_forgot_password"));
    expect(await screen.findByLabelText("Notification template preview panel")).toBeInTheDocument();
    expect(screen.getByText("Preview subject")).toBeInTheDocument();
  });

  it("shows preview loading state", async () => {
    let resolvePreview: ((value: unknown) => void) | null = null;
    previewAgencyEmailTemplateMock.mockReturnValueOnce(
      new Promise((resolve) => {
        resolvePreview = resolve;
      }),
    );

    render(<AgencyNotificationsPage />);
    await screen.findByText("Auth · Forgot Password");
    fireEvent.click(screen.getByRole("button", { name: "Preview template" }));
    expect(screen.getByRole("button", { name: "Previewing..." })).toBeInTheDocument();

    resolvePreview?.({
      key: "auth_forgot_password",
      rendered_subject: "Done",
      rendered_text_body: "Done",
      rendered_html_body: "<p>Done</p>",
      sample_variables: {},
      is_overridden: false,
    });
    expect(await screen.findByLabelText("Notification template preview panel")).toBeInTheDocument();
  });

  it("send test email uses associated template_key", async () => {
    render(<AgencyNotificationsPage />);
    await screen.findByText("Auth · Forgot Password");

    fireEvent.change(screen.getByLabelText("Test email"), { target: { value: "qa@example.com" } });
    fireEvent.click(screen.getByRole("button", { name: "Send test email" }));
    await waitFor(() => expect(sendAgencyEmailTemplateTestMock).toHaveBeenCalledWith("auth_forgot_password", { to_email: "qa@example.com" }));
    expect(await screen.findByText(/Cererea a fost acceptată de Mailgun/)).toBeInTheDocument();
    expect(screen.getByText("Provider message:")).toBeInTheDocument();
  });

  it("shows test-send loading state", async () => {
    let resolveSend: ((value: unknown) => void) | null = null;
    sendAgencyEmailTemplateTestMock.mockReturnValueOnce(
      new Promise((resolve) => {
        resolveSend = resolve;
      }),
    );

    render(<AgencyNotificationsPage />);
    await screen.findByText("Auth · Forgot Password");
    fireEvent.change(screen.getByLabelText("Test email"), { target: { value: "qa@example.com" } });
    fireEvent.click(screen.getByRole("button", { name: "Send test email" }));
    expect(screen.getByRole("button", { name: "Se trimite..." })).toBeInTheDocument();

    resolveSend?.({
      key: "auth_forgot_password",
      to_email: "qa@example.com",
      accepted: true,
      delivery_status: "accepted",
      rendered_subject: "Done",
      provider_message: "Queued. Thank you.",
      provider_id: "<id>",
    });
    expect(await screen.findByText("Queued. Thank you.")).toBeInTheDocument();
  });

  it("handles 403/404/400/503 for preview and test-send", async () => {
    render(<AgencyNotificationsPage />);
    await screen.findByText("Auth · Forgot Password");

    previewAgencyEmailTemplateMock.mockRejectedValueOnce(new ApiRequestError("forbidden", 403));
    fireEvent.click(screen.getByRole("button", { name: "Preview template" }));
    expect(await screen.findByText("Nu ai permisiunea necesară pentru Notifications.")).toBeInTheDocument();

    previewAgencyEmailTemplateMock.mockRejectedValueOnce(new ApiRequestError("missing", 404));
    fireEvent.click(screen.getByRole("button", { name: "Preview template" }));
    expect(await screen.findByText("Notificarea selectată nu a fost găsită.")).toBeInTheDocument();

    sendAgencyEmailTemplateTestMock.mockRejectedValueOnce(new ApiRequestError("invalid email", 400));
    fireEvent.change(screen.getByLabelText("Test email"), { target: { value: "qa@example.com" } });
    fireEvent.click(screen.getByRole("button", { name: "Send test email" }));
    expect(await screen.findByText("invalid email")).toBeInTheDocument();

    sendAgencyEmailTemplateTestMock.mockRejectedValueOnce(new ApiRequestError("Mailgun unavailable", 503));
    fireEvent.click(screen.getByRole("button", { name: "Send test email" }));
    expect(await screen.findByText("Mailgun unavailable")).toBeInTheDocument();
  });
});
