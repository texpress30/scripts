import React from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import AgencyEmailTemplatesPage from "./page";
import { ApiRequestError } from "@/lib/api";

const getAgencyEmailTemplatesMock = vi.fn();
const getAgencyEmailTemplateMock = vi.fn();
const saveAgencyEmailTemplateMock = vi.fn();
const resetAgencyEmailTemplateMock = vi.fn();
const previewAgencyEmailTemplateMock = vi.fn();
const sendAgencyEmailTemplateTestMock = vi.fn();
const getMailgunStatusMock = vi.fn();

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    getAgencyEmailTemplates: (...args: unknown[]) => getAgencyEmailTemplatesMock(...args),
    getAgencyEmailTemplate: (...args: unknown[]) => getAgencyEmailTemplateMock(...args),
    saveAgencyEmailTemplate: (...args: unknown[]) => saveAgencyEmailTemplateMock(...args),
    resetAgencyEmailTemplate: (...args: unknown[]) => resetAgencyEmailTemplateMock(...args),
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

describe("AgencyEmailTemplatesPage", () => {
  function setHtmlSourceEditor(nextValue: string) {
    fireEvent.click(screen.getByRole("button", { name: "HTML" }));
    fireEvent.change(screen.getByTestId("html-source-editor"), { target: { value: nextValue } });
  }

  beforeEach(() => {
    getAgencyEmailTemplatesMock.mockReset();
    getAgencyEmailTemplateMock.mockReset();
    saveAgencyEmailTemplateMock.mockReset();
    resetAgencyEmailTemplateMock.mockReset();
    previewAgencyEmailTemplateMock.mockReset();
    sendAgencyEmailTemplateTestMock.mockReset();
    getMailgunStatusMock.mockReset();
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
          enabled: false,
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

    saveAgencyEmailTemplateMock.mockResolvedValue({});
    resetAgencyEmailTemplateMock.mockResolvedValue({});
    previewAgencyEmailTemplateMock.mockResolvedValue({
      key: "auth_forgot_password",
      rendered_subject: "Rendered preview subject",
      rendered_text_body: "Rendered preview text",
      rendered_html_body: "<p>Rendered preview html</p>",
      sample_variables: {
        reset_link: "https://app.example.com/reset",
        expires_minutes: "60",
      },
      is_overridden: false,
    });
    sendAgencyEmailTemplateTestMock.mockResolvedValue({
      key: "auth_forgot_password",
      to_email: "qa@example.com",
      accepted: true,
      delivery_status: "accepted",
      rendered_subject: "Rendered preview subject",
      provider_message: "Queued. Thank you.",
      provider_id: "<mailgun-message-id>",
    });
    getMailgunStatusMock.mockResolvedValue({
      configured: true,
      enabled: true,
      config_source: "db",
      domain: "mg.example.com",
      base_url: "https://api.mailgun.net",
      from_email: "noreply@example.com",
      from_name: "Example",
      reply_to: "",
      api_key_masked: "key-***",
    });
  });

  it("renders notification-style title and list overview badges", async () => {
    render(<AgencyEmailTemplatesPage />);

    expect(screen.getByTestId("app-shell-title")).toHaveTextContent("Email Templates & Notifications");
    expect(await screen.findByText("Auth · Forgot Password")).toBeInTheDocument();
    expect(screen.getAllByText("Enabled").length).toBeGreaterThan(0);
    expect(screen.getByText("Disabled")).toBeInTheDocument();
    expect(screen.getAllByText("Default").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Overridden").length).toBeGreaterThan(0);
  });

  it("renders rich html editor and loads current html value", async () => {
    render(<AgencyEmailTemplatesPage />);
    await screen.findByDisplayValue("Reset subject");

    expect(screen.getByTestId("html-rich-editor")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "HTML" }));
    expect((screen.getByTestId("html-source-editor") as HTMLTextAreaElement).value).toBe("<p>Reset html</p>");
  });

  it("selects item and loads detail panel", async () => {
    render(<AgencyEmailTemplatesPage />);

    await waitFor(() => expect(getAgencyEmailTemplateMock).toHaveBeenCalledWith("auth_forgot_password"));
    fireEvent.click(screen.getByRole("button", { name: /Team · Invite User/i }));
    await waitFor(() => expect(getAgencyEmailTemplateMock).toHaveBeenCalledWith("team_invite_user"));
    expect(await screen.findByDisplayValue("Invite subject")).toBeInTheDocument();
  });

  it("saves changes and refetches list/detail", async () => {
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
    expect(getAgencyEmailTemplatesMock).toHaveBeenCalledTimes(2);
    expect(getAgencyEmailTemplateMock).toHaveBeenCalledTimes(2);
  });

  it("resets to default and refetches list/detail", async () => {
    render(<AgencyEmailTemplatesPage />);

    await screen.findByDisplayValue("Reset subject");
    fireEvent.click(screen.getByRole("button", { name: "Reset to default" }));

    await waitFor(() => expect(resetAgencyEmailTemplateMock).toHaveBeenCalledWith("auth_forgot_password"));
    expect(await screen.findByText("Template resetat la valorile implicite.")).toBeInTheDocument();
    expect(getAgencyEmailTemplatesMock).toHaveBeenCalledTimes(2);
  });

  it("shows preview button and sends draft values to preview endpoint", async () => {
    render(<AgencyEmailTemplatesPage />);
    await screen.findByDisplayValue("Reset subject");

    fireEvent.change(screen.getByLabelText("Subject"), { target: { value: "Draft subject {{user_email}}" } });
    fireEvent.change(screen.getByLabelText("Text body"), { target: { value: "Draft text {{reset_link}}" } });
    setHtmlSourceEditor("<p>Draft html {{expires_minutes}}</p>");
    fireEvent.click(screen.getByRole("button", { name: "Preview" }));

    await waitFor(() => {
      expect(previewAgencyEmailTemplateMock).toHaveBeenCalledWith("auth_forgot_password", {
        subject: "Draft subject {{user_email}}",
        text_body: "Draft text {{reset_link}}",
        html_body: "<p>Draft html {{expires_minutes}}</p>",
      });
    });
  });

  it("renders preview panel with rendered subject/text/html", async () => {
    render(<AgencyEmailTemplatesPage />);
    await screen.findByDisplayValue("Reset subject");

    fireEvent.click(screen.getByRole("button", { name: "Preview" }));

    expect(await screen.findByLabelText("Template preview panel")).toBeInTheDocument();
    expect(screen.getByText("Rendered preview subject")).toBeInTheDocument();
    expect(screen.getByText("Rendered preview text")).toBeInTheDocument();
    expect(screen.getByText("<p>Rendered preview html</p>")).toBeInTheDocument();
    expect(screen.getByText("{{reset_link}}=https://app.example.com/reset")).toBeInTheDocument();
  });

  it("shows preview loading state", async () => {
    let resolvePreview: ((value: unknown) => void) | null = null;
    previewAgencyEmailTemplateMock.mockReturnValue(
      new Promise((resolve) => {
        resolvePreview = resolve;
      }),
    );

    render(<AgencyEmailTemplatesPage />);
    await screen.findByDisplayValue("Reset subject");
    fireEvent.click(screen.getByRole("button", { name: "Preview" }));
    expect(screen.getByRole("button", { name: "Previewing..." })).toBeInTheDocument();

    resolvePreview?.({
      key: "auth_forgot_password",
      rendered_subject: "Done",
      rendered_text_body: "Done",
      rendered_html_body: "<p>Done</p>",
      sample_variables: {},
      is_overridden: false,
    });
    expect(await screen.findByLabelText("Template preview panel")).toBeInTheDocument();
  });

  it("shows test email input and send test email button", async () => {
    render(<AgencyEmailTemplatesPage />);
    await screen.findByDisplayValue("Reset subject");

    expect(screen.getByLabelText("Test email")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Send test email" })).toBeInTheDocument();
  });

  it("loads and shows Mailgun configured/active status metadata", async () => {
    render(<AgencyEmailTemplatesPage />);

    expect(await screen.findByLabelText("Mailgun status panel")).toBeInTheDocument();
    expect(screen.getByText("Configurat:")).toBeInTheDocument();
    expect(screen.getByText("Activ:")).toBeInTheDocument();
    expect(screen.getByText("mg.example.com")).toBeInTheDocument();
    expect(screen.getByText("noreply@example.com")).toBeInTheDocument();
    expect(screen.getByText("key-***")).toBeInTheDocument();
    expect(screen.getByText("db")).toBeInTheDocument();
    expect(screen.getByText("Mailgun este configurat și activ. Poți trimite emailuri de test.")).toBeInTheDocument();
  });

  it("shows env-managed hint while keeping test-send available", async () => {
    getMailgunStatusMock.mockResolvedValueOnce({
      configured: true,
      enabled: true,
      config_source: "env",
      domain: "mg.env.example.com",
      base_url: "https://api.mailgun.net",
      from_email: "env@example.com",
      from_name: "Env",
      reply_to: "",
      api_key_masked: "key***env",
    });
    render(<AgencyEmailTemplatesPage />);

    await screen.findByLabelText("Mailgun status panel");
    expect(screen.getByText("env")).toBeInTheDocument();
    expect(screen.getByText(/managed by Railway env/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Send test email" })).toBeEnabled();
  });

  it("shows sandbox-domain hint when Mailgun domain is sandbox", async () => {
    getMailgunStatusMock.mockResolvedValueOnce({
      configured: true,
      enabled: true,
      domain: "sandbox123.mailgun.org",
      base_url: "https://api.mailgun.net",
      from_email: "noreply@example.com",
      from_name: "Example",
      reply_to: "",
      api_key_masked: "key-***",
    });

    render(<AgencyEmailTemplatesPage />);
    expect(await screen.findByText(/Domain Mailgun este de tip sandbox/)).toBeInTheDocument();
  });

  it("disables Send test email and shows integrations CTA when Mailgun is not configured", async () => {
    getMailgunStatusMock.mockResolvedValueOnce({
      configured: false,
      enabled: false,
      domain: "",
      base_url: "",
      from_email: "",
      from_name: "",
      reply_to: "",
      api_key_masked: "",
    });

    render(<AgencyEmailTemplatesPage />);
    await screen.findByDisplayValue("Reset subject");

    const sendButton = screen.getByRole("button", { name: "Send test email" });
    expect(sendButton).toBeDisabled();
    expect(screen.getByText(/Mailgun nu este disponibil pentru test-send/)).toBeInTheDocument();
    expect(screen.getAllByRole("link", { name: /Agency Integrations|Configurează Mailgun în Agency Integrations/i }).length).toBeGreaterThan(0);
  });

  it("shows safe fallback when Mailgun status fails and keeps other actions available", async () => {
    getMailgunStatusMock.mockRejectedValueOnce(new ApiRequestError("status unavailable", 503));

    render(<AgencyEmailTemplatesPage />);
    await screen.findByDisplayValue("Reset subject");

    expect(screen.getByText(/Nu am putut verifica statusul Mailgun acum/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Send test email" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Preview" })).toBeEnabled();
    expect(screen.getByRole("button", { name: "Reset to default" })).toBeEnabled();
  });

  it("send test email uses current draft values and endpoint", async () => {
    render(<AgencyEmailTemplatesPage />);
    await screen.findByDisplayValue("Reset subject");

    fireEvent.change(screen.getByLabelText("Subject"), { target: { value: "Draft subject {{user_email}}" } });
    fireEvent.change(screen.getByLabelText("Text body"), { target: { value: "Draft text {{reset_link}}" } });
    setHtmlSourceEditor("<p>Draft html {{expires_minutes}}</p>");
    fireEvent.change(screen.getByLabelText("Test email"), { target: { value: "qa@example.com" } });
    fireEvent.click(screen.getByRole("button", { name: "Send test email" }));

    await waitFor(() => {
      expect(sendAgencyEmailTemplateTestMock).toHaveBeenCalledWith("auth_forgot_password", {
        to_email: "qa@example.com",
        subject: "Draft subject {{user_email}}",
        text_body: "Draft text {{reset_link}}",
        html_body: "<p>Draft html {{expires_minutes}}</p>",
      });
    });
    expect(await screen.findByText(/Cererea a fost acceptată de Mailgun pentru qa@example.com/)).toBeInTheDocument();
    expect(screen.getByText("Delivery status:")).toBeInTheDocument();
    expect(screen.getByText("Provider message:")).toBeInTheDocument();
    expect(screen.getByText("Provider id:")).toBeInTheDocument();
    expect(screen.getByText("<mailgun-message-id>")).toBeInTheDocument();
  });

  it("shows send test loading state", async () => {
    let resolveSend: ((value: unknown) => void) | null = null;
    sendAgencyEmailTemplateTestMock.mockReturnValue(
      new Promise((resolve) => {
        resolveSend = resolve;
      }),
    );

    render(<AgencyEmailTemplatesPage />);
    await screen.findByDisplayValue("Reset subject");
    fireEvent.change(screen.getByLabelText("Test email"), { target: { value: "qa@example.com" } });
    fireEvent.click(screen.getByRole("button", { name: "Send test email" }));
    expect(screen.getByRole("button", { name: "Sending..." })).toBeInTheDocument();

    resolveSend?.({
      key: "auth_forgot_password",
      to_email: "qa@example.com",
      accepted: true,
      delivery_status: "accepted",
      rendered_subject: "Done",
      provider_message: "Queued. Thank you.",
      provider_id: "<mailgun-message-id>",
    });
    expect(await screen.findByText(/Cererea a fost acceptată de Mailgun pentru qa@example.com/)).toBeInTheDocument();
  });

  it("shows loading state for list", async () => {
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

  it("shows loading state for detail", async () => {
    let resolveDetail: ((value: unknown) => void) | null = null;
    getAgencyEmailTemplateMock.mockReturnValue(
      new Promise((resolve) => {
        resolveDetail = resolve;
      }),
    );

    render(<AgencyEmailTemplatesPage />);
    expect(await screen.findByText("Se încarcă detaliile...")).toBeInTheDocument();

    resolveDetail?.({
      key: "auth_forgot_password",
      label: "Auth · Forgot Password",
      description: "Forgot template",
      subject: "Reset subject",
      text_body: "Reset text",
      html_body: "<p>Reset html</p>",
      available_variables: ["reset_link"],
      scope: "agency",
      enabled: true,
      is_overridden: false,
      updated_at: null,
    });

    expect(await screen.findByDisplayValue("Reset subject")).toBeInTheDocument();
  });

  it("reset reloads html editor with latest detail value", async () => {
    render(<AgencyEmailTemplatesPage />);
    await screen.findByDisplayValue("Reset subject");
    setHtmlSourceEditor("<p>Changed html</p>");

    fireEvent.click(screen.getByRole("button", { name: "Reset to default" }));
    await screen.findByText("Template resetat la valorile implicite.");

    fireEvent.click(screen.getByRole("button", { name: "HTML" }));
    expect((screen.getByTestId("html-source-editor") as HTMLTextAreaElement).value).toBe("<p>Reset html</p>");
  });

  it("handles 403 list error clearly", async () => {
    getAgencyEmailTemplatesMock.mockRejectedValueOnce(new ApiRequestError("forbidden", 403));
    render(<AgencyEmailTemplatesPage />);
    expect(await screen.findByText("Nu ai permisiunea necesară pentru Email Templates.")).toBeInTheDocument();
  });

  it("handles 404 detail error clearly", async () => {
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

  it("handles 403 preview error clearly", async () => {
    previewAgencyEmailTemplateMock.mockRejectedValueOnce(new ApiRequestError("forbidden", 403));

    render(<AgencyEmailTemplatesPage />);
    await screen.findByDisplayValue("Reset subject");
    fireEvent.click(screen.getByRole("button", { name: "Preview" }));
    expect(await screen.findByText("Nu ai permisiunea necesară pentru Email Templates.")).toBeInTheDocument();
  });

  it("handles 404 preview error clearly", async () => {
    previewAgencyEmailTemplateMock.mockRejectedValueOnce(new ApiRequestError("missing", 404));

    render(<AgencyEmailTemplatesPage />);
    await screen.findByDisplayValue("Reset subject");
    fireEvent.click(screen.getByRole("button", { name: "Preview" }));
    expect(await screen.findByText("Template-ul selectat nu a fost găsit.")).toBeInTheDocument();
  });

  it("handles 400 preview error clearly", async () => {
    previewAgencyEmailTemplateMock.mockRejectedValueOnce(new ApiRequestError("payload invalid", 400));

    render(<AgencyEmailTemplatesPage />);
    await screen.findByDisplayValue("Reset subject");
    fireEvent.click(screen.getByRole("button", { name: "Preview" }));
    expect(await screen.findByText("payload invalid")).toBeInTheDocument();
  });

  it("handles 403 send test error clearly", async () => {
    sendAgencyEmailTemplateTestMock.mockRejectedValueOnce(new ApiRequestError("forbidden", 403));

    render(<AgencyEmailTemplatesPage />);
    await screen.findByDisplayValue("Reset subject");
    fireEvent.change(screen.getByLabelText("Test email"), { target: { value: "qa@example.com" } });
    fireEvent.click(screen.getByRole("button", { name: "Send test email" }));
    expect(await screen.findByText("Nu ai permisiunea necesară pentru Email Templates.")).toBeInTheDocument();
  });

  it("handles 404 send test error clearly", async () => {
    sendAgencyEmailTemplateTestMock.mockRejectedValueOnce(new ApiRequestError("missing", 404));

    render(<AgencyEmailTemplatesPage />);
    await screen.findByDisplayValue("Reset subject");
    fireEvent.change(screen.getByLabelText("Test email"), { target: { value: "qa@example.com" } });
    fireEvent.click(screen.getByRole("button", { name: "Send test email" }));
    expect(await screen.findByText("Template-ul selectat nu a fost găsit.")).toBeInTheDocument();
  });

  it("handles 400 send test error clearly", async () => {
    sendAgencyEmailTemplateTestMock.mockRejectedValueOnce(new ApiRequestError("to_email invalid", 400));

    render(<AgencyEmailTemplatesPage />);
    await screen.findByDisplayValue("Reset subject");
    fireEvent.change(screen.getByLabelText("Test email"), { target: { value: "invalid" } });
    fireEvent.click(screen.getByRole("button", { name: "Send test email" }));
    expect(await screen.findByText("to_email invalid")).toBeInTheDocument();
  });

  it("handles 503 send test error clearly", async () => {
    sendAgencyEmailTemplateTestMock.mockRejectedValueOnce(new ApiRequestError("Mailgun nu este configurat", 503));

    render(<AgencyEmailTemplatesPage />);
    await screen.findByDisplayValue("Reset subject");
    fireEvent.change(screen.getByLabelText("Test email"), { target: { value: "qa@example.com" } });
    fireEvent.click(screen.getByRole("button", { name: "Send test email" }));
    expect(await screen.findByText("Mailgun nu este configurat")).toBeInTheDocument();
  });
});
