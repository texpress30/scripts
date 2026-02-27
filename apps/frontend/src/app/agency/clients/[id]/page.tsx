"use client";

import { useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";

import { AppShell } from "@/components/AppShell";
import { ProtectedPage } from "@/components/ProtectedPage";
import { apiRequest } from "@/lib/api";

type Account = { id: string; name: string };
type PlatformInfo = { platform: string; enabled: boolean; count: number; accounts: Account[] };
type ClientDetails = {
  client: {
    id: number;
    display_id?: number;
    name: string;
    owner_email: string;
    client_type?: string;
    account_manager?: string;
  };
  platforms: PlatformInfo[];
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

export default function AgencyClientDetailsPage() {
  const params = useParams<{ id: string }>();
  const displayId = Number(params.id);
  const [data, setData] = useState<ClientDetails | null>(null);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const [clientType, setClientType] = useState("lead");
  const [accountManager, setAccountManager] = useState("");

  async function load() {
    setError("");
    try {
      const payload = await apiRequest<ClientDetails>(`/clients/display/${displayId}`);
      setData(payload);
      setClientType(payload.client.client_type ?? "lead");
      setAccountManager(payload.client.account_manager ?? "");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Nu am putut încărca detaliile clientului.");
    }
  }

  useEffect(() => {
    if (displayId > 0) {
      void load();
    }
  }, [displayId]);

  async function saveProfile() {
    setSaving(true);
    setError("");
    try {
      const payload = await apiRequest<ClientDetails>(`/clients/display/${displayId}`, {
        method: "PATCH",
        body: JSON.stringify({ client_type: clientType, account_manager: accountManager }),
      });
      setData(payload);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Nu am putut salva profilul clientului.");
    } finally {
      setSaving(false);
    }
  }

  const title = useMemo(() => (data ? `Client: ${data.client.name}` : `Client #${displayId}`), [data, displayId]);

  return (
    <ProtectedPage>
      <AppShell title={title}>
        <main className="space-y-4 p-6">
          {error ? <p className="text-sm text-red-600">{error}</p> : null}
          {data ? (
            <>
              <section className="wm-card p-4">
                <p className="text-sm text-slate-500">Client #{data.client.display_id ?? displayId}</p>
                <h2 className="text-xl font-semibold text-slate-900">{data.client.name}</h2>
                <p className="text-sm text-slate-600">Owner: {data.client.owner_email}</p>

                <div className="mt-4 grid grid-cols-1 gap-3 md:grid-cols-2">
                  <label className="text-sm text-slate-700">
                    Tip client
                    <select value={clientType} onChange={(e) => setClientType(e.target.value)} className="mt-1 w-full rounded-md border border-slate-300 px-2 py-2">
                      <option value="lead">lead</option>
                      <option value="e-commerce">e-commerce</option>
                      <option value="programmatic">programmatic</option>
                    </select>
                  </label>

                  <label className="text-sm text-slate-700">
                    Responsabil cont
                    <input
                      value={accountManager}
                      onChange={(e) => setAccountManager(e.target.value)}
                      className="mt-1 w-full rounded-md border border-slate-300 px-2 py-2"
                      placeholder="Nume membru echipă"
                    />
                  </label>
                </div>

                <button className="wm-btn-primary mt-3" onClick={() => void saveProfile()} disabled={saving}>
                  {saving ? "Se salvează..." : "Salvează profil client"}
                </button>
              </section>

              <section className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
                {data.platforms.map((platform) => (
                  <article key={platform.platform} className="wm-card p-4">
                    <h3 className="text-base font-semibold text-slate-900">{prettyPlatform(platform.platform)}</h3>
                    <p className="mt-1 text-xs text-slate-500">Activ: {platform.enabled ? "Da" : "Nu"}</p>
                    <p className="text-xs text-slate-500">Conturi atașate: {platform.count}</p>
                    <ul className="mt-2 space-y-1">
                      {platform.accounts.map((account) => (
                        <li key={account.id} className="text-sm text-slate-700">
                          {account.name} <span className="text-xs text-slate-500">({account.id})</span>
                        </li>
                      ))}
                      {platform.accounts.length === 0 ? <li className="text-sm text-slate-400">Fără conturi atașate.</li> : null}
                    </ul>
                  </article>
                ))}
              </section>
            </>
          ) : null}
        </main>
      </AppShell>
    </ProtectedPage>
  );
}
