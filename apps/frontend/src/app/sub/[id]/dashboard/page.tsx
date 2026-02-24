"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import { AppShell } from "@/components/AppShell";
import { ProtectedPage } from "@/components/ProtectedPage";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { apiRequest } from "@/lib/api";
import {
  isPinterestIntegrationEnabled,
  isSnapchatIntegrationEnabled,
  isTikTokIntegrationEnabled,
} from "@/lib/featureFlags";
import { getCurrentRole, isReadOnlyRole } from "@/lib/session";

type DashboardResponse = {
  client_id: number;
  totals: { spend: number; conversions: number; roas: number };
  platforms: {
    google_ads: { spend: number; conversions: number; roas?: number; is_synced?: boolean };
    meta_ads: { spend: number; conversions: number; roas?: number; is_synced?: boolean };
    tiktok_ads?: { spend: number; conversions: number; roas?: number; is_synced?: boolean };
    pinterest_ads?: { spend: number; conversions: number; roas?: number; is_synced?: boolean };
    snapchat_ads?: { spend: number; conversions: number; roas?: number; is_synced?: boolean };
  };
};

export default function SubDashboardPage() {
  const params = useParams<{ id: string }>();
  const clientId = Number(params.id);
  const role = getCurrentRole();
  const readOnly = isReadOnlyRole(role);
  const tiktokEnabled = isTikTokIntegrationEnabled();
  const pinterestEnabled = isPinterestIntegrationEnabled();
  const snapchatEnabled = isSnapchatIntegrationEnabled();

  const [data, setData] = useState<DashboardResponse | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<"google" | "meta" | "tiktok" | "pinterest" | "snapchat" | null>(null);

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

  async function sync(channel: "google" | "meta" | "tiktok" | "pinterest" | "snapchat") {
    setBusy(channel);
    setError("");
    try {
      const path =
        channel === "google"
          ? `/integrations/google-ads/${clientId}/sync`
          : channel === "meta"
            ? `/integrations/meta-ads/${clientId}/sync`
            : channel === "tiktok"
              ? `/integrations/tiktok-ads/${clientId}/sync`
              : channel === "pinterest"
                ? `/integrations/pinterest-ads/${clientId}/sync`
                : `/integrations/snapchat-ads/${clientId}/sync`;
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
  const pinterest = data?.platforms.pinterest_ads ?? { spend: 0, conversions: 0, roas: 0 };
  const snapchat = data?.platforms.snapchat_ads ?? { spend: 0, conversions: 0, roas: 0 };

  return (
    <ProtectedPage>
      <AppShell title={`Sub-account Dashboard #${clientId}`}>
        <div className="mb-4 flex items-center gap-4 text-sm">
          <Link href={`/sub/${clientId}/campaigns`} className="text-indigo-600 hover:underline">Campaigns</Link>
          <Link href={`/sub/${clientId}/rules`} className="text-indigo-600 hover:underline">Rules</Link>
          <Link href={`/sub/${clientId}/creative`} className="text-indigo-600 hover:underline">Creative</Link>
          <Link href={`/sub/${clientId}/recommendations`} className="text-indigo-600 hover:underline">Recommendations</Link>
        </div>

        {error ? <p className="mb-4 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p> : null}

        <section className="grid grid-cols-1 gap-4 md:grid-cols-3">
          <MetricCard title="Spend" value={loading ? "..." : `$${totals.spend.toLocaleString()}`} />
          <MetricCard title="Conversii" value={loading ? "..." : totals.conversions.toLocaleString()} />
          <MetricCard title="ROAS" value={loading ? "..." : totals.roas.toFixed(2)} />
        </section>

        <section className="mt-6 grid grid-cols-1 gap-4 lg:grid-cols-5">
          <IntegrationCard
            title="Google Ads"
            spend={google.spend}
            conversions={google.conversions}
            loading={loading}
            synced={Boolean(google.is_synced)}
            buttonLabel={busy === "google" ? "Sync..." : "Sync Google"}
            disabled={readOnly || busy !== null}
            onSync={() => sync("google")}
          />
          <IntegrationCard
            title="Meta Ads"
            spend={meta.spend}
            conversions={meta.conversions}
            loading={loading}
            synced={Boolean(meta.is_synced)}
            buttonLabel={busy === "meta" ? "Sync..." : "Sync Meta"}
            disabled={readOnly || busy !== null}
            onSync={() => sync("meta")}
          />
          {tiktokEnabled ? (
            <IntegrationCard
              title="TikTok Ads"
              spend={tiktok.spend}
              conversions={tiktok.conversions}
              loading={loading}
              synced={Boolean(tiktok.is_synced)}
              buttonLabel={busy === "tiktok" ? "Sync..." : "Sync TikTok"}
              disabled={readOnly || busy !== null}
              onSync={() => sync("tiktok")}
            />
          ) : null}
          {pinterestEnabled ? (
            <IntegrationCard
              title="Pinterest Ads"
              spend={pinterest.spend}
              conversions={pinterest.conversions}
              loading={loading}
              synced={Boolean(pinterest.is_synced)}
              buttonLabel={busy === "pinterest" ? "Sync..." : "Sync Pinterest"}
              disabled={readOnly || busy !== null}
              onSync={() => sync("pinterest")}
            />
          ) : null}
          {snapchatEnabled ? (
            <IntegrationCard
              title="Snapchat Ads"
              spend={snapchat.spend}
              conversions={snapchat.conversions}
              loading={loading}
              synced={Boolean(snapchat.is_synced)}
              buttonLabel={busy === "snapchat" ? "Sync..." : "Sync Snapchat"}
              disabled={readOnly || busy !== null}
              onSync={() => sync("snapchat")}
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
  loading,
  synced,
}: {
  title: string;
  spend: number;
  conversions: number;
  buttonLabel: string;
  disabled: boolean;
  onSync: () => void;
  loading: boolean;
  synced: boolean;
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
      </CardHeader>
      <CardContent>
        <p className="text-sm text-slate-600">Status: {loading ? "Loading..." : synced ? "Synced" : "No data"}</p>
        <p className="text-sm text-slate-600">Spend: {loading ? "..." : `$${spend.toLocaleString()}`}</p>
        <p className="text-sm text-slate-600">Conversii: {loading ? "..." : conversions.toLocaleString()}</p>
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
