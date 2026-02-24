"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";

import { AppShell } from "@/components/AppShell";
import { ProtectedPage } from "@/components/ProtectedPage";
import { apiRequest } from "@/lib/api";
import { getCurrentRole, isReadOnlyRole } from "@/lib/session";

type Recommendation = {
  id: number;
  status: string;
  payload: {
    problema: string;
    cauza: string;
    actiune: string;
    impact_estimat: string;
    incredere: number;
    risc: string;
  };
  updated_at: string;
};

export default function SubRecommendationsPage() {
  const params = useParams<{ id: string }>();
  const clientId = Number(params.id);
  const role = getCurrentRole();
  const readOnly = isReadOnlyRole(role);

  const [items, setItems] = useState<Recommendation[]>([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function load() {
    setError("");
    try {
      const result = await apiRequest<{ items: Recommendation[] }>(`/ai/recommendations/${clientId}/list`);
      setItems(result.items);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Nu pot încărca recomandările");
    }
  }

  useEffect(() => {
    if (Number.isFinite(clientId)) void load();
  }, [clientId]);

  async function generate() {
    setBusy(true);
    try {
      await apiRequest(`/ai/recommendations/${clientId}`);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Nu pot genera recomandări");
    } finally {
      setBusy(false);
    }
  }

  async function review(recommendationId: number, action: "approve" | "dismiss") {
    setBusy(true);
    try {
      await apiRequest(`/ai/recommendations/${clientId}/${recommendationId}/review`, {
        method: "POST",
        body: JSON.stringify({ action, snooze_days: 3 }),
      });
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Nu pot actualiza recomandarea");
    } finally {
      setBusy(false);
    }
  }

  return (
    <ProtectedPage>
      <AppShell title={`Sub Recommendations · #${clientId}`}>
        {error ? <p className="mb-3 text-sm text-red-600">{error}</p> : null}

        <button
          onClick={generate}
          disabled={readOnly || busy}
          className="wm-btn-primary mb-4 disabled:opacity-50"
          title={readOnly ? "Read-only" : undefined}
        >
          Generate recommendation
        </button>

        <div className="space-y-3">
          {items.map((item) => (
            <div key={item.id} className="wm-card p-4">
              <div className="mb-2 flex items-center justify-between">
                <span className="text-xs uppercase text-slate-500">#{item.id} · {item.status}</span>
                <span className="text-xs text-slate-400">{new Date(item.updated_at).toLocaleString()}</span>
              </div>
              <p className="text-sm font-semibold">Problema: {item.payload.problema}</p>
              <p className="text-sm">Cauza: {item.payload.cauza}</p>
              <p className="text-sm">Actiune: {item.payload.actiune}</p>

              <div className="mt-3 flex gap-2">
                <button
                  onClick={() => review(item.id, "approve")}
                  disabled={readOnly || busy}
                  className="rounded bg-emerald-600 px-3 py-1.5 text-xs text-white disabled:opacity-50"
                  title={readOnly ? "Read-only" : undefined}
                >
                  Approve
                </button>
                <button
                  onClick={() => review(item.id, "dismiss")}
                  disabled={readOnly || busy}
                  className="rounded bg-rose-600 px-3 py-1.5 text-xs text-white disabled:opacity-50"
                  title={readOnly ? "Read-only" : undefined}
                >
                  Dismiss
                </button>
              </div>
            </div>
          ))}

          {items.length === 0 ? <div className="wm-card p-4 text-sm text-slate-500">Nu există recomandări.</div> : null}
        </div>
      </AppShell>
    </ProtectedPage>
  );
}
