"use client";

import React, { useEffect, useMemo, useState } from "react";

import {
  ApiRequestError,
  MailgunConfigPayload,
  MailgunStatusResponse,
  MailgunTestPayload,
  getMailgunStatus,
  saveMailgunConfig,
  sendMailgunTestEmail,
} from "@/lib/api";

type MailgunConfigForm = {
  api_key: string;
  domain: string;
  base_url: string;
  from_email: string;
  from_name: string;
  reply_to: string;
  enabled: boolean;
};

type MailgunTestForm = {
  to_email: string;
  subject: string;
  text: string;
};

function statusBadge(status: MailgunStatusResponse | null): { label: string; toneClass: string } {
  if (!status || !status.configured) return { label: "Neconfigurat", toneClass: "bg-amber-100 text-amber-700" };
  if (status.enabled) return { label: "Configurat activ", toneClass: "bg-emerald-100 text-emerald-700" };
  return { label: "Configurat, dezactivat", toneClass: "bg-slate-100 text-slate-700" };
}

function normalizeError(error: unknown, fallback: string): string {
  if (error instanceof ApiRequestError) {
    if (error.status === 403) return "Nu ai acces la această integrare.";
    if (error.status === 404) return "Config Mailgun inexistent.";
    if (error.status === 400) return error.message || fallback;
  }
  if (error instanceof Error && error.message.trim()) return error.message;
  return fallback;
}

function configFromStatus(status: MailgunStatusResponse | null): MailgunConfigForm {
  return {
    api_key: "",
    domain: status?.domain ?? "",
    base_url: status?.base_url ?? "https://api.mailgun.net",
    from_email: status?.from_email ?? "",
    from_name: status?.from_name ?? "",
    reply_to: status?.reply_to ?? "",
    enabled: status?.configured ? Boolean(status.enabled) : true,
  };
}

