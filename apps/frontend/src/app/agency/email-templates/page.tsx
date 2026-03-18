"use client";

import React, { useEffect, useMemo, useState } from "react";

import { AppShell } from "@/components/AppShell";
import { ProtectedPage } from "@/components/ProtectedPage";
import {
  ApiRequestError,
  type AgencyEmailTemplateDetail,
  type AgencyEmailTemplateListItem,
  getAgencyEmailTemplate,
  getAgencyEmailTemplates,
  resetAgencyEmailTemplate,
  saveAgencyEmailTemplate,
} from "@/lib/api";

type TemplateEditorState = {
  subject: string;
  text_body: string;
  html_body: string;
  enabled: boolean;
};

function formatDate(value: string | null | undefined): string {
  if (!value) return "Never updated";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleString();
}

function resolveErrorMessage(error: unknown, fallback: string): string {
  if (error instanceof ApiRequestError) {
    if (error.status === 403) return "Nu ai permisiunea necesară pentru Email Templates.";
    if (error.status === 404) return "Template-ul selectat nu a fost găsit.";
    if (error.status === 400) return error.message || "Date invalide pentru salvare.";
    return error.message || fallback;
  }
  if (error instanceof Error) return error.message || fallback;
  return fallback;
}

function StatusBadge({ enabled }: { enabled: boolean }) {
  return (
    <span
      className={`rounded-full px-2 py-0.5 text-xs font-medium ${
        enabled ? "bg-emerald-100 text-emerald-700" : "bg-rose-100 text-rose-700"
      }`}
    >
      {enabled ? "Enabled" : "Disabled"}
    </span>
  );
}

function OverrideBadge({ overridden }: { overridden: boolean }) {
  return (
    <span
      className={`rounded-full px-2 py-0.5 text-xs font-medium ${
        overridden ? "bg-sky-100 text-sky-700" : "bg-slate-100 text-slate-700"
      }`}
    >
      {overridden ? "Overridden" : "Default"}
    </span>
  );
}

