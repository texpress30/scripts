"use client";

import Link from "next/link";
import { ArrowRight, GitBranch, Package, Car, Home, Building, Plane, Film, Rss } from "lucide-react";
import type { FeedSource, CatalogType } from "@/lib/types/feed-management";
import { SourceTypeIcon } from "./SourceTypeIcon";
import { useChannels } from "@/lib/hooks/useMasterFields";

const CATALOG_CONFIG: Record<CatalogType, { label: string; icon: typeof Package; color: string }> = {
  product: { label: "Product", icon: Package, color: "text-indigo-600 dark:text-indigo-400" },
  vehicle: { label: "Vehicle", icon: Car, color: "text-blue-600 dark:text-blue-400" },
  home_listing: { label: "Home Listing", icon: Home, color: "text-emerald-600 dark:text-emerald-400" },
  hotel: { label: "Hotel", icon: Building, color: "text-amber-600 dark:text-amber-400" },
  flight: { label: "Flight", icon: Plane, color: "text-sky-600 dark:text-sky-400" },
  media: { label: "Media", icon: Film, color: "text-rose-600 dark:text-rose-400" },
};

function timeAgo(value: string | null): string {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  const seconds = Math.floor((Date.now() - date.getTime()) / 1000);
  if (seconds < 60) return "just now";
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

export function SourceMappingsCard({
  source,
  subaccountId,
}: {
  source: FeedSource;
  subaccountId: number;
}) {
  const { channels } = useChannels(source.id);

  const catalogCfg = CATALOG_CONFIG[source.catalog_type] ?? CATALOG_CONFIG.product;
  const CatalogIcon = catalogCfg.icon;
  const lastSync = source.last_sync ? `Last sync: ${timeAgo(source.last_sync)}` : "";
  const productInfo = `${source.product_count} products`;
  const activeChannels = channels.filter((ch) => ch.status === "active").length;

  return (
    <section className="wm-card overflow-hidden">
      {/* Source header */}
      <div className="flex flex-col gap-2 border-b border-slate-200 px-5 py-4 dark:border-slate-700 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <div className="flex items-center gap-2">
            <h3 className="text-sm font-semibold text-slate-900 dark:text-slate-100">{source.name}</h3>
            <span className={`inline-flex items-center gap-1 rounded bg-slate-100 px-2 py-0.5 text-xs font-medium dark:bg-slate-800 ${catalogCfg.color}`}>
              <CatalogIcon className="h-3 w-3" />
              {catalogCfg.label}
            </span>
          </div>
          <div className="mt-1 flex items-center gap-2 text-xs text-slate-500 dark:text-slate-400">
            <SourceTypeIcon type={source.source_type} showLabel />
            <span className="text-slate-300 dark:text-slate-600">&middot;</span>
            <span>{productInfo}</span>
            {lastSync && (
              <>
                <span className="text-slate-300 dark:text-slate-600">&middot;</span>
                <span>{lastSync}</span>
              </>
            )}
          </div>
        </div>
      </div>

      {/* Actions body */}
      <div className="px-5 py-4">
        <div className="space-y-2">
          {/* Master Fields link */}
          <Link
            href={`/agency/feed-management/field-mapping/${source.id}`}
            className="flex w-full items-center justify-between rounded-lg border border-slate-200 bg-white px-4 py-3 text-left transition hover:border-indigo-300 dark:border-slate-700 dark:bg-slate-900 dark:hover:border-indigo-700"
          >
            <div className="flex items-center gap-3">
              <GitBranch className="h-5 w-5 text-indigo-500" />
              <div>
                <p className="text-sm font-medium text-slate-900 dark:text-slate-100">
                  Map Master Fields
                </p>
                <p className="mt-0.5 text-xs text-slate-500 dark:text-slate-400">
                  Configure universal field mappings for this source
                </p>
              </div>
            </div>
            <ArrowRight className="h-4 w-4 text-slate-400" />
          </Link>

          {/* Channels link */}
          <Link
            href={`/agency/feed-management/field-mapping/${source.id}/channels`}
            className="flex w-full items-center justify-between rounded-lg border border-slate-200 bg-white px-4 py-3 text-left transition hover:border-indigo-300 dark:border-slate-700 dark:bg-slate-900 dark:hover:border-indigo-700"
          >
            <div className="flex items-center gap-3">
              <Rss className="h-5 w-5 text-emerald-500" />
              <div>
                <p className="text-sm font-medium text-slate-900 dark:text-slate-100">
                  Channels
                </p>
                <p className="mt-0.5 text-xs text-slate-500 dark:text-slate-400">
                  {channels.length > 0
                    ? `${channels.length} channel${channels.length > 1 ? "s" : ""} configured${activeChannels > 0 ? ` · ${activeChannels} active` : ""}`
                    : "Create channels to publish your feed"}
                </p>
              </div>
            </div>
            <ArrowRight className="h-4 w-4 text-slate-400" />
          </Link>
        </div>
      </div>
    </section>
  );
}
