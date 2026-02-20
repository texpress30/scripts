"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import { AppShell } from "@/components/AppShell";
import { ProtectedPage } from "@/components/ProtectedPage";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { apiRequest } from "@/lib/api";
import { isTikTokIntegrationEnabled } from "@/lib/featureFlags";
import { getCurrentRole, isReadOnlyRole } from "@/lib/session";

type DashboardResponse = {
  client_id: number;
  totals: { spend: number; conversions: number; roas: number };
  platforms: {
    google_ads: { spend: number; conversions: number; roas?: number };
    meta_ads: { spend: number; conversions: number; roas?: number };
    tiktok_ads?: { spend: number; conversions: number; roas?: number };
  };
};

export default function SubDashboardPage() {
  const params = useParams<{ id: string }>();
  const clientId = Number(params.id);
  const role = getCurrentRole();
  const readOnly = isReadOnlyRole(role);
  const tiktokEnabled = isTikTokIntegrationEnabled();

  const [data, setData] = useState<DashboardResponse | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<"google" | "meta" | "tiktok" | null>(null);

  async function load() {
    setLoading(true);
    setError("");
    try {
      const result = await apiRequest<DashboardResponse>(`/dashboard/${clientId}`);
      setData(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Nu pot încărca dashboard-ul clientului");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (Number.isFinite(clientId)) void load();
  }, [clientId]);

  async function sync(channel: "google" | "meta" | "tiktok") {
    setBusy(channel);
    setError("");
    try {
      const path = channel === "google"
        ? `/integrations/google-ads/${clientId}/sync`
        : channel === "meta"
          ? `/integrations/meta-ads/${clientId}/sync`
          : `/integrations/tiktok-ads/${clientId}/sync`;
      await apiRequest(path, { method: "POST" });
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Sync eșuat");
    } finally {
      setBusy(null);
    }
  }

  const totals = data?.totals ?? { spend: 0, conversions: 0, roas: 0 };
  const google = data?.platforms.google_ads ?? { spend: 0, conversions: 0, roas: 0 };
  const meta = data?.platforms.meta_ads ?? { spend: 0, conversions: 0, roas: 0 };
  const tiktok = data?.platforms.tiktok_ads ?? { spend: 0, conversions: 0, roas: 0 };

  return (
    <ProtectedPage>
      <AppShell title={`Sub-account Dashboard #${clientId}`}>
        <div className="mb-4 flex items-center gap-4 text-sm">
          <Link href={`/sub/${clientId}/campaigns`} className="text-indigo-600 hover:underline">Campaigns</Link>
          <Link href={`/sub/${clientId}/rules`} className="text-indigo-600 hover:underline">Rules</Link>
          <Link href={`/sub/${clientId}/creative`} className="text-indigo-600 hover:underline">Creative</Link>
          <Link href={`/sub/${clientId}/recommendations`} className="text-indigo-600 hover:underline">Recommendations</Link>
        </div>

        {error ? <p className="mb-4 text-sm text-red-600">{error}</p> : null}

        <section className="grid grid-cols-1 gap-4 md:grid-cols-3">
          <MetricCard title="Spend" value={loading ? "..." : `$${totals.spend.toLocaleString()}`} />
          <MetricCard title="Conversii" value={loading ? "..." : totals.conversions.toLocaleString()} />
          <MetricCard title="ROAS" value={loading ? "..." : totals.roas.toFixed(2)} />
        </section>

        <section className="mt-6 grid grid-cols-1 gap-4 lg:grid-cols-3">
          <IntegrationCard
            title="Google Ads"
            spend={google.spend}
            conversions={google.conversions}
            buttonLabel={busy === "google" ? "Sync..." : "Sync Google"}
            disabled={readOnly || busy !== null}
            onSync={() => sync("google")}
          />
          <IntegrationCard
            title="Meta Ads"
            spend={meta.spend}
            conversions={meta.conversions}
            buttonLabel={busy === "meta" ? "Sync..." : "Sync Meta"}
            disabled={readOnly || busy !== null}
            onSync={() => sync("meta")}
          />
          {tiktokEnabled ? (
            <IntegrationCard
              title="TikTok Ads"
              spend={tiktok.spend}
              conversions={tiktok.conversions}
              buttonLabel={busy === "tiktok" ? "Sync..." : "Sync TikTok"}
              disabled={readOnly || busy !== null}
              onSync={() => sync("tiktok")}
            />
          ) : null}
        </section>
      </AppShell>
    </ProtectedPage>
  );
}

function MetricCard({ title, value }: { title: string; value: string }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
      </CardHeader>
      <CardContent>
        <p className="text-2xl font-bold text-slate-900">{value}</p>
      </CardContent>
    </Card>
  );
}

function IntegrationCard({
  title,
  spend,
  conversions,
  buttonLabel,
  disabled,
  onSync,
}: {
  title: string;
  spend: number;
  conversions: number;
  buttonLabel: string;
  disabled: boolean;
  onSync: () => void;
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
      </CardHeader>
      <CardContent>
        <p className="text-sm text-slate-600">Spend: ${spend.toLocaleString()}</p>
        <p className="text-sm text-slate-600">Conversii: {conversions.toLocaleString()}</p>
        <button
          disabled={disabled}
          onClick={onSync}
          className="mt-4 h-9 rounded-md bg-indigo-600 px-4 text-sm font-medium text-white hover:bg-indigo-500 disabled:opacity-50"
          title={disabled ? "Read-only sau acțiune în progres" : undefined}
        >
          {buttonLabel}
        </button>
      </CardContent>
    </Card>
  );
}
