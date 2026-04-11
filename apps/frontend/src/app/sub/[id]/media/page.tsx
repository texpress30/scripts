"use client";

import { useParams } from "next/navigation";

import { AppShell } from "@/components/AppShell";
import { MediaLibraryView } from "@/components/media/MediaLibraryView";
import { ProtectedPage } from "@/components/ProtectedPage";

export default function SubMediaStoragePage() {
  const params = useParams<{ id: string }>();
  const clientId = Number(params?.id);

  return (
    <ProtectedPage>
      <AppShell title="Stocare Media">
        {Number.isFinite(clientId) && clientId > 0 ? (
          <MediaLibraryView clientId={clientId} />
        ) : (
          <div className="wm-card p-5">
            <p className="text-sm text-slate-500 dark:text-slate-400">
              Sub-account invalid. Întoarce-te în panoul de control și alege un sub-account valid.
            </p>
          </div>
        )}
      </AppShell>
    </ProtectedPage>
  );
}