export function MailgunIntegrationCard() {
  const [status, setStatus] = useState<MailgunStatusResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [statusError, setStatusError] = useState("");

  const [configOpen, setConfigOpen] = useState(false);
  const [configForm, setConfigForm] = useState<MailgunConfigForm>(configFromStatus(null));
  const [configErrors, setConfigErrors] = useState<Record<string, string>>({});
  const [configBusy, setConfigBusy] = useState(false);
  const [configMessage, setConfigMessage] = useState("");

  const [testForm, setTestForm] = useState<MailgunTestForm>({ to_email: "", subject: "", text: "" });
  const [testError, setTestError] = useState("");
  const [testMessage, setTestMessage] = useState("");
  const [testBusy, setTestBusy] = useState(false);

  const badge = useMemo(() => statusBadge(status), [status]);
  const isEnvManaged = status?.config_source === "env";

  async function loadStatus() {
    setLoading(true);
    setStatusError("");
    try {
      const payload = await getMailgunStatus();
      setStatus(payload);
      setConfigForm(configFromStatus(payload));
    } catch (err) {
      setStatus(null);
      setStatusError(normalizeError(err, "Nu am putut încărca statusul Mailgun."));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadStatus();
  }, []);

  function validateConfig(): Record<string, string> {
    const next: Record<string, string> = {};
    if (!configForm.api_key.trim()) next.api_key = "API key este obligatoriu.";
    if (!configForm.domain.trim()) next.domain = "Domain este obligatoriu.";
    if (!configForm.base_url.trim()) next.base_url = "Base URL este obligatoriu.";
    if (!configForm.from_email.trim()) next.from_email = "From email este obligatoriu.";
    if (!configForm.from_name.trim()) next.from_name = "From name este obligatoriu.";
    return next;
  }

  async function onSaveConfig() {
    const nextErrors = validateConfig();
    setConfigErrors(nextErrors);
    if (Object.keys(nextErrors).length > 0) return;

    setConfigBusy(true);
    setConfigMessage("");
    setTestError("");
    try {
      const payload: MailgunConfigPayload = {
        api_key: configForm.api_key.trim(),
        domain: configForm.domain.trim(),
        base_url: configForm.base_url.trim(),
        from_email: configForm.from_email.trim(),
        from_name: configForm.from_name.trim(),
        reply_to: configForm.reply_to.trim(),
        enabled: configForm.enabled,
      };
      await saveMailgunConfig(payload);
      setConfigMessage("Configurația Mailgun a fost salvată.");
      setConfigOpen(false);
      await loadStatus();
      setConfigForm((prev) => ({ ...prev, api_key: "" }));
    } catch (err) {
      setConfigMessage(normalizeError(err, "Nu am putut salva configurația Mailgun."));
    } finally {
      setConfigBusy(false);
    }
  }

  async function onTestSend() {
    if (!testForm.to_email.trim()) {
      setTestError("Email destinatar este obligatoriu.");
      return;
    }
    setTestBusy(true);
    setTestError("");
    setTestMessage("");
    try {
      const payload: MailgunTestPayload = {
        to_email: testForm.to_email.trim(),
      };
      if (testForm.subject.trim()) payload.subject = testForm.subject.trim();
      if (testForm.text.trim()) payload.text = testForm.text.trim();

      await sendMailgunTestEmail(payload);
      setTestMessage("Emailul de test a fost trimis cu succes.");
    } catch (err) {
      setTestError(normalizeError(err, "Nu am putut trimite emailul de test."));
    } finally {
      setTestBusy(false);
    }
  }

  return (
    <article className="wm-card p-4" data-testid="mailgun-card">
      <div className="flex items-center justify-between">
        <h2 className="text-base font-semibold text-slate-900">Mailgun</h2>
        <span className={`rounded-full px-3 py-1 text-xs font-medium ${badge.toneClass}`}>{badge.label}</span>
      </div>

      {loading ? <p className="mt-2 text-sm text-slate-600">Se încarcă statusul Mailgun...</p> : null}

      {statusError ? (
        <div className="mt-3 rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">
          <p>{statusError}</p>
          <button className="mt-2 rounded border border-red-300 px-2 py-1 text-xs" onClick={() => void loadStatus()}>
            Reîncearcă
          </button>
        </div>
      ) : null}

      {!loading && !statusError ? (
        <div className="mt-3 space-y-1 text-xs text-slate-600">
          <p>Configured: {String(Boolean(status?.configured))}</p>
          <p>Enabled: {String(Boolean(status?.enabled))}</p>
          <p>Config source: {status?.config_source || "none"}</p>
          <p>Domain: {status?.domain || "-"}</p>
          <p>Base URL: {status?.base_url || "-"}</p>
          <p>From email: {status?.from_email || "-"}</p>
          <p>From name: {status?.from_name || "-"}</p>
          <p>Reply-To: {status?.reply_to || "-"}</p>
          <p>API key: {status?.api_key_masked || "-"}</p>
          {!status?.configured ? <p className="pt-1 text-amber-700">Mailgun nu este configurat. Completează formularul de mai jos.</p> : null}
          {status?.configured && status?.config_source === "env" ? (
            <p className="pt-1 text-amber-700">Managed by Railway env. Configurarea manuală din UI este read-only.</p>
          ) : null}
        </div>
      ) : null}

      <div className="mt-4 flex flex-wrap gap-2">
        <button
          onClick={() => {
            if (isEnvManaged) return;
            setConfigOpen((prev) => !prev);
            setConfigErrors({});
            setConfigMessage("");
          }}
          className="wm-btn-primary"
          disabled={loading || configBusy || isEnvManaged}
        >
          {isEnvManaged ? "Configured in Railway" : configOpen ? "Închide configurare" : status?.configured ? "Editează configurare" : "Configurează Mailgun"}
        </button>
      </div>

      {configOpen && !isEnvManaged ? (
        <div className="mt-4 space-y-3 rounded-md border border-slate-200 p-3">
          <p className="text-xs text-slate-500">Din motive de securitate, API key trebuie reintrodus la salvare.</p>
          <label className="block text-xs text-slate-700">
            API key *
            <input className="wm-input mt-1" type="password" value={configForm.api_key} onChange={(e) => setConfigForm((prev) => ({ ...prev, api_key: e.target.value }))} />
            {configErrors.api_key ? <span className="text-red-600">{configErrors.api_key}</span> : null}
          </label>

          <label className="block text-xs text-slate-700">
            Domain *
            <input className="wm-input mt-1" value={configForm.domain} onChange={(e) => setConfigForm((prev) => ({ ...prev, domain: e.target.value }))} />
            {configErrors.domain ? <span className="text-red-600">{configErrors.domain}</span> : null}
          </label>

          <label className="block text-xs text-slate-700">
            Base URL *
            <input className="wm-input mt-1" value={configForm.base_url} onChange={(e) => setConfigForm((prev) => ({ ...prev, base_url: e.target.value }))} />
            {configErrors.base_url ? <span className="text-red-600">{configErrors.base_url}</span> : null}
          </label>

          <label className="block text-xs text-slate-700">
            From email *
            <input className="wm-input mt-1" value={configForm.from_email} onChange={(e) => setConfigForm((prev) => ({ ...prev, from_email: e.target.value }))} />
            {configErrors.from_email ? <span className="text-red-600">{configErrors.from_email}</span> : null}
          </label>

          <label className="block text-xs text-slate-700">
            From name *
            <input className="wm-input mt-1" value={configForm.from_name} onChange={(e) => setConfigForm((prev) => ({ ...prev, from_name: e.target.value }))} />
            {configErrors.from_name ? <span className="text-red-600">{configErrors.from_name}</span> : null}
          </label>

          <label className="block text-xs text-slate-700">
            Reply-To
            <input className="wm-input mt-1" value={configForm.reply_to} onChange={(e) => setConfigForm((prev) => ({ ...prev, reply_to: e.target.value }))} />
          </label>

          <label className="inline-flex items-center gap-2 text-xs text-slate-700">
            <input type="checkbox" checked={configForm.enabled} onChange={(e) => setConfigForm((prev) => ({ ...prev, enabled: e.target.checked }))} />
            Enabled
          </label>

          {configMessage ? <p className="text-xs text-slate-700">{configMessage}</p> : null}

          <button className="wm-btn-primary" onClick={() => void onSaveConfig()} disabled={configBusy}>
            {configBusy ? "Se salvează..." : "Salvează configurarea"}
          </button>
        </div>
      ) : null}

      <div className="mt-4 space-y-2 rounded-md border border-slate-200 p-3">
        <p className="text-sm font-medium text-slate-800">Test Email</p>
        <label className="block text-xs text-slate-700">
          To email *
          <input className="wm-input mt-1" value={testForm.to_email} onChange={(e) => setTestForm((prev) => ({ ...prev, to_email: e.target.value }))} />
        </label>
        <label className="block text-xs text-slate-700">
          Subject
          <input className="wm-input mt-1" value={testForm.subject} onChange={(e) => setTestForm((prev) => ({ ...prev, subject: e.target.value }))} />
        </label>
        <label className="block text-xs text-slate-700">
          Text
          <textarea className="wm-input mt-1" value={testForm.text} onChange={(e) => setTestForm((prev) => ({ ...prev, text: e.target.value }))} rows={3} />
        </label>

        {testError ? <p className="text-xs text-red-600">{testError}</p> : null}
        {testMessage ? <p className="text-xs text-emerald-600">{testMessage}</p> : null}

        <button className="wm-btn-primary" onClick={() => void onTestSend()} disabled={testBusy || loading}>
          {testBusy ? "Se trimite..." : "Test Email"}
        </button>
      </div>
    </article>
  );
}
