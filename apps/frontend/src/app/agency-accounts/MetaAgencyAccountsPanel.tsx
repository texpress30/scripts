"use client";

import React, { useEffect, useMemo, useState } from "react";

import { apiRequest } from "@/lib/api";

type ClientOption = {
  id: number;
  name: string;
  display_id?: number;
};

type MetaAccountItem = {
  id?: string;
  account_id?: string;
  name?: string;
  display_name?: string;
  attached_client_id?: number | null;
  attached_client_name?: string | null;
  status?: string | null;
  currency?: string | null;
  timezone?: string | null;
  [key: string]: unknown;
};

type MetaAccountsResponse = {
  items?: MetaAccountItem[];
  count?: number;
};

type RowBusy = {
  mode: "attach" | "detach";
  accountId: string;
};

function resolveAccountId(item: MetaAccountItem): string {
  return String(item.account_id || item.id || "").trim();
}

function resolveAccountName(item: MetaAccountItem): string {
  const name = String(item.display_name || item.name || "").trim();
  return name || `Meta Account ${resolveAccountId(item) || "unknown"}`;
}

export function MetaAgencyAccountsPanel({ clients }: { clients: ClientOption[] }) {
  const [metaAccounts, setMetaAccounts] = useState<MetaAccountItem[]>([]);
  const [loadingMeta, setLoadingMeta] = useState(true);
  const [loadingMetaError, setLoadingMetaError] = useState("");
  const [rowBusy, setRowBusy] = useState<RowBusy | null>(null);
  const [rowError, setRowError] = useState<Record<string, string>>({});
  const [rowSuccess, setRowSuccess] = useState("");
  const [selectedClientByAccount, setSelectedClientByAccount] = useState<Record<string, string>>({});

  const clientsUnavailable = clients.length === 0;

  async function loadMetaAccounts() {
    setLoadingMeta(true);
    setLoadingMetaError("");
    try {
      const payload = await apiRequest<MetaAccountsResponse>("/clients/accounts/meta_ads");
      setMetaAccounts(Array.isArray(payload.items) ? payload.items : []);
    } catch (err) {
      setMetaAccounts([]);
      setLoadingMetaError(err instanceof Error ? err.message : "Nu am putut încărca Meta accounts");
    } finally {
      setLoadingMeta(false);
    }
  }

  useEffect(() => {
    void loadMetaAccounts();
  }, []);

  const normalizedRows = useMemo(
    () =>
      metaAccounts
        .map((item) => {
          const accountId = resolveAccountId(item);
          return {
            raw: item,
            accountId,
            accountName: resolveAccountName(item),
            attachedClientId: item.attached_client_id ?? null,
            attachedClientName: item.attached_client_name ?? null,
            status: item.status ?? null,
            currency: item.currency ?? null,
            timezone: item.timezone ?? null,
          };
        })
        .filter((item) => item.accountId !== ""),
    [metaAccounts],
  );

  async function attachMetaAccount(accountId: string) {
    const selectedClientId = Number(selectedClientByAccount[accountId] || 0);
    if (!selectedClientId) return;

    setRowSuccess("");
    setRowError((current) => ({ ...current, [accountId]: "" }));
    setRowBusy({ mode: "attach", accountId });
    try {
      await apiRequest(`/clients/${selectedClientId}/attach-account`, {
        method: "POST",
        body: JSON.stringify({ platform: "meta_ads", account_id: accountId }),
      });
      setRowSuccess(`Contul Meta ${accountId} a fost atașat.`);
      await loadMetaAccounts();
    } catch (err) {
      setRowError((current) => ({ ...current, [accountId]: err instanceof Error ? err.message : "Attach Meta account failed" }));
    } finally {
      setRowBusy(null);
    }
  }

  async function detachMetaAccount(clientId: number, accountId: string) {
    setRowSuccess("");
    setRowError((current) => ({ ...current, [accountId]: "" }));
    setRowBusy({ mode: "detach", accountId });
    try {
      await apiRequest(`/clients/${clientId}/detach-account`, {
        method: "POST",
        body: JSON.stringify({ platform: "meta_ads", account_id: accountId }),
      });
      setRowSuccess(`Contul Meta ${accountId} a fost detașat.`);
      await loadMetaAccounts();
    } catch (err) {
      setRowError((current) => ({ ...current, [accountId]: err instanceof Error ? err.message : "Detach Meta account failed" }));
    } finally {
      setRowBusy(null);
    }
  }

  return (
    <div className="mt-4 wm-card p-4">
      <div className="flex items-center justify-between gap-2">
        <h3 className="text-base font-semibold text-slate-900">Meta Ads Accounts</h3>
        <button
          type="button"
          className="rounded-md border border-slate-300 px-3 py-1 text-xs font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50"
          onClick={() => void loadMetaAccounts()}
          disabled={loadingMeta || rowBusy !== null}
        >
          {loadingMeta ? "Refreshing..." : "Refresh"}
        </button>
      </div>

      {rowSuccess ? <p className="mt-2 text-xs text-emerald-700">{rowSuccess}</p> : null}
      {loadingMetaError ? <p className="mt-2 text-xs text-red-600">{loadingMetaError}</p> : null}
      {clientsUnavailable ? <p className="mt-2 text-xs text-amber-700">Nu există clienți disponibili; atașarea este dezactivată.</p> : null}

      {loadingMeta ? <p className="mt-3 text-sm text-slate-500">Se încarcă conturile Meta...</p> : null}
      {!loadingMeta && normalizedRows.length === 0 ? (
        <p className="mt-3 text-sm text-slate-500">Nu există conturi Meta importate. Rulează Import Accounts din Agency Integrations.</p>
      ) : null}

      {!loadingMeta && normalizedRows.length > 0 ? (
        <div className="mt-3 space-y-3">
          {normalizedRows.map((row) => {
            const isAttached = Boolean(row.attachedClientId);
            const isAttachBusy = rowBusy?.mode === "attach" && rowBusy.accountId === row.accountId;
            const isDetachBusy = rowBusy?.mode === "detach" && rowBusy.accountId === row.accountId;
            const selectedClientId = selectedClientByAccount[row.accountId] ?? "";

            return (
              <div key={row.accountId} className="rounded-md border border-slate-200 p-3">
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <div>
                    <p className="text-sm font-semibold text-slate-900">{row.accountName}</p>
                    <p className="text-xs text-slate-500">ID: {row.accountId}</p>
                    <p className={`mt-1 inline-flex rounded-full px-2 py-0.5 text-[11px] font-medium ${isAttached ? "bg-emerald-100 text-emerald-700" : "bg-amber-100 text-amber-700"}`}>
                      {isAttached ? "Atașat" : "Neatașat"}
                    </p>
                    <div className="mt-1 space-y-0.5 text-xs text-slate-500">
                      {row.status ? <p>Status: {row.status}</p> : null}
                      {row.currency ? <p>Currency: {row.currency}</p> : null}
                      {row.timezone ? <p>Timezone: {row.timezone}</p> : null}
                    </div>
                    {isAttached ? <p className="mt-1 text-xs text-slate-700">Client: {row.attachedClientName || `#${row.attachedClientId}`}</p> : null}
                  </div>

                  <div className="min-w-[240px] space-y-2">
                    {!isAttached ? (
                      <>
                        <select
                          aria-label={`client-select-${row.accountId}`}
                          className="w-full rounded-md border border-slate-300 px-2 py-1 text-sm"
                          value={selectedClientId}
                          onChange={(event) =>
                            setSelectedClientByAccount((current) => ({
                              ...current,
                              [row.accountId]: event.target.value,
                            }))
                          }
                          disabled={isAttachBusy || clientsUnavailable}
                        >
                          <option value="">Alege client...</option>
                          {clients.map((client) => (
                            <option key={client.id} value={client.id}>
                              #{client.display_id ?? client.id} {client.name}
                            </option>
                          ))}
                        </select>
                        <button
                          type="button"
                          className="w-full rounded-md bg-indigo-600 px-3 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50"
                          onClick={() => void attachMetaAccount(row.accountId)}
                          disabled={isAttachBusy || clientsUnavailable || Number(selectedClientId || 0) <= 0}
                        >
                          {isAttachBusy ? "Attaching..." : "Attach"}
                        </button>
                      </>
                    ) : (
                      <button
                        type="button"
                        className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50"
                        onClick={() => void detachMetaAccount(Number(row.attachedClientId), row.accountId)}
                        disabled={isDetachBusy}
                      >
                        {isDetachBusy ? "Detaching..." : "Detach"}
                      </button>
                    )}
                    {rowError[row.accountId] ? <p className="text-xs text-red-600">{rowError[row.accountId]}</p> : null}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      ) : null}
    </div>
  );
}
