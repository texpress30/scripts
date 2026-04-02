"use client";

import { Loader2, FileDown } from "lucide-react";
import { useFeedManagement } from "@/lib/contexts/FeedManagementContext";
import { useFeedSources } from "@/lib/hooks/useFeedSources";
import { useFeedImports } from "@/lib/hooks/useFeedSources";
import { ImportHistoryTable } from "@/components/feed-management/ImportHistoryTable";

export default function ImportsPage() {
  const { selectedId, isLoading: clientsLoading } = useFeedManagement();
  const { sources, isLoading: sourcesLoading } = useFeedSources(selectedId);

  if (!selectedId && !clientsLoading) {
    return (
      <div className="wm-card flex flex-col items-center justify-center px-6 py-16 text-center">
        <p className="text-sm text-slate-500 dark:text-slate-400">
          Selecteaza un client pentru a vizualiza importurile.
        </p>
      </div>
    );
  }

  if (sourcesLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="h-6 w-6 animate-spin text-slate-400" />
      </div>
    );
  }

  if (sources.length === 0) {
    return (
      <div className="wm-card flex flex-col items-center justify-center px-6 py-16 text-center">
        <FileDown className="mx-auto mb-3 h-10 w-10 text-slate-300 dark:text-slate-600" />
        <p className="text-sm font-medium text-slate-500 dark:text-slate-400">
          Nicio sursa configurata. Adauga o sursa din tab-ul Sources pentru a vedea importurile.
        </p>
      </div>
    );
  }

  return (
    <>
      <div className="mb-6">
        <h2 className="text-lg font-semibold text-slate-900 dark:text-slate-100">Import History</h2>
        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
          Istoricul importurilor pentru toate sursele.
        </p>
      </div>

      <div className="space-y-6">
        {sources.map((source) => (
          <SourceImportsSection key={source.id} sourceId={source.id} sourceName={source.name} subaccountId={selectedId!} />
        ))}
      </div>
    </>
  );
}

function SourceImportsSection({ sourceId, sourceName, subaccountId }: { sourceId: string; sourceName: string; subaccountId: number }) {
  const { imports, isLoading } = useFeedImports(subaccountId, sourceId);

  return (
    <section className="wm-card overflow-hidden">
      <div className="border-b border-slate-200 px-6 py-4 dark:border-slate-700">
        <h3 className="text-sm font-semibold text-slate-900 dark:text-slate-100">{sourceName}</h3>
      </div>
      {isLoading ? (
        <div className="flex items-center justify-center py-8">
          <Loader2 className="h-5 w-5 animate-spin text-slate-400" />
        </div>
      ) : imports.length === 0 ? (
        <div className="px-6 py-6 text-center text-sm text-slate-400">
          Niciun import pentru aceasta sursa.
        </div>
      ) : (
        <ImportHistoryTable imports={imports} />
      )}
    </section>
  );
}
