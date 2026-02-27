"use client";

import { useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";

import { AppShell } from "@/components/AppShell";
import { ProtectedPage } from "@/components/ProtectedPage";
import { apiRequest } from "@/lib/api";

type Account = { id: string; name: string };
type PlatformInfo = { platform: string; enabled: boolean; count: number; accounts: Account[] };
type ClientDetails = {
  client: { id: number; display_id?: number; name: string; owner_email: string; google_customer_id?: string | null };
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
  const clientId = Number(params.id);
  const [data, setData] = useState<ClientDetails | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    async function load() {
      setError("");
      try {
        const payload = await apiRequest<ClientDetails>(`/clients/${clientId}`);
        setData(payload);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Nu am putut încărca detaliile clientului.");
      }
    }
    if (clientId > 0) {
      void load();
    }
  }, [clientId]);

  const title = useMemo(() => (data ? `Client: ${data.client.name}` : "Client details"), [data]);

  return (
    <ProtectedPage>
      <AppShell title={title}>
        <main className="space-y-4 p-6">
          {error ? <p className="text-sm text-red-600">{error}</p> : null}
          {data ? (
            <>
              <section className="wm-card p-4">
                <p className="text-sm text-slate-500">Client #{data.client.display_id ?? data.client.id}</p>
                <h2 className="text-xl font-semibold text-slate-900">{data.client.name}</h2>
                <p className="text-sm text-slate-600">Owner: {data.client.owner_email}</p>
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
