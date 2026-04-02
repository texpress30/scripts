"use client";

import { Loader2, GitBranch, Plus } from "lucide-react";
import Link from "next/link";
import { useFeedSources } from "@/lib/hooks/useFeedSources";
import { useFeedManagement } from "@/lib/contexts/FeedManagementContext";
import { SourceMappingsCard } from "@/components/feed-management/SourceMappingsCard";

export default function FieldMappingPage() {
  const { selectedId, isLoading: clientsLoading } = useFeedManagement();
  const { sources, isLoading: sourcesLoading } = useFeedSources(selectedId);

  const loading = clientsLoading || sourcesLoading;

  return (
    <>
      <div className="mb-6">
        <h2 className="text-lg font-semibold text-slate-900 dark:text-slate-100">Field Mapping</h2>
        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
          Configureaza cum se mapeaza campurile surselor la schema catalogului.
        </p>
      </div>

      {!selectedId && !clientsLoading ? (
        <div className="wm-card flex flex-col items-center justify-center px-6 py-16 text-center">
          <p className="text-sm text-slate-500 dark:text-slate-400">
            Selecteaza un client pentru a vizualiza maparile.
          </p>
        </div>
      ) : loading ? (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="h-6 w-6 animate-spin text-slate-400" />
        </div>
      ) : sources.length === 0 ? (
        <div className="wm-card flex flex-col items-center justify-center px-6 py-16 text-center">
          <GitBranch className="mx-auto mb-3 h-10 w-10 text-slate-300 dark:text-slate-600" />
          <p className="text-sm font-medium text-slate-500 dark:text-slate-400">
            Nicio sursa configurata pentru acest client.
          </p>
          <p className="mt-1 text-xs text-slate-400 dark:text-slate-500">
            Adauga o sursa din tab-ul Sources pentru a configura maparile.
          </p>
          <Link href="/agency/feed-management/sources/new" className="wm-btn-primary mt-4 gap-2 text-sm">
            <Plus className="h-4 w-4" />
            Add Source
          </Link>
        </div>
      ) : (
        <div className="space-y-6">
          {sources.map((source) => (
            <SourceMappingsCard
              key={source.id}
              source={source}
              subaccountId={selectedId!}
            />
          ))}
        </div>
      )}
    </>
  );
}
