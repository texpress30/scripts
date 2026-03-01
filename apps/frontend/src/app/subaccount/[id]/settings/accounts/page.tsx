"use client";

import { useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";

import { AppShell } from "@/components/AppShell";
import { ProtectedPage } from "@/components/ProtectedPage";
import { apiRequest } from "@/lib/api";

type ClientItem = { id: number; display_id?: number; name: string };
type Account = { id: string; name: string; client_type?: string; account_manager?: string; currency?: string };
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

export default function SubAccountSettingsPage() {
  const params = useParams<{ id: string }>();
  const clientId = Number(params.id);

  const [details, setDetails] = useState<ClientDetails | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let ignore = false;

    async function load() {
      if (!Number.isFinite(clientId) || clientId <= 0) {
        setError("ID sub-account invalid.");
        setLoading(false);
        return;
      }

      setLoading(true);
      setError("");
      try {
        const clients = await apiRequest<{ items: ClientItem[] }>("/clients");
        const currentClient = clients.items.find((item) => item.id === clientId);
        const displayId = currentClient?.display_id;
        if (!displayId) {
          throw new Error("Nu am găsit sub-account-ul curent în lista de clienți.");
        }

        const payload = await apiRequest<ClientDetails>(`/clients/display/${displayId}`);
        if (!ignore) {
          setDetails(payload);
        }
      } catch (err) {
        if (!ignore) {
          setError(err instanceof Error ? err.message : "Nu am putut încărca conturile sub-account-ului.");
        }
      } finally {
        if (!ignore) {
          setLoading(false);
        }
      }
    }

    void load();
    return () => {
      ignore = true;
    };
  }, [clientId]);

  const title = useMemo(() => {
    if (details?.client.name) {
      return `Sub-account #${clientId} — Conturi (${details.client.name})`;
    }
    return `Sub-account #${clientId} — Conturi`;
  }, [clientId, details?.client.name]);

  return (
    <ProtectedPage>
      <AppShell title={title}>
        <main className="space-y-4 p-6">
          {error ? <p className="rounded-md border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</p> : null}

          <section className="wm-card p-4">
            <h2 className="text-lg font-semibold text-slate-900">Conturi alocate</h2>
            <p className="mt-1 text-sm text-slate-600">Conturile sunt afișate pe platforme pentru acest sub-account, fără selector de client.</p>
          </section>

          {loading ? <p className="text-sm text-slate-500">Se încarcă conturile...</p> : null}

          {!loading && details ? (
            <section className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
              {details.platforms.map((platform) => (
                <article key={platform.platform} className="wm-card p-4">
                  <h3 className="text-base font-semibold text-slate-900">{prettyPlatform(platform.platform)}</h3>
                  <p className="mt-1 text-xs text-slate-500">Activ: {platform.enabled ? "Da" : "Nu"}</p>
                  <p className="text-xs text-slate-500">Conturi atașate: {platform.count}</p>

                  <ul className="mt-2 space-y-2">
                    {platform.accounts.map((account) => (
                      <li key={`${platform.platform}:${account.id}`} className="rounded-md border border-slate-100 p-2 text-sm text-slate-700">
                        <div>
                          {account.name} <span className="text-xs text-slate-500">({account.id})</span>
                        </div>

                        <div className="mt-2 space-y-1 text-xs">
                          <div className="flex items-center gap-2">
                            <span className="text-slate-500">Tip client:</span>
                            <span className="font-medium text-slate-700">{account.client_type ?? details.client.client_type ?? "lead"}</span>
                          </div>

                          <div className="flex items-center gap-2">
                            <span className="text-slate-500">Responsabil:</span>
                            <span className="font-medium text-slate-700">{account.account_manager ?? details.client.account_manager ?? "—"}</span>
                          </div>

                          <div className="flex items-center gap-2">
                            <span className="text-slate-500">Monedă:</span>
                            <span className="font-medium text-slate-700">{account.currency ?? details.client.currency ?? "USD"}</span>
                          </div>
                        </div>
                      </li>
                    ))}

                    {platform.accounts.length === 0 ? <li className="text-sm text-slate-400">Fără conturi atașate.</li> : null}
                  </ul>
                </article>
              ))}
            </section>
          ) : null}
        </main>
      </AppShell>
    </ProtectedPage>
  );
}
