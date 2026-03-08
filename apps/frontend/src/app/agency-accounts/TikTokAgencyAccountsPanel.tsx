"use client";

import React, { useEffect, useMemo, useState } from "react";

import { apiRequest } from "@/lib/api";

type ClientRecord = {
  id: number;
  name: string;
  owner_email?: string;
  display_id?: number;
};

type ClientsResponse = {
  items?: ClientRecord[];
};

type TikTokAccount = {
  id: string;
  name: string;
  account_id?: string;
  account_name?: string;
  attached_client_id?: number | null;
  attached_client_name?: string | null;
  status?: string | null;
  currency?: string | null;
  timezone?: string | null;
};

type TikTokAccountsResponse = {
  items?: TikTokAccount[];
  count?: number;
  last_import_at?: string | null;
};

function formatDateTime(value?: string | null): string {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString();
}

function rowAccountName(account: TikTokAccount): string {
  return String(account.name || account.account_name || account.id || account.account_id || "-");
}

function rowAccountId(account: TikTokAccount): string {
  return String(account.id || account.account_id || "-");
}

function isIntegrationsUnavailableError(message: string): boolean {
  const normalized = message.trim().toLowerCase();
  return normalized.includes("disabled") || normalized.includes("feature flag") || normalized.includes("integration");
}

