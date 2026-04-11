"use client";

import { Loader2, GitBranch, Plus, ArrowRight, Package, Car, Home, Building, Plane, Film, MapPin, Briefcase } from "lucide-react";
import Link from "next/link";
import { useFeedSources } from "@/lib/hooks/useFeedSources";
import { useFeedManagement } from "@/lib/contexts/FeedManagementContext";
import { useMasterFields } from "@/lib/hooks/useMasterFields";
import { SourceTypeIcon } from "@/components/feed-management/SourceTypeIcon";
import type { CatalogType, FeedSource } from "@/lib/types/feed-management";

const CATALOG_CONFIG: Record<CatalogType, { label: string; icon: typeof Package; color: string }> = {
  product: { label: "Product", icon: Package, color: "text-indigo-600 dark:text-indigo-400" },
  vehicle: { label: "Vehicle", icon: Car, color: "text-blue-600 dark:text-blue-400" },
  home_listing: { label: "Home Listing", icon: Home, color: "text-emerald-600 dark:text-emerald-400" },
  hotel: { label: "Hotel", icon: Building, color: "text-amber-600 dark:text-amber-400" },
  flight: { label: "Flight", icon: Plane, color: "text-sky-600 dark:text-sky-400" },
  media: { label: "Media", icon: Film, color: "text-rose-600 dark:text-rose-400" },
  destination: { label: "Destination", icon: MapPin, color: "text-teal-600 dark:text-teal-400" },
  service: { label: "Service", icon: Briefcase, color: "text-violet-600 dark:text-violet-400" },
};

function SourceCard({ source }: { source: FeedSource }) {
  const { data } = useMasterFields(source.id);
  const catalogCfg = CATALOG_CONFIG[source.catalog_type] ?? CATALOG_CONFIG.product;
  const CatalogIcon = catalogCfg.icon;
  const mapped = data?.mapped_count ?? 0;
  const total = data?.total_schema_fields ?? 0;

  return (
    <div className="wm-card flex flex-col gap-3 p-5 sm:flex-row sm:items-center sm:justify-between">
      <div>
        <div className="flex items-center gap-2">
          <h3 className="text-sm font-semibold">
            <Link
              href={`/agency/feed-management/field-mapping/${source.id}`}
              className="rounded text-slate-900 hover:text-indigo-600 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500 dark:text-slate-100 dark:hover:text-indigo-400"
            >
              {source.name}
            </Link>
          </h3>
          <span className={`inline-flex items-center gap-1 rounded bg-slate-100 px-2 py-0.5 text-xs font-medium dark:bg-slate-800 ${catalogCfg.color}`}>
            <CatalogIcon className="h-3 w-3" />
            {catalogCfg.label}
          </span>
        </div>
        <div className="mt-1 flex items-center gap-2 text-xs text-slate-500 dark:text-slate-400">
          <SourceTypeIcon type={source.source_type} showLabel />
          <span className="text-slate-300 dark:text-slate-600">&middot;</span>
          <span>{source.product_count} products</span>
          <span className="text-slate-300 dark:text-slate-600">&middot;</span>
          <Link
            href={`/agency/feed-management/field-mapping/${source.id}`}
            className="rounded hover:text-indigo-600 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500 dark:hover:text-indigo-400"
          >
            {mapped} / {total} fields mapped
          </Link>
        </div>
      </div>
      <Link
        href={`/agency/feed-management/field-mapping/${source.id}`}
        className="wm-btn-primary inline-flex items-center gap-1.5 text-xs"
      >
        Map Fields
        <ArrowRight className="h-3.5 w-3.5" />
      </Link>
    </div>
  );
}

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
        <div className="space-y-4">
          {sources.map((source) => (
            <SourceCard key={source.id} source={source} />
          ))}
        </div>
      )}
    </>
  );
}
