"use client";

import React from "react";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import { ArrowLeft, Check, Loader2, Pencil } from "lucide-react";

import { AppShell } from "@/components/AppShell";
import { ProtectedPage } from "@/components/ProtectedPage";
import { AccountSyncStatus } from "@/components/AccountSyncStatus";
import { apiRequest } from "@/lib/api";
import { deriveAccountSyncStatus } from "@/lib/accountSyncStatus";

type Account = {
  id: string;
  name: string;
  client_type?: string;
  account_manager?: string;
  currency?: string;
  coverage_status?: string;
  sync_health_status?: string;
  last_error?: string;
  last_error_summary?: string;
  last_error_details?: Record<string, unknown> | string;
  last_sync_at?: string;
  last_success_at?: string;
  requested_start_date?: string;
  requested_end_date?: string;
  total_chunk_count?: number;
  successful_chunk_count?: number;
  failed_chunk_count?: number;
  retry_attempted?: boolean;
  retry_recovered_chunk_count?: number;
  rows_written_count?: number;
  first_persisted_date?: string;
  last_persisted_date?: string;
};
type PlatformInfo = { platform: string; enabled: boolean; count: number; accounts: Account[] };
type ClientDetails = {
  client: {
    id: number;
    display_id?: number;
    name: string;
    owner_email: string;
    client_type?: string;
    account_manager?: string;
    currency?: string;
  };
  platforms: PlatformInfo[];
};

type SaveField = "name" | "clientCurrency" | "row";
type RowField = "clientType" | "accountManager" | "currency";
type RowDraft = { clientType: string; accountManager: string; currency: string };

const CURRENCY_OPTIONS = ["USD", "EUR", "RON", "GBP"];

function prettyPlatform(platform: string): string {
  const map: Record<string, string> = {
    google_ads: "Google Ads",
    meta_ads: "Meta Ads",
    tiktok_ads: "TikTok Ads",
    pinterest_ads: "Pinterest Ads",
    snapchat_ads: "Snapchat Ads",
  };
  return map[platform] ?? platform;
}

function rowKey(platform: string, accountId: string): string {
  return `${platform}:${accountId}`;
}

function rowFieldKey(key: string, field: RowField): string {
  return `${key}:${field}`;
}