export function TikTokAgencyAccountsPanel() {
  const [accountsLoading, setAccountsLoading] = useState(true);
  const [clientsLoading, setClientsLoading] = useState(true);
  const [accountsError, setAccountsError] = useState("");
  const [clientsError, setClientsError] = useState("");
  const [accounts, setAccounts] = useState<TikTokAccount[]>([]);
  const [lastImportAt, setLastImportAt] = useState<string | null>(null);
  const [clients, setClients] = useState<ClientRecord[]>([]);
  const [selectedClientByAccount, setSelectedClientByAccount] = useState<Record<string, string>>({});
  const [attachBusyByAccount, setAttachBusyByAccount] = useState<Record<string, boolean>>({});
  const [detachBusyByAccount, setDetachBusyByAccount] = useState<Record<string, boolean>>({});
  const [actionErrorByAccount, setActionErrorByAccount] = useState<Record<string, string>>({});
  const [successMessage, setSuccessMessage] = useState("");

  const clientsMap = useMemo(() => {
    const map = new Map<number, ClientRecord>();
    for (const client of clients) map.set(client.id, client);
    return map;
  }, [clients]);

  const clientsUnavailable = !clientsLoading && clients.length === 0;

  async function loadClients() {
    setClientsLoading(true);
    setClientsError("");
    try {
      const payload = await apiRequest<ClientsResponse>("/clients");
      setClients(payload.items ?? []);
    } catch (err) {
      setClients([]);
      setClientsError(err instanceof Error ? err.message : "Nu am putut încărca lista de clienți.");
    } finally {
      setClientsLoading(false);
    }
  }

  async function loadTikTokAccounts() {
    setAccountsLoading(true);
    setAccountsError("");
    try {
      const payload = await apiRequest<TikTokAccountsResponse>("/clients/accounts/tiktok_ads");
      setAccounts(payload.items ?? []);
      setLastImportAt(payload.last_import_at ?? null);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Nu am putut încărca conturile TikTok.";
      setAccounts([]);
      setLastImportAt(null);
      setAccountsError(message);
    } finally {
      setAccountsLoading(false);
    }
  }

  useEffect(() => {
    void Promise.all([loadClients(), loadTikTokAccounts()]);
  }, []);

  function setAttachBusy(accountId: string, value: boolean) {
    setAttachBusyByAccount((current) => ({ ...current, [accountId]: value }));
  }

  function setDetachBusy(accountId: string, value: boolean) {
    setDetachBusyByAccount((current) => ({ ...current, [accountId]: value }));
  }

  function setRowError(accountId: string, value: string) {
    setActionErrorByAccount((current) => ({ ...current, [accountId]: value }));
  }

  async function handleAttach(account: TikTokAccount) {
    const accountId = rowAccountId(account);
    const selectedClientIdRaw = selectedClientByAccount[accountId] ?? "";
    const clientId = Number(selectedClientIdRaw);

    if (!selectedClientIdRaw || Number.isNaN(clientId) || clientId <= 0) {
      setRowError(accountId, "Selectează un client înainte de attach.");
      return;
    }

    setSuccessMessage("");
    setRowError(accountId, "");
    setAttachBusy(accountId, true);
    try {
      await apiRequest(`/clients/${clientId}/attach-account`, {
        method: "POST",
        body: JSON.stringify({ platform: "tiktok_ads", account_id: accountId }),
      });
      const clientName = clientsMap.get(clientId)?.name ?? `#${clientId}`;
      setSuccessMessage(`Contul ${accountId} a fost atașat la ${clientName}.`);
      await loadTikTokAccounts();
    } catch (err) {
      setRowError(accountId, err instanceof Error ? err.message : "Nu am putut atașa contul TikTok.");
    } finally {
      setAttachBusy(accountId, false);
    }
  }

  async function handleDetach(account: TikTokAccount) {
    const accountId = rowAccountId(account);
    const clientId = Number(account.attached_client_id ?? 0);
    if (!clientId) {
      setRowError(accountId, "Nu putem determina clientul atașat pentru detach.");
      return;
    }

    setSuccessMessage("");
    setRowError(accountId, "");
    setDetachBusy(accountId, true);
    try {
      await apiRequest(`/clients/${clientId}/detach-account`, {
        method: "POST",
        body: JSON.stringify({ platform: "tiktok_ads", account_id: accountId }),
      });
      const clientName = clientsMap.get(clientId)?.name ?? account.attached_client_name ?? `#${clientId}`;
      setSuccessMessage(`Contul ${accountId} a fost detașat de la ${clientName}.`);
      await loadTikTokAccounts();
    } catch (err) {
      setRowError(accountId, err instanceof Error ? err.message : "Nu am putut detașa contul TikTok.");
    } finally {
      setDetachBusy(accountId, false);
    }
  }

  return (
    <div className="mt-4 wm-card p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-sm text-slate-600">
          Total TikTok Accounts: <span className="font-semibold text-slate-900">{accounts.length}</span>
        </p>
        <p className="text-xs text-slate-500">Ultimul import: {formatDateTime(lastImportAt)}</p>
      </div>

      {accountsLoading ? <p className="mt-3 text-sm text-slate-500">Se încarcă conturile TikTok...</p> : null}
      {clientsLoading ? <p className="mt-1 text-xs text-slate-500">Se încarcă lista de clienți...</p> : null}

      {accountsError ? (
        <p className={`mt-3 text-sm ${isIntegrationsUnavailableError(accountsError) ? "text-amber-700" : "text-red-600"}`}>
          {isIntegrationsUnavailableError(accountsError)
            ? `TikTok este momentan indisponibil: ${accountsError}`
            : accountsError}
        </p>
      ) : null}

      {clientsError ? <p className="mt-2 text-sm text-red-600">{clientsError}</p> : null}
      {successMessage ? <p className="mt-2 text-sm text-emerald-700">{successMessage}</p> : null}

      {!accountsLoading && !accountsError && accounts.length === 0 ? (
        <div className="mt-3 rounded-md border border-slate-200 bg-slate-50 p-3 text-sm text-slate-600">
          Nu există conturi TikTok importate încă. Rulează mai întâi <span className="font-medium">Import Accounts</span> din Agency Integrations.
        </div>
      ) : null}

      {!accountsLoading && !accountsError && accounts.length > 0 ? (
        <div className="mt-3 overflow-hidden rounded-md border border-slate-200">
          <div className="grid grid-cols-12 gap-2 border-b border-slate-200 bg-slate-50 px-3 py-2 text-xs font-medium uppercase tracking-wide text-slate-500">
            <div className="col-span-4">Cont</div>
            <div className="col-span-2">Status</div>
            <div className="col-span-2">Currency</div>
            <div className="col-span-2">Timezone</div>
            <div className="col-span-2">Acțiune</div>
          </div>

          <ul className="divide-y divide-slate-200">
            {accounts.map((account) => {
              const accountId = rowAccountId(account);
              const attachedClientId = Number(account.attached_client_id ?? 0) || null;
              const isAttached = attachedClientId !== null;
              const attachBusy = Boolean(attachBusyByAccount[accountId]);
              const detachBusy = Boolean(detachBusyByAccount[accountId]);
              const rowBusy = attachBusy || detachBusy;

              return (
                <li key={accountId} className="grid grid-cols-12 gap-2 px-3 py-3 text-sm text-slate-700" data-testid={`tiktok-row-${accountId}`}>
                  <div className="col-span-4">
                    <p className="font-medium text-slate-900">{rowAccountName(account)}</p>
                    <p className="text-xs text-slate-500">{accountId}</p>
                    {isAttached ? (
                      <p className="mt-1 text-xs text-emerald-700">
                        Atașat la {account.attached_client_name ?? (attachedClientId ? `Client #${attachedClientId}` : "-")}
                      </p>
                    ) : (
                      <p className="mt-1 text-xs text-slate-500">Neatașat</p>
                    )}
                    {actionErrorByAccount[accountId] ? <p className="mt-1 text-xs text-red-600">{actionErrorByAccount[accountId]}</p> : null}
                  </div>

                  <div className="col-span-2 text-xs text-slate-600">{account.status || "-"}</div>
                  <div className="col-span-2 text-xs text-slate-600">{account.currency || "-"}</div>
                  <div className="col-span-2 text-xs text-slate-600">{account.timezone || "-"}</div>

                  <div className="col-span-2">
                    {isAttached ? (
                      <button
                        type="button"
                        onClick={() => void handleDetach(account)}
                        disabled={rowBusy}
                        className="rounded-md border border-slate-300 px-2 py-1 text-xs font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50"
                      >
                        {detachBusy ? "Detaching..." : "Detach"}
                      </button>
                    ) : (
                      <div className="space-y-2">
                        <select
                          className="w-full rounded border border-slate-300 px-2 py-1 text-xs"
                          value={selectedClientByAccount[accountId] ?? ""}
                          onChange={(event) => {
                            const value = event.target.value;
                            setSelectedClientByAccount((current) => ({ ...current, [accountId]: value }));
                          }}
                          disabled={clientsLoading || clientsUnavailable || rowBusy}
                        >
                          <option value="">Selectează client</option>
                          {clients.map((client) => (
                            <option key={client.id} value={String(client.id)}>
                              {client.name}
                            </option>
                          ))}
                        </select>
                        <button
                          type="button"
                          onClick={() => void handleAttach(account)}
                          disabled={rowBusy || clientsLoading || clientsUnavailable || !selectedClientByAccount[accountId]}
                          className="rounded-md bg-indigo-600 px-2 py-1 text-xs font-medium text-white disabled:opacity-50"
                        >
                          {attachBusy ? "Attaching..." : "Attach"}
                        </button>
                        {clientsUnavailable ? <p className="text-[11px] text-amber-700">Attach indisponibil: lista de clienți este goală.</p> : null}
                      </div>
                    )}
                  </div>
                </li>
              );
            })}
          </ul>
        </div>
      ) : null}
    </div>
  );
}
