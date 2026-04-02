"use client";

import { useState, useEffect, useCallback } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import {
  ArrowLeft,
  Loader2,
  Search,
  Download,
  ChevronLeft,
  ChevronRight,
  ChevronsLeft,
  ChevronsRight,
} from "lucide-react";
import { useChannel } from "@/lib/hooks/useMasterFields";
import { useChannelProducts } from "@/lib/hooks/useChannelProducts";
import { ChannelProductsTable } from "@/components/feed-management/ChannelProductsTable";
import { ColumnCustomizer } from "@/components/feed-management/ColumnCustomizer";

const ROWS_OPTIONS = [10, 25, 50, 100];

const CHANNEL_TYPE_LABELS: Record<string, string> = {
  google_shopping: "Google Shopping",
  facebook_product_ads: "Facebook Product Ads",
  meta_catalog: "Meta Catalog",
  tiktok_catalog: "TikTok Catalog",
  custom: "Custom",
};

export default function ChannelProductsPage() {
  const params = useParams<{ id: string }>();
  const channelId = params.id;

  const { channel, isLoading: channelLoading } = useChannel(channelId);

  const [page, setPage] = useState(1);
  const [perPage, setPerPage] = useState(10);
  const [searchInput, setSearchInput] = useState("");
  const [search, setSearch] = useState("");
  const [visibleColumns, setVisibleColumns] = useState<Set<string>>(new Set());

  const { products, columns, total, isLoading, error } = useChannelProducts(
    channelId,
    page,
    perPage,
    search,
  );

  // Initialize visible columns when columns arrive
  useEffect(() => {
    if (columns.length > 0 && visibleColumns.size === 0) {
      setVisibleColumns(new Set(columns.map((c) => c.key)));
    }
  }, [columns, visibleColumns.size]);

  // Reset page on search
  const handleSearch = useCallback(() => {
    setSearch(searchInput);
    setPage(1);
  }, [searchInput]);

  const totalPages = Math.max(1, Math.ceil(total / perPage));
  const channelLabel = channel
    ? channel.name || CHANNEL_TYPE_LABELS[channel.channel_type] || channel.channel_type
    : "";

  function handleDownload(format: string) {
    if (!channel) return;
    const url = channel.feed_url
      ? `/api${channel.feed_url}`
      : `/api/feeds/${channel.public_token}.${format}`;
    window.open(url, "_blank");
  }

  if (channelLoading) {
    return (
      <div className="flex items-center justify-center py-16">
        <Loader2 className="h-6 w-6 animate-spin text-slate-400" />
      </div>
    );
  }

  if (!channel) {
    return (
      <div className="py-8">
        <Link
          href="/agency/feed-management/channels"
          className="mb-4 inline-flex items-center gap-1 text-sm text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-300"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to Channels
        </Link>
        <p className="text-red-600">{error ?? "Channel not found."}</p>
      </div>
    );
  }

  return (
    <>
      <Link
        href={`/agency/feed-management/channels/${channelId}`}
        className="mb-4 inline-flex items-center gap-1 text-sm text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-300"
      >
        <ArrowLeft className="h-4 w-4" />
        Back to Channel
      </Link>

      {/* Header */}
      <div className="mb-6">
        <h1 className="text-xl font-semibold text-slate-900 dark:text-slate-100">Channel Products</h1>
        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
          {channelLabel} &middot; {total} products
        </p>
      </div>

      {/* Toolbar */}
      <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <h2 className="text-sm font-semibold text-slate-700 dark:text-slate-300">
          Explore your feed products
        </h2>
        <div className="flex flex-wrap items-center gap-2">
          {/* Search */}
          <div className="relative">
            <input
              type="text"
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleSearch()}
              placeholder="Search..."
              className="wm-input w-48 pl-8 text-xs"
            />
            <Search className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-slate-400" />
          </div>

          {/* Column customizer */}
          <ColumnCustomizer columns={columns} visible={visibleColumns} onChange={setVisibleColumns} />

          {/* Download */}
          <div className="relative">
            <select
              onChange={(e) => {
                if (e.target.value) handleDownload(e.target.value);
                e.target.value = "";
              }}
              defaultValue=""
              className="wm-btn-secondary appearance-none pr-7 text-xs"
            >
              <option value="" disabled>Download as</option>
              <option value="xml">XML</option>
              <option value="csv">CSV</option>
              <option value="json">JSON</option>
            </select>
            <Download className="pointer-events-none absolute right-2 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-slate-400" />
          </div>
        </div>
      </div>

      {/* Table */}
      <div className="wm-card overflow-hidden">
        {isLoading ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="h-5 w-5 animate-spin text-slate-400" />
          </div>
        ) : (
          <ChannelProductsTable
            products={products}
            columns={columns}
            visibleColumns={visibleColumns}
          />
        )}
      </div>

      {/* Pagination */}
      {total > 0 && (
        <div className="mt-4 flex flex-col items-center justify-between gap-3 sm:flex-row">
          <span className="text-xs text-slate-500 dark:text-slate-400">
            Results: {total}
          </span>

          <div className="flex items-center gap-1">
            <button
              type="button"
              onClick={() => setPage(1)}
              disabled={page <= 1}
              className="rounded p-1.5 text-slate-500 hover:bg-slate-100 disabled:opacity-30 dark:hover:bg-slate-800"
            >
              <ChevronsLeft className="h-4 w-4" />
            </button>
            <button
              type="button"
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page <= 1}
              className="rounded p-1.5 text-slate-500 hover:bg-slate-100 disabled:opacity-30 dark:hover:bg-slate-800"
            >
              <ChevronLeft className="h-4 w-4" />
            </button>
            <span className="px-3 text-xs text-slate-600 dark:text-slate-400">
              Page {page} of {totalPages}
            </span>
            <button
              type="button"
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              disabled={page >= totalPages}
              className="rounded p-1.5 text-slate-500 hover:bg-slate-100 disabled:opacity-30 dark:hover:bg-slate-800"
            >
              <ChevronRight className="h-4 w-4" />
            </button>
            <button
              type="button"
              onClick={() => setPage(totalPages)}
              disabled={page >= totalPages}
              className="rounded p-1.5 text-slate-500 hover:bg-slate-100 disabled:opacity-30 dark:hover:bg-slate-800"
            >
              <ChevronsRight className="h-4 w-4" />
            </button>
          </div>

          <div className="flex items-center gap-2">
            <span className="text-xs text-slate-500 dark:text-slate-400">Show rows:</span>
            <select
              value={perPage}
              onChange={(e) => {
                setPerPage(Number(e.target.value));
                setPage(1);
              }}
              className="rounded border border-slate-200 bg-white px-2 py-1 text-xs dark:border-slate-700 dark:bg-slate-900"
            >
              {ROWS_OPTIONS.map((n) => (
                <option key={n} value={n}>{n}</option>
              ))}
            </select>
          </div>
        </div>
      )}
    </>
  );
}
