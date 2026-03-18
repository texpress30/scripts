"use client";

import Link from "next/link";
import React, { useEffect, useMemo, useState } from "react";

import { AppShell } from "@/components/AppShell";
import { ProtectedPage } from "@/components/ProtectedPage";
import {
  ApiRequestError,
  type AgencyEmailNotificationDetail,
  type AgencyEmailNotificationListItem,
  getAgencyEmailNotification,
  getAgencyEmailNotifications,
  resetAgencyEmailNotification,
  saveAgencyEmailNotification,
} from "@/lib/api";

function formatDate(value: string | null | undefined): string {
  if (!value) return "Never updated";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleString();
}

function resolveErrorMessage(error: unknown, fallback: string): string {
  if (error instanceof ApiRequestError) {
    if (error.status === 403) return "Nu ai permisiunea necesară pentru Notifications.";
    if (error.status === 404) return "Notificarea selectată nu a fost găsită.";
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

function runtimeHintForNotification(key: string): string | null {
  if (key === "auth_forgot_password") {
    return "Dacă este dezactivată, endpointul forgot-password rămâne anti-enumeration safe, dar nu se mai trimite email.";
  }
  if (key === "team_invite_user") {
    return "Dacă este dezactivată, invitațiile din Team sunt blocate până la reactivare.";
  }
  return null;
}

export default function AgencyNotificationsPage() {
  const [items, setItems] = useState<AgencyEmailNotificationListItem[]>([]);
  const [listLoading, setListLoading] = useState(true);
  const [listError, setListError] = useState("");

  const [selectedKey, setSelectedKey] = useState<string | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState("");
  const [detail, setDetail] = useState<AgencyEmailNotificationDetail | null>(null);

  const [enabledDraft, setEnabledDraft] = useState<boolean>(true);
  const [saveLoading, setSaveLoading] = useState(false);
  const [resetLoading, setResetLoading] = useState(false);
  const [feedback, setFeedback] = useState("");

  async function loadList(preferredKey?: string | null) {
    setListLoading(true);
    setListError("");
    try {
      const payload = await getAgencyEmailNotifications();
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
      setListError(resolveErrorMessage(error, "Nu am putut încărca lista de notifications."));
    } finally {
      setListLoading(false);
    }
  }

  async function loadDetail(notificationKey: string) {
    setDetailLoading(true);
    setDetailError("");
    try {
      const payload = await getAgencyEmailNotification(notificationKey);
      setDetail(payload);
      setEnabledDraft(Boolean(payload.enabled));
    } catch (error) {
      setDetail(null);
      setDetailError(resolveErrorMessage(error, "Nu am putut încărca detaliile notificării."));
    } finally {
      setDetailLoading(false);
    }
  }

  useEffect(() => {
    void loadList();
  }, []);

  useEffect(() => {
    if (!selectedKey) return;
    void loadDetail(selectedKey);
  }, [selectedKey]);

  const hasChanges = useMemo(() => {
    if (!detail) return false;
    return Boolean(detail.enabled) !== enabledDraft;
  }, [detail, enabledDraft]);

  async function handleSave() {
    if (!selectedKey || !detail) return;
    setFeedback("");
    setSaveLoading(true);
    try {
      await saveAgencyEmailNotification(selectedKey, { enabled: enabledDraft });
      await Promise.all([loadList(selectedKey), loadDetail(selectedKey)]);
      setFeedback("Notification salvată cu succes.");
    } catch (error) {
      setFeedback(resolveErrorMessage(error, "Nu am putut salva notificarea."));
    } finally {
      setSaveLoading(false);
    }
  }

  async function handleReset() {
    if (!selectedKey) return;
    const confirmed = typeof window === "undefined" ? true : window.confirm("Resetezi notificarea la valorile implicite?");
    if (!confirmed) return;
    setFeedback("");
    setResetLoading(true);
    try {
      await resetAgencyEmailNotification(selectedKey);
      await Promise.all([loadList(selectedKey), loadDetail(selectedKey)]);
      setFeedback("Notification resetată la valorile implicite.");
    } catch (error) {
      setFeedback(resolveErrorMessage(error, "Nu am putut reseta notificarea."));
    } finally {
      setResetLoading(false);
    }
  }

  const selectedHint = detail ? runtimeHintForNotification(detail.key) : null;

  return (
    <ProtectedPage>
      <AppShell title="Notifications">
        <div className="space-y-4">
          <section className="wm-card p-4">
            <h1 className="text-lg font-semibold text-slate-900">Agency Notifications</h1>
            <p className="mt-1 text-sm text-slate-600">
              Configurează starea de trimitere pentru notificările email runtime. Conținutul emailurilor rămâne gestionat separat în Email Templates.
            </p>
          </section>

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
            <section className="wm-card p-4 lg:col-span-1" aria-label="Notifications overview list">
              <div className="mb-3">
                <h2 className="text-base font-semibold text-slate-900">Email notifications</h2>
                <p className="mt-1 text-sm text-slate-600">Selectează o notificare pentru activare/dezactivare.</p>
              </div>

              {listLoading ? <p className="text-sm text-slate-500">Se încarcă lista...</p> : null}
              {!listLoading && listError ? <p className="text-sm text-red-600">{listError}</p> : null}
              {!listLoading && !listError && items.length === 0 ? <p className="text-sm text-slate-500">Nu există notifications disponibile.</p> : null}

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
                        onClick={() => {
                          setSelectedKey(item.key);
                          setFeedback("");
                        }}
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
                          <span className="text-xs text-slate-500">{formatDate(item.updated_at)}</span>
                        </div>
                        <p className="mt-2 text-xs text-slate-500">Template: {item.template_key}</p>
                      </button>
                    </li>
                  );
                })}
              </ul>
            </section>

            <section className="wm-card p-4 lg:col-span-2" aria-label="Notification detail panel">
              {!selectedKey ? <p className="text-sm text-slate-500">Selectează o notificare din listă.</p> : null}
              {selectedKey && detailLoading ? <p className="text-sm text-slate-500">Se încarcă detaliile...</p> : null}
              {selectedKey && !detailLoading && detailError ? <p className="text-sm text-red-600">{detailError}</p> : null}

              {selectedKey && !detailLoading && !detailError && detail ? (
                <div className="space-y-4">
                  <div>
                    <h2 className="text-base font-semibold text-slate-900">{detail.label}</h2>
                    <p className="mt-1 text-sm text-slate-600">{detail.description}</p>
                  </div>

                  <div className="grid grid-cols-1 gap-3 rounded-lg border border-slate-200 bg-slate-50 p-3 text-xs text-slate-700 md:grid-cols-2">
                    <p>
                      <span className="font-semibold text-slate-800">Channel:</span> {detail.channel}
                    </p>
                    <p>
                      <span className="font-semibold text-slate-800">Scope:</span> {detail.scope}
                    </p>
                    <p>
                      <span className="font-semibold text-slate-800">Template key:</span> {detail.template_key}
                    </p>
                    <p>
                      <span className="font-semibold text-slate-800">Updated:</span> {formatDate(detail.updated_at)}
                    </p>
                    <p>
                      <span className="font-semibold text-slate-800">Default enabled:</span> {String(Boolean(detail.default_enabled))}
                    </p>
                    <p>
                      <span className="font-semibold text-slate-800">Overridden:</span> {String(Boolean(detail.is_overridden))}
                    </p>
                  </div>

                  <div className="rounded-lg border border-slate-200 p-3">
                    <label className="inline-flex items-center gap-2 text-sm font-medium text-slate-800">
                      <input
                        type="checkbox"
                        checked={enabledDraft}
                        onChange={(event) => setEnabledDraft(event.target.checked)}
                        disabled={saveLoading || resetLoading}
                      />
                      Enabled
                    </label>
                    <p className="mt-2 text-xs text-slate-600">
                      Când este dezactivată, această notificare nu mai trimite email în flow-ul runtime asociat.
                    </p>
                    {selectedHint ? <p className="mt-1 text-xs text-amber-700">{selectedHint}</p> : null}
                    <Link href="/agency/email-templates" className="mt-2 inline-flex text-xs font-medium text-sky-700 underline">
                      Edit associated template
                    </Link>
                  </div>

                  {feedback ? <p className="text-sm text-slate-700">{feedback}</p> : null}

                  <div className="flex flex-wrap gap-2">
                    <button className="wm-btn-primary" onClick={() => void handleSave()} disabled={saveLoading || resetLoading || !hasChanges}>
                      {saveLoading ? "Se salvează..." : "Save changes"}
                    </button>
                    <button
                      className="rounded-md border border-slate-300 px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50"
                      onClick={() => void handleReset()}
                      disabled={resetLoading || saveLoading}
                    >
                      {resetLoading ? "Se resetează..." : "Reset to default"}
                    </button>
                  </div>
                </div>
              ) : null}
            </section>
          </div>
        </div>
      </AppShell>
    </ProtectedPage>
  );
}

