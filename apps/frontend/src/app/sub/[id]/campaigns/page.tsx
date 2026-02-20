"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";

import { AppShell } from "@/components/AppShell";
import { ProtectedPage } from "@/components/ProtectedPage";
import { apiRequest } from "@/lib/api";
import { isTikTokIntegrationEnabled } from "@/lib/featureFlags";
import { getCurrentRole, isReadOnlyRole } from "@/lib/session";

export default function SubCampaignsPage() {
  const params = useParams<{ id: string }>();
  const clientId = Number(params.id);
  const role = getCurrentRole();
  const readOnly = isReadOnlyRole(role);
  const tiktokEnabled = isTikTokIntegrationEnabled();

  const [result, setResult] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState<string | null>(null);

  async function action(name: "google" | "meta" | "tiktok" | "evaluate") {
    setError("");
    setResult("");
    setBusy(name);
    try {
      if (name === "google") await apiRequest(`/integrations/google-ads/${clientId}/sync`, { method: "POST" });
      if (name === "meta") await apiRequest(`/integrations/meta-ads/${clientId}/sync`, { method: "POST" });
      if (name === "tiktok") await apiRequest(`/integrations/tiktok-ads/${clientId}/sync`, { method: "POST" });
      if (name === "evaluate") await apiRequest(`/rules/${clientId}/evaluate`, { method: "POST" });
      setResult(`Acțiunea ${name} a fost executată.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Acțiunea a eșuat");
    } finally {
      setBusy(null);
    }
  }

  return (
    <ProtectedPage>
      <AppShell title={`Sub Campaigns · #${clientId}`}>
        <div className="mb-4 flex items-center gap-3 text-sm">
          <Link href={`/sub/${clientId}/dashboard`} className="text-indigo-600 hover:underline">Dashboard</Link>
          <Link href={`/sub/${clientId}/rules`} className="text-indigo-600 hover:underline">Rules</Link>
        </div>

        {error ? <p className="mb-3 text-sm text-red-600">{error}</p> : null}
        {result ? <p className="mb-3 text-sm text-emerald-600">{result}</p> : null}

        <section className="grid grid-cols-1 gap-4 md:grid-cols-4">
          <ActionCard
            title="Sync Google"
            disabled={readOnly || busy !== null}
            description="Rulează sincronizare Google Ads pentru acest sub-account"
            onClick={() => action("google")}
          />
          <ActionCard
            title="Sync Meta"
            disabled={readOnly || busy !== null}
            description="Rulează sincronizare Meta Ads pentru acest sub-account"
            onClick={() => action("meta")}
          />
          {tiktokEnabled ? (
            <ActionCard
              title="Sync TikTok (beta)"
              disabled={readOnly || busy !== null}
              description="Rulează endpoint-ul skeleton TikTok (Slice 8.2.1)"
              onClick={() => action("tiktok")}
            />
          ) : null}
          <ActionCard
            title="Evaluate Rules"
            disabled={readOnly || busy !== null}
            description="Evaluează regulile active pentru acest sub-account"
            onClick={() => action("evaluate")}
          />
        </section>
      </AppShell>
    </ProtectedPage>
  );
}

function ActionCard({
  title,
  description,
  onClick,
  disabled,
}: {
  title: string;
  description: string;
  onClick: () => void;
  disabled: boolean;
}) {
  return (
    <article className="wm-card p-4">
      <h3 className="text-sm font-semibold">{title}</h3>
      <p className="mt-2 text-sm text-slate-600">{description}</p>
      <button
        disabled={disabled}
        onClick={onClick}
        className="mt-4 wm-btn-primary disabled:opacity-50"
        title={disabled ? "Disponibil doar pentru roluri cu write" : undefined}
      >
        Execută
      </button>
    </article>
  );
}