export default function AgencyClientDetailsPage() {
  const params = useParams<{ id: string }>();
  const displayId = Number(params.id);
  const [data, setData] = useState<ClientDetails | null>(null);
  const [error, setError] = useState("");

  const [editingName, setEditingName] = useState(false);
  const [editingClientCurrency, setEditingClientCurrency] = useState(false);
  const [editingRowFieldKey, setEditingRowFieldKey] = useState<string | null>(null);

  const [nameInput, setNameInput] = useState("");
  const [clientCurrencyInput, setClientCurrencyInput] = useState("USD");
  const [rowDrafts, setRowDrafts] = useState<Record<string, RowDraft>>({});

  const [savingField, setSavingField] = useState<SaveField | null>(null);
  const [savingRowFieldKey, setSavingRowFieldKey] = useState<string | null>(null);
  const [savedField, setSavedField] = useState<string | null>(null);

  function markSaved(field: string) {
    setSavedField(field);
    window.setTimeout(() => setSavedField((current) => (current === field ? null : current)), 1200);
  }

  function setAllRowDraftsFromPayload(payload: ClientDetails) {
    const next: Record<string, RowDraft> = {};
    for (const platform of payload.platforms) {
      for (const account of platform.accounts) {
        next[rowKey(platform.platform, account.id)] = {
          clientType: account.client_type ?? payload.client.client_type ?? "lead",
          accountManager: account.account_manager ?? payload.client.account_manager ?? "",
          currency: account.currency ?? payload.client.currency ?? "USD",
        };
      }
    }
    setRowDrafts(next);
  }

  async function load() {
    setError("");
    try {
      const payload = await apiRequest<ClientDetails>(`/clients/display/${displayId}`);
      setData(payload);
      setNameInput(payload.client.name);
      setClientCurrencyInput((payload.client.currency ?? "USD").toUpperCase());
      setAllRowDraftsFromPayload(payload);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Nu am putut încărca detaliile clientului.");
    }
  }

  useEffect(() => {
    if (displayId > 0) {
      void load();
    }
  }, [displayId]);

  async function patchProfile(payload: { name?: string; client_type?: string; account_manager?: string; currency?: string; platform?: string; account_id?: string }, field: SaveField, successKey: string, rowFieldId?: string) {
    setSavingField(field);
    if (rowFieldId) setSavingRowFieldKey(rowFieldId);
    setError("");
    try {
      const response = await apiRequest<ClientDetails>(`/clients/display/${displayId}`, {
        method: "PATCH",
        body: JSON.stringify(payload),
      });
      setData(response);
      setNameInput(response.client.name);
      setClientCurrencyInput((response.client.currency ?? "USD").toUpperCase());
      setAllRowDraftsFromPayload(response);
      markSaved(successKey);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Nu am putut salva modificarea.");
    } finally {
      setSavingField((current) => (current === field ? null : current));
      if (rowFieldId) setSavingRowFieldKey((current) => (current === rowFieldId ? null : current));
    }
  }

  async function saveNameIfChanged() {
    if (!data) return;
    const trimmed = nameInput.trim();
    const current = data.client.name;
    if (trimmed === "" || trimmed === current) {
      setNameInput(current);
      setEditingName(false);
      return;
    }
    await patchProfile({ name: trimmed }, "name", "name");
    setEditingName(false);
  }

  async function saveClientCurrencyIfChanged(nextValue?: string) {
    if (!data) return;
    const normalizedCurrency = (nextValue ?? clientCurrencyInput).trim().toUpperCase();
    const currentCurrency = (data.client.currency ?? "USD").toUpperCase();

    if (normalizedCurrency === "" || normalizedCurrency === currentCurrency) {
      setClientCurrencyInput(currentCurrency);
      setEditingClientCurrency(false);
      return;
    }

    await patchProfile({ currency: normalizedCurrency }, "clientCurrency", "clientCurrency");
    setEditingClientCurrency(false);
  }

  async function saveRowFieldIfChanged(key: string, platform: string, accountId: string, field: RowField, nextDraft?: RowDraft) {
    if (!data) return;
    const draft = nextDraft ?? rowDrafts[key];
    if (!draft) {
      setEditingRowFieldKey(null);
      return;
    }

    const currentAccount = data.platforms
      .find((item) => item.platform === platform)
      ?.accounts.find((item) => item.id === accountId);

    const currentType = currentAccount?.client_type ?? data.client.client_type ?? "lead";
    const currentManager = currentAccount?.account_manager ?? data.client.account_manager ?? "";
    const currentCurrency = currentAccount?.currency ?? data.client.currency ?? "USD";

    const normalizedManager = draft.accountManager.trim();
    const normalizedCurrency = draft.currency.toUpperCase();
    const rowFieldId = rowFieldKey(key, field);

    let payload: { client_type?: string; account_manager?: string; currency?: string; platform: string; account_id: string } | null = null;

    if (field === "clientType") {
      if (draft.clientType === currentType) {
        setEditingRowFieldKey(null);
        return;
      }
      payload = { client_type: draft.clientType, platform, account_id: accountId };
    }

    if (field === "accountManager") {
      if (normalizedManager === currentManager) {
        setEditingRowFieldKey(null);
        return;
      }
      payload = { account_manager: normalizedManager, platform, account_id: accountId };
    }

    if (field === "currency") {
      if (normalizedCurrency === currentCurrency) {
        setEditingRowFieldKey(null);
        return;
      }
      payload = { currency: normalizedCurrency, platform, account_id: accountId };
    }

    if (payload) {
      await patchProfile(payload, "row", rowFieldId, rowFieldId);
    }
    setEditingRowFieldKey(null);
  }

  const title = useMemo(() => (data ? `Client: ${data.client.name}` : `Client #${displayId}`), [data, displayId]);

  const sectionSyncSummary = useMemo(() => {
    if (!data) return {} as Record<string, { warning: number; error: number }>;
    const byPlatform: Record<string, { warning: number; error: number }> = {};
    for (const platform of data.platforms) {
      const normalized = String(platform.platform || "").toLowerCase();
      if (normalized !== "meta_ads" && normalized !== "tiktok_ads") continue;
      const counter = { warning: 0, error: 0 };
      for (const account of platform.accounts) {
        const ui = deriveAccountSyncStatus(platform.platform, account as unknown as Record<string, unknown>);
        if (ui.uiStatus === "warning") counter.warning += 1;
        if (ui.uiStatus === "error") counter.error += 1;
      }
      byPlatform[platform.platform] = counter;
    }
    return byPlatform;
  }, [data]);

  return (
    <ProtectedPage>
      <AppShell
        title={title}
        headerPrefix={
          <Link
            href="/agency/clients"
            className="inline-flex h-8 w-8 items-center justify-center rounded-md border border-slate-200 text-slate-600 hover:bg-slate-50"
            title="Înapoi la clienți"
          >
            <ArrowLeft className="h-4 w-4" />
          </Link>
        }
      >
        <main className="space-y-4 p-6">
          {error ? (
            <p className="rounded-md border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</p>
          ) : null}

          {!data ? (
            <p className="text-sm text-slate-500">Se încarcă detaliile clientului...</p>
          ) : (
            <>
              <section className="wm-card space-y-2 p-4">
                <div className="flex items-center justify-between gap-3">
                  {editingName ? (
                    <input
                      value={nameInput}
                      onChange={(e) => setNameInput(e.target.value)}
                      onBlur={() => void saveNameIfChanged()}
                      onKeyDown={(e) => {
                        if (e.key === "Enter") {
                          e.preventDefault();
                          void saveNameIfChanged();
                        }
                        if (e.key === "Escape") {
                          setNameInput(data.client.name);
                          setEditingName(false);
                        }
                      }}
                      className="w-full rounded-md border border-slate-300 px-3 py-2 text-2xl font-semibold text-slate-900"
                      autoFocus
                    />
                  ) : (
                    <h2 className="text-3xl font-semibold text-slate-900">{data.client.name}</h2>
                  )}
                  <button
                    type="button"
                    onClick={() => setEditingName((current) => !current)}
                    className="rounded p-2 text-slate-500 hover:bg-slate-100"
                    title="Editează numele clientului"
                    disabled={savingField === "name"}
                  >
                    {savingField === "name" ? (
                      <Loader2 className="h-4 w-4 animate-spin text-slate-500" />
                    ) : savedField === "name" ? (
                      <Check className="h-4 w-4 text-emerald-600" />
                    ) : (
                      <Pencil className="h-4 w-4" />
                    )}
                  </button>
                </div>
                <p className="text-sm text-slate-600">Owner: {data.client.owner_email}</p>
                <div className="flex items-center justify-between gap-2 text-sm">
                  <div className="flex items-center gap-2">
                    <span className="text-slate-500">Moneda clientului:</span>
                    {editingClientCurrency ? (
                      <select
                        value={clientCurrencyInput}
                        onChange={(e) => {
                          const value = e.target.value;
                          setClientCurrencyInput(value);
                          void saveClientCurrencyIfChanged(value);
                        }}
                        className="rounded border border-slate-300 px-2 py-1 text-xs"
                        disabled={savingField === "clientCurrency"}
                        autoFocus
                      >
                        {CURRENCY_OPTIONS.map((currency) => (
                          <option key={currency} value={currency}>
                            {currency}
                          </option>
                        ))}
                      </select>
                    ) : (
                      <span className="font-medium text-slate-700">{(data.client.currency ?? "USD").toUpperCase()}</span>
                    )}
                  </div>
                  <button
                    type="button"
                    onClick={() => {
                      setClientCurrencyInput((data.client.currency ?? "USD").toUpperCase());
                      setEditingClientCurrency(true);
                    }}
                    className="rounded p-1 text-slate-500 hover:bg-slate-100"
                    title="Editează moneda clientului"
                    disabled={savingField === "clientCurrency"}
                  >
                    {savingField === "clientCurrency" ? (
                      <Loader2 className="h-3.5 w-3.5 animate-spin text-slate-500" />
                    ) : savedField === "clientCurrency" ? (
                      <Check className="h-3.5 w-3.5 text-emerald-600" />
                    ) : (
                      <Pencil className="h-3.5 w-3.5" />
                    )}
                  </button>
                </div>
              </section>

              <section className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
                {data.platforms.map((platform) => (
                  <article key={platform.platform} className="wm-card p-4">
                    <div className="flex items-center justify-between gap-2">
                      <h3 className="text-base font-semibold text-slate-900">{prettyPlatform(platform.platform)}</h3>
                      {sectionSyncSummary[platform.platform] && (sectionSyncSummary[platform.platform].warning > 0 || sectionSyncSummary[platform.platform].error > 0) ? (
                        <span className="text-xs font-medium text-slate-600">
                          {sectionSyncSummary[platform.platform].error > 0 ? `${sectionSyncSummary[platform.platform].error} error` : null}
                          {sectionSyncSummary[platform.platform].error > 0 && sectionSyncSummary[platform.platform].warning > 0 ? " • " : null}
                          {sectionSyncSummary[platform.platform].warning > 0 ? `${sectionSyncSummary[platform.platform].warning} warning` : null}
                        </span>
                      ) : null}
                    </div>
                    <p className="mt-1 text-xs text-slate-500">Activ: {platform.enabled ? "Da" : "Nu"}</p>
                    <p className="text-xs text-slate-500">Conturi atașate: {platform.count}</p>
                    <ul className="mt-2 space-y-2">
                      {platform.accounts.map((account) => {
                        const key = rowKey(platform.platform, account.id);
                        const draft = rowDrafts[key] ?? {
                          clientType: account.client_type ?? data.client.client_type ?? "lead",
                          accountManager: account.account_manager ?? data.client.account_manager ?? "",
                          currency: account.currency ?? data.client.currency ?? "USD",
                        };
                        const typeFieldId = rowFieldKey(key, "clientType");
                        const managerFieldId = rowFieldKey(key, "accountManager");
                        const currencyFieldId = rowFieldKey(key, "currency");
                        return (
                          <li key={key} className="rounded-md border border-slate-100 p-2 text-sm text-slate-700">
                            <div className="flex items-start justify-between gap-2">
                              <div>
                                {account.name} <span className="text-xs text-slate-500">({account.id})</span>
                              </div>
                            </div>

                            {(platform.platform === "meta_ads" || platform.platform === "tiktok_ads") ? (
                              <AccountSyncStatus platform={platform.platform} account={account as unknown as Record<string, unknown>} />
                            ) : null}

                            <div className="mt-2 space-y-2 text-xs">
                              <div className="flex items-center justify-between gap-2">
                                <div className="flex items-center gap-2">
                                  <span className="text-slate-500">Tip client:</span>
                                  {editingRowFieldKey === typeFieldId ? (
                                    <select
                                      value={draft.clientType}
                                      onChange={(e) => {
                                        const value = e.target.value;
                                        const nextDraft = { ...draft, clientType: value };
                                        setRowDrafts((prev) => ({ ...prev, [key]: nextDraft }));
                                        void saveRowFieldIfChanged(key, platform.platform, account.id, "clientType", nextDraft);
                                      }}
                                      className="rounded border border-slate-300 px-2 py-1 text-xs"
                                      disabled={savingRowFieldKey === typeFieldId}
                                      autoFocus
                                    >
                                      <option value="lead">lead</option>
                                      <option value="e-commerce">e-commerce</option>
                                      <option value="programmatic">programmatic</option>
                                    </select>
                                  ) : (
                                    <span className="font-medium text-slate-700">{draft.clientType}</span>
                                  )}
                                </div>
                                <button
                                  type="button"
                                  onClick={() => setEditingRowFieldKey(typeFieldId)}
                                  className="rounded p-1 text-slate-500 hover:bg-slate-100"
                                  title="Editează tipul contului"
                                  disabled={savingRowFieldKey === typeFieldId}
                                >
                                  {savingRowFieldKey === typeFieldId ? <Loader2 className="h-3.5 w-3.5 animate-spin text-slate-500" /> : savedField === typeFieldId ? <Check className="h-3.5 w-3.5 text-emerald-600" /> : <Pencil className="h-3.5 w-3.5" />}
                                </button>
                              </div>

                              <div className="flex items-center justify-between gap-2">
                                <div className="flex items-center gap-2">
                                  <span className="text-slate-500">Responsabil:</span>
                                  {editingRowFieldKey === managerFieldId ? (
                                    <input
                                      value={draft.accountManager}
                                      onChange={(e) => setRowDrafts((prev) => ({ ...prev, [key]: { ...draft, accountManager: e.target.value } }))}
                                      onBlur={() => void saveRowFieldIfChanged(key, platform.platform, account.id, "accountManager")}
                                      onKeyDown={(e) => {
                                        if (e.key === "Enter") {
                                          e.preventDefault();
                                          void saveRowFieldIfChanged(key, platform.platform, account.id, "accountManager");
                                        }
                                        if (e.key === "Escape") {
                                          setEditingRowFieldKey(null);
                                        }
                                      }}
                                      className="w-full rounded border border-slate-300 px-2 py-1 text-xs"
                                      placeholder="Nume responsabil"
                                      autoFocus
                                    />
                                  ) : (
                                    <span className="font-medium text-slate-700">{draft.accountManager || "—"}</span>
                                  )}
                                </div>
                                <button
                                  type="button"
                                  onClick={() => setEditingRowFieldKey(managerFieldId)}
                                  className="rounded p-1 text-slate-500 hover:bg-slate-100"
                                  title="Editează responsabilul"
                                  disabled={savingRowFieldKey === managerFieldId}
                                >
                                  {savingRowFieldKey === managerFieldId ? <Loader2 className="h-3.5 w-3.5 animate-spin text-slate-500" /> : savedField === managerFieldId ? <Check className="h-3.5 w-3.5 text-emerald-600" /> : <Pencil className="h-3.5 w-3.5" />}
                                </button>
                              </div>

                              <div className="flex items-center justify-between gap-2">
                                <div className="flex items-center gap-2">
                                  <span className="text-slate-500">Moneda contului:</span>
                                  {editingRowFieldKey === currencyFieldId ? (
                                    <select
                                      value={draft.currency}
                                      onChange={(e) => {
                                        const value = e.target.value;
                                        const nextDraft = { ...draft, currency: value };
                                        setRowDrafts((prev) => ({ ...prev, [key]: nextDraft }));
                                        void saveRowFieldIfChanged(key, platform.platform, account.id, "currency", nextDraft);
                                      }}
                                      className="rounded border border-slate-300 px-2 py-1 text-xs"
                                      disabled={savingRowFieldKey === currencyFieldId}
                                      autoFocus
                                    >
                                      {CURRENCY_OPTIONS.map((currency) => (
                                        <option key={currency} value={currency}>
                                          {currency}
                                        </option>
                                      ))}
                                    </select>
                                  ) : (
                                    <span className="font-medium text-slate-700">{draft.currency}</span>
                                  )}
                                </div>
                                <button
                                  type="button"
                                  onClick={() => setEditingRowFieldKey(currencyFieldId)}
                                  className="rounded p-1 text-slate-500 hover:bg-slate-100"
                                  title="Editează moneda contului sursă"
                                  disabled={savingRowFieldKey === currencyFieldId}
                                >
                                  {savingRowFieldKey === currencyFieldId ? <Loader2 className="h-3.5 w-3.5 animate-spin text-slate-500" /> : savedField === currencyFieldId ? <Check className="h-3.5 w-3.5 text-emerald-600" /> : <Pencil className="h-3.5 w-3.5" />}
                                </button>
                              </div>

                            </div>
                          </li>
                        );
                      })}
                      {platform.accounts.length === 0 ? <li className="text-sm text-slate-400">Fără conturi atașate.</li> : null}
                    </ul>
                  </article>
                ))}
              </section>
            </>
          )}
        </main>
      </AppShell>
    </ProtectedPage>
  );
}
