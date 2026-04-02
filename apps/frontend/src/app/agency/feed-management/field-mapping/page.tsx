"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Plus, Loader2, ArrowRight, GitBranch } from "lucide-react";
import { useFeedSources } from "@/lib/hooks/useFeedSources";
import { useFeedManagement } from "@/lib/contexts/FeedManagementContext";
import { useFieldMappings } from "@/lib/hooks/useFieldMappings";
import { SourceTypeIcon } from "@/components/feed-management/SourceTypeIcon";

const CATALOG_LABELS: Record<string, string> = {
  product: "Product",
  vehicle: "Vehicle",
  home_listing: "Home Listing",
  hotel: "Hotel",
  flight: "Flight",
  media: "Media",
};

export default function FieldMappingPage() {
  const router = useRouter();
  const { selectedId } = useFeedManagement();
  const { sources, isLoading: sourcesLoading } = useFeedSources(selectedId);
  const [selectedSourceId, setSelectedSourceId] = useState<string>("");
  const { mappings, isLoading: mappingsLoading, createMapping, isCreating } = useFieldMappings(selectedId, selectedSourceId || undefined);

  const selectedSource = sources.find((s) => s.id === selectedSourceId) ?? null;

  async function handleCreateMapping() {
    if (!selectedSourceId) return;
    try {
      const mapping = await createMapping({ source_id: selectedSourceId });
      router.push(`/agency/feed-management/field-mapping/${mapping.id}`);
    } catch {
      // error handled by hook
    }
  }

  return (
    <>
      <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="text-xl font-semibold text-slate-900 dark:text-slate-100">Field Mapping</h1>
          <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
            Configurează cum se mapează câmpurile surselor la schema catalogului.
          </p>
        </div>
      </div>

      {/* Source selector */}
      <div className="wm-card mb-6 p-4">
        <label className="mb-2 block text-xs font-medium text-slate-600 dark:text-slate-400">Feed Source</label>
        {sourcesLoading ? (
          <div className="flex items-center gap-2 py-2">
            <Loader2 className="h-4 w-4 animate-spin text-slate-400" />
            <span className="text-sm text-slate-400">Loading sources...</span>
          </div>
        ) : (
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
            <select
              value={selectedSourceId}
              onChange={(e) => setSelectedSourceId(e.target.value)}
              className="wm-input max-w-md"
            >
              <option value="">-- Selectează o sursă --</option>
              {sources.map((s) => (
                <option key={s.id} value={s.id}>{s.name} ({CATALOG_LABELS[s.catalog_type] ?? s.catalog_type})</option>
              ))}
            </select>

            {selectedSource && (
              <div className="flex items-center gap-2 text-sm text-slate-500 dark:text-slate-400">
                <SourceTypeIcon type={selectedSource.source_type} showLabel />
                <span className="text-slate-300 dark:text-slate-600">|</span>
                <span className="rounded bg-indigo-100 px-2 py-0.5 text-xs font-medium text-indigo-700 dark:bg-indigo-900/40 dark:text-indigo-400">
                  {CATALOG_LABELS[selectedSource.catalog_type] ?? selectedSource.catalog_type}
                </span>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Mappings list */}
      {selectedSourceId && (
        <div>
          <div className="mb-4 flex items-center justify-between">
            <h2 className="text-sm font-semibold text-slate-700 dark:text-slate-300">
              Mappings ({mappings.length})
            </h2>
            <button
              type="button"
              onClick={() => void handleCreateMapping()}
              disabled={isCreating}
              className="wm-btn-primary gap-2 text-sm"
            >
              {isCreating ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />}
              Create Mapping
            </button>
          </div>

          {mappingsLoading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="h-6 w-6 animate-spin text-slate-400" />
            </div>
          ) : mappings.length === 0 ? (
            <div className="rounded-xl border-2 border-dashed border-slate-200 py-12 text-center dark:border-slate-700">
              <GitBranch className="mx-auto mb-3 h-10 w-10 text-slate-300 dark:text-slate-600" />
              <p className="text-sm font-medium text-slate-500 dark:text-slate-400">
                Nicio mapare configurată pentru această sursă.
              </p>
              <p className="mt-1 text-xs text-slate-400 dark:text-slate-500">
                Creează prima mapare pentru a începe transformarea datelor.
              </p>
            </div>
          ) : (
            <div className="space-y-3">
              {mappings.map((mapping) => (
                <button
                  key={mapping.id}
                  type="button"
                  onClick={() => router.push(`/agency/feed-management/field-mapping/${mapping.id}`)}
                  className="wm-card flex w-full items-center justify-between p-4 text-left transition hover:border-indigo-300 dark:hover:border-indigo-700"
                >
                  <div>
                    <p className="text-sm font-medium text-slate-900 dark:text-slate-100">
                      Mapping #{mapping.id}
                    </p>
                    <p className="mt-0.5 text-xs text-slate-500 dark:text-slate-400">
                      {(mapping.rules ?? []).length} rules configured &middot; Updated {new Date(mapping.updated_at).toLocaleDateString()}
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="rounded bg-indigo-100 px-2 py-0.5 text-xs font-medium text-indigo-700 dark:bg-indigo-900/40 dark:text-indigo-400">
                      {CATALOG_LABELS[mapping.catalog_type] ?? mapping.catalog_type}
                    </span>
                    <ArrowRight className="h-4 w-4 text-slate-400" />
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Empty state when no source selected */}
      {!selectedSourceId && !sourcesLoading && (
        <div className="rounded-xl border-2 border-dashed border-slate-200 py-16 text-center dark:border-slate-700">
          <GitBranch className="mx-auto mb-3 h-12 w-12 text-slate-300 dark:text-slate-600" />
          <p className="text-sm font-medium text-slate-500 dark:text-slate-400">
            Selectează o sursă de date pentru a vizualiza și configura mapările.
          </p>
        </div>
      )}
    </>
  );
}