export default function AgencyEmailTemplatesPage() {
  const [items, setItems] = useState<AgencyEmailTemplateListItem[]>([]);
  const [listLoading, setListLoading] = useState(true);
  const [listError, setListError] = useState("");

  const [selectedKey, setSelectedKey] = useState<string | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState("");
  const [detail, setDetail] = useState<AgencyEmailTemplateDetail | null>(null);

  const [editor, setEditor] = useState<TemplateEditorState | null>(null);
  const [saveLoading, setSaveLoading] = useState(false);
  const [resetLoading, setResetLoading] = useState(false);
  const [feedback, setFeedback] = useState("");

  async function loadList(preferredKey?: string | null) {
    setListLoading(true);
    setListError("");
    try {
      const payload = await getAgencyEmailTemplates();
      const nextItems = payload.items || [];
      setItems(nextItems);
      if (nextItems.length === 0) {
        setSelectedKey(null);
      } else if (preferredKey && nextItems.some((item) => item.key === preferredKey)) {
        setSelectedKey(preferredKey);
      } else {
        setSelectedKey((current) => {
          if (current && nextItems.some((item) => item.key === current)) return current;
          return nextItems[0].key;
        });
      }
    } catch (error) {
      setItems([]);
      setSelectedKey(null);
      setListError(resolveErrorMessage(error, "Nu am putut încărca lista de template-uri."));
    } finally {
      setListLoading(false);
    }
  }

  async function loadDetail(templateKey: string) {
    setDetailLoading(true);
    setDetailError("");
    try {
      const payload = await getAgencyEmailTemplate(templateKey);
      setDetail(payload);
      setEditor({
        subject: payload.subject || "",
        text_body: payload.text_body || "",
        html_body: payload.html_body || "",
        enabled: Boolean(payload.enabled),
      });
    } catch (error) {
      setDetail(null);
      setEditor(null);
      setDetailError(resolveErrorMessage(error, "Nu am putut încărca detaliile template-ului."));
    } finally {
      setDetailLoading(false);
    }
  }

  useEffect(() => {
    void loadList();
  }, []);

  useEffect(() => {
    if (!selectedKey) {
      setDetail(null);
      setEditor(null);
      setDetailError("");
      return;
    }
    setFeedback("");
    void loadDetail(selectedKey);
  }, [selectedKey]);

  const hasChanges = useMemo(() => {
    if (!detail || !editor) return false;
    return (
      editor.subject !== (detail.subject || "") ||
      editor.text_body !== (detail.text_body || "") ||
      editor.html_body !== (detail.html_body || "") ||
      editor.enabled !== Boolean(detail.enabled)
    );
  }, [detail, editor]);

  async function handleSave() {
    if (!selectedKey || !editor) return;
    setFeedback("");
    setSaveLoading(true);
    try {
      await saveAgencyEmailTemplate(selectedKey, {
        subject: editor.subject,
        text_body: editor.text_body,
        html_body: editor.html_body,
        enabled: editor.enabled,
      });
      await Promise.all([loadDetail(selectedKey), loadList(selectedKey)]);
      setFeedback("Template salvat cu succes.");
    } catch (error) {
      setFeedback(resolveErrorMessage(error, "Nu am putut salva template-ul."));
    } finally {
      setSaveLoading(false);
    }
  }

  async function handleReset() {
    if (!selectedKey) return;
    const confirmed = window.confirm("Sigur dorești resetarea la valorile implicite?");
    if (!confirmed) return;

    setFeedback("");
    setResetLoading(true);
    try {
      await resetAgencyEmailTemplate(selectedKey);
      await Promise.all([loadDetail(selectedKey), loadList(selectedKey)]);
      setFeedback("Template resetat la valorile implicite.");
    } catch (error) {
      setFeedback(resolveErrorMessage(error, "Nu am putut reseta template-ul."));
    } finally {
      setResetLoading(false);
    }
  }

  const positiveFeedback = feedback.includes("succes") || feedback.includes("resetat");

  return (
    <ProtectedPage>
      <AppShell title="Email Templates & Notifications">
        <div className="space-y-4">
          <section className="wm-card p-4">
            <h1 className="text-lg font-semibold text-slate-900">Email Templates & Notifications</h1>
            <p className="mt-1 text-sm text-slate-600">
              Configurează template-urile email active pentru fluxurile existente (forgot password, invite user)
              folosind contractul actual din backend.
            </p>
          </section>

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
            <section className="wm-card p-4 lg:col-span-1" aria-label="Template overview list">
              <div className="mb-3">
                <h2 className="text-base font-semibold text-slate-900">Notification templates</h2>
                <p className="mt-1 text-sm text-slate-600">Selectează un item pentru detalii și editare.</p>
              </div>

              {listLoading ? <p className="text-sm text-slate-500">Se încarcă lista...</p> : null}
              {!listLoading && listError ? <p className="text-sm text-red-600">{listError}</p> : null}
              {!listLoading && !listError && items.length === 0 ? <p className="text-sm text-slate-500">Nu există template-uri disponibile.</p> : null}

              <ul className="space-y-2">
                {items.map((item) => {
                  const isActive = item.key === selectedKey;
                  return (
                    <li key={item.key}>
                      <button
                        type="button"
                        className={`w-full rounded-lg border p-3 text-left transition ${
                          isActive ? "border-sky-500 bg-sky-50" : "border-slate-200 bg-white hover:border-slate-300"
                        }`}
                        onClick={() => setSelectedKey(item.key)}
                      >
                        <div className="flex items-start justify-between gap-2">
                          <div>
                            <p className="text-sm font-semibold text-slate-900">{item.label}</p>
                            <p className="mt-1 text-xs text-slate-600">{item.description}</p>
                          </div>
                          <StatusBadge enabled={item.enabled} />
                        </div>
                        <div className="mt-3 flex flex-wrap items-center gap-2">
                          <OverrideBadge overridden={item.is_overridden} />
                          <span className="text-xs text-slate-500">Updated: {formatDate(item.updated_at)}</span>
                        </div>
                      </button>
                    </li>
                  );
                })}
              </ul>
            </section>

            <section className="wm-card p-4 lg:col-span-2" aria-label="Template detail editor">
              {!selectedKey ? <p className="text-sm text-slate-500">Selectează un template din listă pentru a vedea detaliile.</p> : null}
              {selectedKey && detailLoading ? <p className="text-sm text-slate-500">Se încarcă detaliile...</p> : null}
              {selectedKey && !detailLoading && detailError ? <p className="text-sm text-red-600">{detailError}</p> : null}

              {selectedKey && !detailLoading && !detailError && detail && editor ? (
                <div className="space-y-5">
                  <div className="border-b border-slate-200 pb-4">
                    <div className="flex flex-wrap items-center gap-2">
                      <h2 className="text-base font-semibold text-slate-900">{detail.label}</h2>
                      <StatusBadge enabled={editor.enabled} />
                      <OverrideBadge overridden={detail.is_overridden} />
                    </div>
                    <p className="mt-1 text-sm text-slate-600">{detail.description}</p>
                    <p className="mt-2 text-xs text-slate-500">Updated: {formatDate(detail.updated_at)}</p>
                  </div>

                  <div className="grid grid-cols-1 gap-3 rounded-lg border border-slate-200 bg-slate-50 p-3 text-xs text-slate-600 md:grid-cols-2">
                    <p>
                      <span className="font-semibold text-slate-700">Scope:</span> {detail.scope}
                    </p>
                    <p>
                      <span className="font-semibold text-slate-700">Template key:</span> {detail.key}
                    </p>
                  </div>

                  <div>
                    <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Available variables</p>
                    <div className="mt-2 flex flex-wrap gap-2">
                      {detail.available_variables.length > 0 ? (
                        detail.available_variables.map((variable) => (
                          <code key={variable} className="rounded-full bg-slate-100 px-2 py-1 text-xs text-slate-700">
                            {`{{${variable}}}`}
                          </code>
                        ))
                      ) : (
                        <span className="text-xs text-slate-500">No variables exposed for this template.</span>
                      )}
                    </div>
                  </div>

                  <div className="space-y-4 rounded-lg border border-slate-200 p-4">
                    <h3 className="text-sm font-semibold text-slate-900">Template content</h3>

                    <label className="block">
                      <span className="mb-1 block text-sm font-medium text-slate-700">Subject</span>
                      <input
                        className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
                        value={editor.subject}
                        onChange={(event) => setEditor((prev) => (prev ? { ...prev, subject: event.target.value } : prev))}
                      />
                    </label>

                    <label className="block">
                      <span className="mb-1 block text-sm font-medium text-slate-700">Text body</span>
                      <textarea
                        className="min-h-[140px] w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
                        value={editor.text_body}
                        onChange={(event) => setEditor((prev) => (prev ? { ...prev, text_body: event.target.value } : prev))}
                      />
                    </label>

                    <label className="block">
                      <span className="mb-1 block text-sm font-medium text-slate-700">HTML body</span>
                      <textarea
                        className="min-h-[140px] w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
                        value={editor.html_body}
                        onChange={(event) => setEditor((prev) => (prev ? { ...prev, html_body: event.target.value } : prev))}
                      />
                    </label>

                    <label className="inline-flex items-center gap-2 text-sm text-slate-700">
                      <input
                        type="checkbox"
                        checked={editor.enabled}
                        onChange={(event) => setEditor((prev) => (prev ? { ...prev, enabled: event.target.checked } : prev))}
                      />
                      Enabled
                    </label>
                  </div>

                  <div className="flex flex-wrap items-center gap-2">
                    <button
                      type="button"
                      className="rounded-lg bg-sky-600 px-4 py-2 text-sm font-medium text-white disabled:cursor-not-allowed disabled:opacity-60"
                      onClick={handleSave}
                      disabled={saveLoading || resetLoading || !hasChanges}
                    >
                      {saveLoading ? "Saving..." : "Save changes"}
                    </button>
                    <button
                      type="button"
                      className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 disabled:cursor-not-allowed disabled:opacity-60"
                      onClick={handleReset}
                      disabled={saveLoading || resetLoading}
                    >
                      {resetLoading ? "Resetting..." : "Reset to default"}
                    </button>
                  </div>

                  {feedback ? <p className={`text-sm ${positiveFeedback ? "text-emerald-600" : "text-red-600"}`}>{feedback}</p> : null}
                </div>
              ) : null}
            </section>
          </div>
        </div>
      </AppShell>
    </ProtectedPage>
  );
}
