"use client";

import Link from "next/link";
import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { Plus, Loader2, CheckCircle2, X } from "lucide-react";
import { useFeedSources } from "@/lib/hooks/useFeedSources";
import { useFeedManagement } from "@/lib/contexts/FeedManagementContext";
import { FeedSourceCard } from "@/components/feed-management/FeedSourceCard";

type ImportResultBanner = {
  kind: "success" | "error";
  message: string;
};

function FeedSourcesPageBody() {
  const searchParams = useSearchParams();
  const { selectedId, isLoading: clientsLoading } = useFeedManagement();
  const {
    sources,
    isLoading,
    error,
    deleteSource,
    syncSource,
    importShopifySource,
    reconnectShopifySource,
    syncingIds,
  } = useFeedSources(selectedId);

  const [shopifyConnected, setShopifyConnected] = useState(false);
  const [importingId, setImportingId] = useState<string | null>(null);
  const [reconnectingId, setReconnectingId] = useState<string | null>(null);
  const [importResult, setImportResult] = useState<ImportResultBanner | null>(null);

  useEffect(() => {
    if (searchParams.get("shopify_connected") === "1") {
      setShopifyConnected(true);
    }
  }, [searchParams]);

  function handleDelete(id: string) {
    if (!window.confirm("Sigur vrei să ștergi această sursă?")) return;
    void deleteSource(id);
  }

  function handleSync(id: string) {
    void syncSource(id);
  }

  async function handleImport(id: string) {
    setImportingId(id);
    setImportResult(null);
    try {
      const result = await importShopifySource(id);
      setImportResult({
        kind: result.status === "completed" ? "success" : "error",
        message:
          result.status === "completed"
            ? `Importate ${result.imported} produse${result.deactivated ? ` (${result.deactivated} dezactivate)` : ""}.`
            : result.message ?? `Import finalizat cu status ${result.status}.`,
      });
    } catch (err) {
      setImportResult({
        kind: "error",
        message: err instanceof Error ? err.message : "Importul a eșuat.",
      });
    } finally {
      setImportingId(null);
    }
  }

  async function handleReconnect(id: string) {
    setReconnectingId(id);
    try {
      const source = sources.find((s) => s.id === id);
      const result = await reconnectShopifySource(id);
      sessionStorage.setItem(
        "shopify_oauth_context",
        JSON.stringify({
          source_id: id,
          client_id: selectedId,
          shop_domain: source?.shop_domain ?? undefined,
          state: result.state,
          return_path: "/agency/feed-management/sources",
        }),
      );
      window.location.href = result.authorize_url;
    } catch (err) {
      setImportResult({
        kind: "error",
        message: err instanceof Error ? err.message : "Reconectarea a eșuat.",
      });
      setReconnectingId(null);
    }
  }

  return (
    <>
      <div className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-xl font-semibold text-slate-900 dark:text-slate-100">Feed Sources</h1>
          <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
            Gestionează sursele de produse conectate la platformă.
          </p>
        </div>
        <Link href="/agency/feed-management/sources/new" className="wm-btn-primary gap-2">
          <Plus className="h-4 w-4" />
          Add New Source
        </Link>
      </div>

      {shopifyConnected ? (
        <div className="mb-4 flex items-center justify-between gap-3 rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700 dark:border-emerald-800 dark:bg-emerald-900/20 dark:text-emerald-400">
          <span className="flex items-center gap-2">
            <CheckCircle2 className="h-4 w-4" />
            Sursa Shopify a fost conectată cu succes.
          </span>
          <button type="button" onClick={() => setShopifyConnected(false)} className="text-emerald-700 hover:opacity-70 dark:text-emerald-400">
            <X className="h-4 w-4" />
          </button>
        </div>
      ) : null}

      {importResult ? (
        <div
          className={`mb-4 flex items-center justify-between gap-3 rounded-lg border px-4 py-3 text-sm ${
            importResult.kind === "success"
              ? "border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-800 dark:bg-emerald-900/20 dark:text-emerald-400"
              : "border-red-200 bg-red-50 text-red-700 dark:border-red-800 dark:bg-red-900/20 dark:text-red-400"
          }`}
        >
          <span>{importResult.message}</span>
          <button type="button" onClick={() => setImportResult(null)} className="hover:opacity-70">
            <X className="h-4 w-4" />
          </button>
        </div>
      ) : null}

      {!selectedId && !clientsLoading ? (
        <div className="wm-card flex flex-col items-center justify-center px-6 py-16 text-center">
          <p className="text-sm text-slate-500 dark:text-slate-400">
            Selectează un client pentru a vizualiza sursele de date.
          </p>
        </div>
      ) : error ? (
        <p className="mb-4 text-red-600">{error}</p>
      ) : isLoading ? (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="h-6 w-6 animate-spin text-slate-400" />
        </div>
      ) : sources.length === 0 ? (
        <div className="wm-card flex flex-col items-center justify-center px-6 py-16 text-center">
          <div className="mb-3 rounded-full bg-slate-100 p-4 dark:bg-slate-800">
            <Plus className="h-8 w-8 text-slate-400" />
          </div>
          <h2 className="text-lg font-medium text-slate-700 dark:text-slate-300">
            Nu ai surse configurate
          </h2>
          <p className="mb-4 mt-1 max-w-sm text-sm text-slate-500 dark:text-slate-400">
            Conectează o sursă de produse pentru a începe importul de date în platformă.
          </p>
          <Link href="/agency/feed-management/sources/new" className="wm-btn-primary gap-2">
            <Plus className="h-4 w-4" />
            Add New Source
          </Link>
        </div>
      ) : (
        <>
          {syncingIds.size > 0 && (
            <div className="mb-4 flex items-center gap-2 rounded-lg border border-indigo-200 bg-indigo-50 px-4 py-3 text-sm text-indigo-700 dark:border-indigo-800 dark:bg-indigo-900/20 dark:text-indigo-300">
              <Loader2 className="h-4 w-4 animate-spin" />
              Syncing in progress... Products are being imported from source.
            </div>
          )}
          <section className="wm-card">
            <div className="overflow-x-auto overflow-y-visible">
              <table className="min-w-full text-sm">
                <thead className="bg-slate-100 text-left text-slate-600 dark:bg-slate-800 dark:text-slate-400">
                  <tr>
                    <th className="px-4 py-3">Name</th>
                    <th className="px-4 py-3">Platform</th>
                    <th className="px-4 py-3">Catalog</th>
                    <th className="px-4 py-3">Status</th>
                    <th className="px-4 py-3">Last Sync</th>
                    <th className="px-4 py-3">Products</th>
                    <th className="px-4 py-3">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {sources.map((source) => (
                    <FeedSourceCard
                      key={source.id}
                      source={source}
                      onSync={handleSync}
                      onDelete={handleDelete}
                      onImport={handleImport}
                      onReconnect={handleReconnect}
                      isSyncing={syncingIds.has(source.id)}
                      isImporting={importingId === source.id}
                      isReconnecting={reconnectingId === source.id}
                    />
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        </>
      )}
    </>
  );
}

export default function FeedSourcesPage() {
  return (
    <Suspense fallback={null}>
      <FeedSourcesPageBody />
    </Suspense>
  );
}
