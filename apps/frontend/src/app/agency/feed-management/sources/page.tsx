"use client";

import Link from "next/link";
import { Plus, Loader2 } from "lucide-react";
import { useFeedSources } from "@/lib/hooks/useFeedSources";
import { useFeedManagement } from "@/lib/contexts/FeedManagementContext";
import { FeedSourceCard } from "@/components/feed-management/FeedSourceCard";

export default function FeedSourcesPage() {
  const { selectedId, isLoading: clientsLoading } = useFeedManagement();
  const { sources, isLoading, error, deleteSource, syncSource, syncingIds } = useFeedSources(selectedId);

  function handleDelete(id: string) {
    if (!window.confirm("Sigur vrei să ștergi această sursă?")) return;
    void deleteSource(id);
  }

  function handleSync(id: string) {
    void syncSource(id);
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
                    isSyncing={syncingIds.has(source.id)}
                  />
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </>
  );
}
