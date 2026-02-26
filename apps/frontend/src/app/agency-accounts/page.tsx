"use client";

import { useEffect, useMemo, useState } from "react";

import { AppShell } from "@/components/AppShell";
import { ProtectedPage } from "@/components/ProtectedPage";
import { apiRequest } from "@/lib/api";

type ClientRecord = {
  id: number;
  name: string;
  owner_email: string;
  google_customer_id?: string | null;
};

type ClientsResponse = { items: ClientRecord[] };

type AccountSummaryItem = {
  platform: string;
  connected_count: number;
  last_import_at?: string | null;
};

type AccountSummaryResponse = { items: AccountSummaryItem[] };

type GoogleAccount = { id: string; name: string };

type GoogleAccountsResponse = {
  items: GoogleAccount[];
  count: number;
  last_import_at?: string | null;
};

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

function formatDate(value?: string | null): string {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString();
}

export default function AgencyAccountsPage() {
  const [clients, setClients] = useState<ClientRecord[]>([]);
  const [summary, setSummary] = useState<AccountSummaryItem[]>([]);
  const [selectedPlatform, setSelectedPlatform] = useState<string>("google_ads");
  const [googleAccounts, setGoogleAccounts] = useState<GoogleAccount[]>([]);
  const [attachStatus, setAttachStatus] = useState("");

  async function loadClients() {
    const payload = await apiRequest<ClientsResponse>("/clients");
    setClients(payload.items);
  }

  async function loadAccountSummary() {
    const payload = await apiRequest<AccountSummaryResponse>("/clients/accounts/summary");
    setSummary(payload.items);
  }

  async function loadGoogleAccounts() {
    const payload = await apiRequest<GoogleAccountsResponse>("/clients/accounts/google");
    setGoogleAccounts(payload.items);
  }

  useEffect(() => {
    void loadClients();
    void loadAccountSummary();
    void loadGoogleAccounts();
  }, []);

  async function attachGoogleAccount(clientId: number, customerId: string) {
    setAttachStatus("");
    try {
      await apiRequest(`/clients/${clientId}/attach-google-account`, {
        method: "POST",
        body: JSON.stringify({ customer_id: customerId }),
      });
      setAttachStatus(`Contul ${customerId} a fost atașat clientului #${clientId}.`);
      await loadClients();
    } catch (err) {
      setAttachStatus(err instanceof Error ? err.message : "Nu am putut atașa contul Google");
    }
  }

  const selectedSummary = useMemo(() => summary.find((item) => item.platform === selectedPlatform), [summary, selectedPlatform]);

  return (
    <ProtectedPage>
      <AppShell title="Agency Accounts">
        <main className="p-6">
          <section>
            <h2 className="mb-3 text-lg font-semibold text-slate-900">Agency Accounts</h2>
            <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-5">
              {summary.map((item) => {
                const active = item.platform === selectedPlatform;
                return (
                  <button
                    key={item.platform}
                    onClick={() => setSelectedPlatform(item.platform)}
                    className={`wm-card p-4 text-left transition ${active ? "ring-2 ring-indigo-500" : "hover:bg-slate-50"}`}
                  >
                    <p className="text-sm font-semibold text-slate-900">{prettyPlatform(item.platform)}</p>
                    <p className="mt-1 text-xs text-slate-500">Conturi conectate: {item.connected_count}</p>
                    <p className="mt-1 text-xs text-slate-500">Ultimul import: {formatDate(item.last_import_at)}</p>
                  </button>
                );
              })}
            </div>

            {selectedPlatform === "google_ads" ? (
              <div className="mt-4 wm-card p-4">
                <h3 className="text-base font-semibold text-slate-900">Google Accounts disponibile</h3>
                <p className="mt-1 text-xs text-slate-500">Ultimul import: {formatDate(selectedSummary?.last_import_at)}</p>
                {attachStatus ? <p className="mt-2 text-xs text-emerald-700">{attachStatus}</p> : null}
                <div className="mt-3 space-y-2">
                  {googleAccounts.map((account) => (
                    <div key={account.id} className="flex flex-wrap items-center justify-between rounded-md border border-slate-200 px-3 py-2">
                      <div>
                        <p className="text-sm font-medium text-slate-900">{account.name}</p>
                        <p className="text-xs text-slate-500">ID: {account.id}</p>
                      </div>
                      <div className="flex items-center gap-2">
                        <select
                          className="rounded-md border border-slate-300 px-2 py-1 text-sm"
                          onChange={(event) => {
                            const value = Number(event.target.value);
                            if (value > 0) {
                              void attachGoogleAccount(value, account.id);
                              event.currentTarget.value = "";
                            }
                          }}
                          defaultValue=""
                        >
                          <option value="" disabled>
                            Atașează la client...
                          </option>
                          {clients.map((client) => (
                            <option key={client.id} value={client.id}>
                              #{client.id} {client.name}
                            </option>
                          ))}
                        </select>
                      </div>
                    </div>
                  ))}
                  {googleAccounts.length === 0 ? <p className="text-sm text-slate-500">Nu există conturi importate.</p> : null}
                </div>
              </div>
            ) : (
              <div className="mt-4 wm-card p-4 text-sm text-slate-500">Detalierea conturilor este disponibilă momentan pentru Google Ads.</div>
            )}
          </section>
        </main>
      </AppShell>
    </ProtectedPage>
  );
}
