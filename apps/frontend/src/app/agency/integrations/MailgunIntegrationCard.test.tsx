import React from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import { MailgunIntegrationCard } from "./MailgunIntegrationCard";

const apiMock = vi.hoisted(() => ({
  getMailgunStatus: vi.fn(),
  saveMailgunConfig: vi.fn(),
  sendMailgunTestEmail: vi.fn(),
  importMailgunConfigFromEnv: vi.fn(),
}));

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    getMailgunStatus: (...args: unknown[]) => apiMock.getMailgunStatus(...args),
    saveMailgunConfig: (...args: unknown[]) => apiMock.saveMailgunConfig(...args),
    sendMailgunTestEmail: (...args: unknown[]) => apiMock.sendMailgunTestEmail(...args),
    importMailgunConfigFromEnv: (...args: unknown[]) => apiMock.importMailgunConfigFromEnv(...args),
  };
});

describe("MailgunIntegrationCard", () => {
  beforeEach(() => {
    apiMock.getMailgunStatus.mockReset();
    apiMock.saveMailgunConfig.mockReset();
    apiMock.sendMailgunTestEmail.mockReset();
    apiMock.importMailgunConfigFromEnv.mockReset();
  });

  it("loads status and renders configured data with masked api key only", async () => {
    apiMock.getMailgunStatus.mockResolvedValueOnce({
      configured: true,
      enabled: true,
      config_source: "db",
      domain: "mg.example.com",
      base_url: "https://api.mailgun.net",
      from_email: "noreply@example.com",
      from_name: "Agency",
      reply_to: "help@example.com",
      api_key_masked: "key***ret",
    });

    render(<MailgunIntegrationCard />);

    expect(await screen.findByText("Domain: mg.example.com")).toBeInTheDocument();
    expect(screen.getByText("API key: key***ret")).toBeInTheDocument();
    expect(screen.queryByText("key-super-secret")).not.toBeInTheDocument();
  });

  it("renders unconfigured state", async () => {
    apiMock.getMailgunStatus.mockResolvedValueOnce({
      configured: false,
      enabled: false,
      config_source: "none",
      domain: "",
      base_url: "",
      from_email: "",
      from_name: "",
      reply_to: "",
      api_key_masked: "",
    });

    render(<MailgunIntegrationCard />);

    expect(await screen.findByText(/Mailgun nu este configurat/i)).toBeInTheDocument();
  });

  it("saves config and refetches status", async () => {
    apiMock.getMailgunStatus
      .mockResolvedValueOnce({
        configured: false,
        enabled: false,
        config_source: "none",
        domain: "",
        base_url: "",
        from_email: "",
        from_name: "",
        reply_to: "",
        api_key_masked: "",
      })
      .mockResolvedValueOnce({
        configured: true,
        enabled: true,
        config_source: "db",
        domain: "mg.example.com",
        base_url: "https://api.mailgun.net",
        from_email: "noreply@example.com",
        from_name: "Agency",
        reply_to: "",
        api_key_masked: "key***ret",
      });
    apiMock.saveMailgunConfig.mockResolvedValue({ configured: true });

    render(<MailgunIntegrationCard />);
    await screen.findByText(/Mailgun nu este configurat/i);

    fireEvent.click(screen.getByRole("button", { name: /Configurează Mailgun/i }));
    fireEvent.change(screen.getByLabelText(/API key/i), { target: { value: "key-super-secret" } });
    fireEvent.change(screen.getByLabelText(/^Domain/i), { target: { value: "mg.example.com" } });
    fireEvent.change(screen.getByLabelText(/Base URL/i), { target: { value: "https://api.mailgun.net" } });
    fireEvent.change(screen.getByLabelText(/From email/i), { target: { value: "noreply@example.com" } });
    fireEvent.change(screen.getByLabelText(/From name/i), { target: { value: "Agency" } });
    fireEvent.click(screen.getByRole("button", { name: /Salvează configurarea/i }));

    await waitFor(() => {
      expect(apiMock.saveMailgunConfig).toHaveBeenCalledWith({
        api_key: "key-super-secret",
        domain: "mg.example.com",
        base_url: "https://api.mailgun.net",
        from_email: "noreply@example.com",
        from_name: "Agency",
        reply_to: "",
        enabled: true,
      });
    });

    await waitFor(() => expect(apiMock.getMailgunStatus).toHaveBeenCalledTimes(2));
  });

  it("sends test email request", async () => {
    apiMock.getMailgunStatus.mockResolvedValueOnce({
      configured: true,
      enabled: true,
      config_source: "db",
      domain: "mg.example.com",
      base_url: "https://api.mailgun.net",
      from_email: "noreply@example.com",
      from_name: "Agency",
      reply_to: "",
      api_key_masked: "key***ret",
    });
    apiMock.sendMailgunTestEmail.mockResolvedValue({ ok: true });

    render(<MailgunIntegrationCard />);
    await screen.findByText("Domain: mg.example.com");

    fireEvent.change(screen.getByLabelText(/To email/i), { target: { value: "test@example.com" } });
    fireEvent.change(screen.getByLabelText(/Subject/i), { target: { value: "hello" } });
    fireEvent.click(screen.getByRole("button", { name: "Test Email" }));

    await waitFor(() => {
      expect(apiMock.sendMailgunTestEmail).toHaveBeenCalledWith({
        to_email: "test@example.com",
        subject: "hello",
      });
    });
  });

  it("shows clear 403 status error", async () => {
    const { ApiRequestError } = await import("@/lib/api");
    apiMock.getMailgunStatus.mockRejectedValueOnce(new ApiRequestError("forbidden", 403));

    render(<MailgunIntegrationCard />);

    expect(await screen.findByText("Nu ai acces la această integrare.")).toBeInTheDocument();
  });

  it("shows env source and supports import-from-env action", async () => {
    apiMock.getMailgunStatus
      .mockResolvedValueOnce({
        configured: true,
        enabled: true,
        config_source: "env",
        domain: "mg.env.example.com",
        base_url: "https://api.mailgun.net",
        from_email: "env@example.com",
        from_name: "Env Sender",
        reply_to: "",
        api_key_masked: "key***env",
      })
      .mockResolvedValueOnce({
        configured: true,
        enabled: true,
        config_source: "db",
        domain: "mg.env.example.com",
        base_url: "https://api.mailgun.net",
        from_email: "env@example.com",
        from_name: "Env Sender",
        reply_to: "",
        api_key_masked: "key***env",
      });
    apiMock.importMailgunConfigFromEnv.mockResolvedValue({
      imported: true,
      message: "Configurația Mailgun a fost importată din env în DB.",
      configured: true,
      enabled: true,
      config_source: "db",
      domain: "mg.env.example.com",
      base_url: "https://api.mailgun.net",
      from_email: "env@example.com",
      from_name: "Env Sender",
      reply_to: "",
      api_key_masked: "key***env",
    });

    render(<MailgunIntegrationCard />);
    expect(await screen.findByText("Config source: env")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Importă din env în DB" }));

    await waitFor(() => expect(apiMock.importMailgunConfigFromEnv).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(apiMock.getMailgunStatus).toHaveBeenCalledTimes(2));
  });
});
