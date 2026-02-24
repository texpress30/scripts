"use client";

import { useEffect, useMemo, useState } from "react";

import { AppShell } from "@/components/AppShell";
import { ProtectedPage } from "@/components/ProtectedPage";
import { apiRequest } from "@/lib/api";

type ClientItem = {
  id: number;
  name: string;
  owner_email: string;
};

type ClientsResponse = { items: ClientItem[] };
type IntegrationStatus = { platform: string; status: string };

type DashboardResponse = {
  totals: { spend: number; conversions: number; roas: number };
};

export default function AgencyDashboardPage() {
  const [clients, setClients] = useState<ClientItem[]>([]);
  const [googleStatus, setGoogleStatus] = useState<IntegrationStatus | null>(null);
  const [metaStatus, setMetaStatus] = useState<IntegrationStatus | null>(null);
  const [tiktokStatus, setTiktokStatus] = useState<IntegrationStatus | null>(null);
  const [pinterestStatus, setPinterestStatus] = useState<IntegrationStatus | null>(null);
  const [snapchatStatus, setSnapchatStatus] = useState<IntegrationStatus | null>(null);
  const [totals, setTotals] = useState({ spend: 0, conversions: 0, roas: 0 });
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let ignore = false;

    async function loadAgencyDashboard() {
      setLoading(true);
      setError("");

      try {
        const clientsResponse = await apiRequest<ClientsResponse>("/clients");
        if (ignore) return;

        setClients(clientsResponse.items);

        const [google, meta, tiktok, pinterest, snapchat] = await Promise.all([
          apiRequest<IntegrationStatus>("/integrations/google-ads/status"),
          apiRequest<IntegrationStatus>("/integrations/meta-ads/status"),
          apiRequest<IntegrationStatus>("/integrations/tiktok-ads/status"),
          apiRequest<IntegrationStatus>("/integrations/pinterest-ads/status"),
          apiRequest<IntegrationStatus>("/integrations/snapchat-ads/status"),
        ]);

        if (ignore) return;
        setGoogleStatus(google);
        setMetaStatus(meta);
        setTiktokStatus(tiktok);
        setPinterestStatus(pinterest);
        setSnapchatStatus(snapchat);

        const dashboardItems = await Promise.all(
          clientsResponse.items.map((client) => apiRequest<DashboardResponse>(`/dashboard/${client.id}`))
        );

        if (ignore) return;

        const aggregated = dashboardItems.reduce(
          (acc, item) => {
            acc.spend += item.totals.spend;
            acc.conversions += item.totals.conversions;
            return acc;
          },
          { spend: 0, conversions: 0 }
        );

        setTotals({
          spend: Number(aggregated.spend.toFixed(2)),
          conversions: aggregated.conversions,
          roas: aggregated.spend > 0 ? Number((aggregated.conversions / aggregated.spend).toFixed(2)) : 0,
        });
      } catch (err) {
        if (!ignore) {
          setError(err instanceof Error ? err.message : "Nu am putut încărca dashboard-ul agency");
        }
      } finally {
        if (!ignore) setLoading(false);
      }
    }

    void loadAgencyDashboard();
    return () => {
      ignore = true;
    };
  }, []);

  const integrationSummary = useMemo(
    () => [
      { label: "Google Ads", status: googleStatus?.status ?? "unknown" },
      { label: "Meta Ads", status: metaStatus?.status ?? "unknown" },
      { label: "TikTok Ads", status: tiktokStatus?.status ?? "unknown" },
      { label: "Pinterest Ads", status: pinterestStatus?.status ?? "unknown" },
      { label: "Snapchat Ads", status: snapchatStatus?.status ?? "unknown" },
    ],
    [
      googleStatus?.status,
      metaStatus?.status,
      tiktokStatus?.status,
      pinterestStatus?.status,
      snapchatStatus?.status,
    ]
  );

  return (
    <ProtectedPage>
      <AppShell title="Agency Dashboard">
        {error ? <p className="mb-4 text-sm text-red-600">{error}</p> : null}

        <section className="grid grid-cols-1 gap-4 md:grid-cols-4">
          <Card title="Clienți activi" value={loading ? "..." : String(clients.length)} />
          <Card title="Spend total" value={loading ? "..." : `$${totals.spend.toLocaleString()}`} />
          <Card title="Conversii total" value={loading ? "..." : totals.conversions.toLocaleString()} />
          <Card title="ROAS agregat" value={loading ? "..." : totals.roas.toFixed(2)} />
        </section>

        <section className="mt-6 grid grid-cols-1 gap-4 lg:grid-cols-2">
          <article className="wm-card p-4">
            <h3 className="text-sm font-semibold text-slate-900">Integration health</h3>
            <ul className="mt-3 space-y-2 text-sm text-slate-600">
              {integrationSummary.map((item) => (
                <li key={item.label} className="flex items-center justify-between">
                  <span>{item.label}</span>
                  <span className="font-medium text-slate-900">{item.status}</span>
                </li>
              ))}
            </ul>
          </article>

          <article className="wm-card p-4">
            <h3 className="text-sm font-semibold text-slate-900">Top clienți (după spend)</h3>
            <ul className="mt-3 space-y-2 text-sm text-slate-600">
              {clients.slice(0, 5).map((client) => (
                <li key={client.id} className="flex items-center justify-between">
                  <span>{client.name}</span>
                  <span className="text-slate-500">#{client.id}</span>
                </li>
              ))}
              {!loading && clients.length === 0 ? <li>Nu există clienți.</li> : null}
            </ul>
          </article>
        </section>
      </AppShell>
    </ProtectedPage>
  );
}

function Card({ title, value }: { title: string; value: string }) {
  return (
    <article className="wm-card p-4">
      <p className="text-xs uppercase tracking-wide text-slate-500">{title}</p>
      <p className="mt-2 text-2xl font-semibold text-slate-900">{value}</p>
    </article>
  );
}
