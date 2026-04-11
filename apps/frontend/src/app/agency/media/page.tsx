"use client";

import { useEffect, useState } from "react";
import { Loader2 } from "lucide-react";

import { AppShell } from "@/components/AppShell";
import { MediaLibraryView } from "@/components/media/MediaLibraryView";
import { ProtectedPage } from "@/components/ProtectedPage";
import { apiRequest } from "@/lib/api";

type CompanySettingsWithStorage = {
  logo_storage_client_id?: number | null;
};

export default function AgencyMediaStoragePage() {
  const [storageClientId, setStorageClientId] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      setError("");
      try {
        const settings = await apiRequest<CompanySettingsWithStorage>("/company/settings", { requireAuth: true });
        if (cancelled) return;
        const id = Number(settings.logo_storage_client_id);
        if (Number.isFinite(id) && id > 0) {
          setStorageClientId(id);
        } else {
          setError(
            "Nu am putut identifica contul de stocare al agenției. Încarcă un logo în Setări → Company pentru a inițializa spațiul de stocare.",
          );
        }
      } catch (err) {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : "Nu am putut încărca spațiul de stocare al agenției.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <ProtectedPage>
      <AppShell title={null}>
        {loading ? (
          <div className="flex items-center justify-center py-10 text-sm text-slate-500">
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            Se încarcă spațiul de stocare al agenției...
          </div>
        ) : error ? (
          <div className="wm-card p-5">
            <p className="text-sm text-red-600">{error}</p>
          </div>
        ) : storageClientId ? (
          <MediaLibraryView clientId={storageClientId} showHeader />
        ) : null}
      </AppShell>
    </ProtectedPage>
  );
}
