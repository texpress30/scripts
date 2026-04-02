"use client";

import { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import {
  Loader2,
  Search,
  Download,
  ChevronLeft,
  ChevronRight,
  ChevronsLeft,
  ChevronsRight,
  Package,
  GitBranch,
  RefreshCw,
  Rss,
} from "lucide-react";
import { useFeedSources } from "@/lib/hooks/useFeedSources";
import { useFeedManagement } from "@/lib/contexts/FeedManagementContext";
import { useChannels, type FeedChannel } from "@/lib/hooks/useMasterFields";
import { useChannelProducts } from "@/lib/hooks/useChannelProducts";
import { ChannelProductsTable } from "@/components/feed-management/ChannelProductsTable";
import { ColumnCustomizer } from "@/components/feed-management/ColumnCustomizer";

const ROWS_OPTIONS = [10, 25, 50, 100];

// ---------------------------------------------------------------------------
// Helper: aggregate channels across sources
// ---------------------------------------------------------------------------

type ChannelWithSource = FeedChannel & { sourceName: string };

function useAllChannels(sources: { id: string; name: string }[]) {
  // Call useChannels for every source — hooks must be called unconditionally
  // so we pre-allocate slots for up to 10 sources (practical limit).
  const s0 = useChannels(sources[0]?.id ?? null);
  const s1 = useChannels(sources[1]?.id ?? null);
  const s2 = useChannels(sources[2]?.id ?? null);
  const s3 = useChannels(sources[3]?.id ?? null);
  const s4 = useChannels(sources[4]?.id ?? null);
  const s5 = useChannels(sources[5]?.id ?? null);
  const s6 = useChannels(sources[6]?.id ?? null);
  const s7 = useChannels(sources[7]?.id ?? null);
  const s8 = useChannels(sources[8]?.id ?? null);
  const s9 = useChannels(sources[9]?.id ?? null);

  const slots = [s0, s1, s2, s3, s4, s5, s6, s7, s8, s9];
  const isLoading = sources.some((_, i) => slots[i]?.isLoading);

  const all: ChannelWithSource[] = [];
  for (let i = 0; i < Math.min(sources.length, 10); i++) {
    const chs = slots[i]?.channels ?? [];
    for (const ch of chs) {
      all.push({ ...ch, sourceName: sources[i].name });
    }
  }

  return { channels: all, isLoading };
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function ProductsPage() {
  const { selectedId, isLoading: clientsLoading } = useFeedManagement();
  const { sources, isLoading: sourcesLoading } = useFeedSources(selectedId);

  const { channels, isLoading: channelsLoading } = useAllChannels(sources);

  const [selectedChannelId, setSelectedChannelId] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [perPage, setPerPage] = useState(10);
  const [searchInput, setSearchInput] = useState("");
  const [search, setSearch] = useState("");
  const [visibleColumns, setVisibleColumns] = useState<Set<string>>(new Set());

  // Auto-select first channel
  useEffect(() => {
    if (channels.length > 0 && !selectedChannelId) {
      setSelectedChannelId(channels[0].id);
    }
    // Reset if current channel disappears
    if (selectedChannelId && channels.length > 0 && !channels.find((c) => c.id === selectedChannelId)) {
      setSelectedChannelId(channels[0].id);
    }
  }, [channels, selectedChannelId]);

  // Reset page on channel or search change
  useEffect(() => { setPage(1); }, [selectedChannelId, search]);

  const { products, columns, total, isLoading: productsLoading } = useChannelProducts(
    selectedChannelId,
    page,
    perPage,
    search,
  );

  // Init visible columns
  useEffect(() => {
    if (columns.length > 0 && visibleColumns.size === 0) {
      setVisibleColumns(new Set(columns.map((c) => c.key)));
    }
  }, [columns, visibleColumns.size]);

  const handleSearch = useCallback(() => {
    setSearch(searchInput);
    setPage(1);
  }, [searchInput]);

  const totalPages = Math.max(1, Math.ceil(total / perPage));
  const loading = clientsLoading || sourcesLoading || channelsLoading;

  const selectedChannel = channels.find((c) => c.id === selectedChannelId) ?? null;

  function handleDownload(format: string) {
    if (!selectedChannel) return;
    const url = selectedChannel.feed_url
      ? `/api${selectedChannel.feed_url}`
      : `/api/feeds/${selectedChannel.public_token}.${format}`;
    window.open(url, "_blank");
  }

  // Group channels by source for the selector
  const sourceMap = new Map<string, { name: string; channels: ChannelWithSource[] }>();
  for (const ch of channels) {
    const key = ch.feed_source_id;
    if (!sourceMap.has(key)) sourceMap.set(key, { name: ch.sourceName, channels: [] });
    sourceMap.get(key)!.channels.push(ch);
  }

  // ---------------------------------------------------------------------------
  // Empty states
  // ---------------------------------------------------------------------------

  if (!selectedId && !clientsLoading) {
    return (
      <div className="wm-card flex flex-col items-center justify-center px-6 py-16 text-center">
        <p className="text-sm text-slate-500 dark:text-slate-400">
          Selecteaza un client pentru a vizualiza produsele.
        </p>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="h-6 w-6 animate-spin text-slate-400" />
      </div>
    );
  }

  if (sources.length === 0) {
    return (
      <div className="wm-card flex flex-col items-center justify-center px-6 py-16 text-center">
        <RefreshCw className="mx-auto mb-3 h-10 w-10 text-slate-300 dark:text-slate-600" />
        <p className="text-sm font-medium text-slate-500 dark:text-slate-400">No products synced yet</p>
        <p className="mt-1 text-xs text-slate-400 dark:text-slate-500">Sync your feed source to import products.</p>
        <Link href="/agency/feed-management/sources" className="wm-btn-primary mt-4 text-sm">
          Go to Sources
        </Link>
      </div>
    );
  }

  if (channels.length === 0) {
    return (
      <div className="wm-card flex flex-col items-center justify-center px-6 py-16 text-center">
        <Rss className="mx-auto mb-3 h-10 w-10 text-slate-300 dark:text-slate-600" />
        <p className="text-sm font-medium text-slate-500 dark:text-slate-400">No channels configured yet</p>
        <p className="mt-1 text-xs text-slate-400 dark:text-slate-500">Create a channel first to view transformed products.</p>
        <Link href="/agency/feed-management/channels" className="wm-btn-primary mt-4 text-sm">
          Go to Channels
        </Link>
      </div>
    );
  }

  // ---------------------------------------------------------------------------
  // Main render
  // ---------------------------------------------------------------------------

  return (
    <>
      {/* Header */}
      <div className="mb-6">
        <h2 className="text-lg font-semibold text-slate-900 dark:text-slate-100">Products</h2>
        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
          View transformed products for your feed channels.
        </p>
      </div>

      {/* Channel selector */}
      <div className="mb-4">
        <label htmlFor="prod-channel" className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">
          Channel
        </label>
        <select
          id="prod-channel"
          value={selectedChannelId ?? ""}
          onChange={(e) => {
            setSelectedChannelId(e.target.value);
            setVisibleColumns(new Set());
          }}
          className="wm-input max-w-md"
        >
          {[...sourceMap.entries()].map(([sourceId, { name, channels: chs }]) => (
            <optgroup key={sourceId} label={name}>
              {chs.map((ch) => (
                <option key={ch.id} value={ch.id}>
                  {ch.name} ({ch.included_products} products)
                </option>
              ))}
            </optgroup>
          ))}
        </select>
      </div>

      {/* Toolbar */}
      <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <h3 className="text-sm font-semibold text-slate-700 dark:text-slate-300">
          Explore your feed products
        </h3>
        <div className="flex flex-wrap items-center gap-2">
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
          <ColumnCustomizer columns={columns} visible={visibleColumns} onChange={setVisibleColumns} />
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
        {productsLoading ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="h-5 w-5 animate-spin text-slate-400" />
          </div>
        ) : columns.length === 0 ? (
          <div className="flex flex-col items-center justify-center px-6 py-12 text-center">
            <GitBranch className="mx-auto mb-3 h-8 w-8 text-slate-300 dark:text-slate-600" />
            <p className="text-sm font-medium text-slate-500 dark:text-slate-400">No field mappings configured</p>
            <p className="mt-1 text-xs text-slate-400 dark:text-slate-500">Configure Master Fields to transform your product data.</p>
            <Link href="/agency/feed-management/field-mapping" className="wm-btn-primary mt-3 text-xs">
              Go to Field Mapping
            </Link>
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
          <span className="text-xs text-slate-500 dark:text-slate-400">Results: {total}</span>
          <div className="flex items-center gap-1">
            <button type="button" onClick={() => setPage(1)} disabled={page <= 1} className="rounded p-1.5 text-slate-500 hover:bg-slate-100 disabled:opacity-30 dark:hover:bg-slate-800">
              <ChevronsLeft className="h-4 w-4" />
            </button>
            <button type="button" onClick={() => setPage((p) => Math.max(1, p - 1))} disabled={page <= 1} className="rounded p-1.5 text-slate-500 hover:bg-slate-100 disabled:opacity-30 dark:hover:bg-slate-800">
              <ChevronLeft className="h-4 w-4" />
            </button>
            <span className="px-3 text-xs text-slate-600 dark:text-slate-400">Page {page} of {totalPages}</span>
            <button type="button" onClick={() => setPage((p) => Math.min(totalPages, p + 1))} disabled={page >= totalPages} className="rounded p-1.5 text-slate-500 hover:bg-slate-100 disabled:opacity-30 dark:hover:bg-slate-800">
              <ChevronRight className="h-4 w-4" />
            </button>
            <button type="button" onClick={() => setPage(totalPages)} disabled={page >= totalPages} className="rounded p-1.5 text-slate-500 hover:bg-slate-100 disabled:opacity-30 dark:hover:bg-slate-800">
              <ChevronsRight className="h-4 w-4" />
            </button>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-xs text-slate-500 dark:text-slate-400">Show rows:</span>
            <select value={perPage} onChange={(e) => { setPerPage(Number(e.target.value)); setPage(1); }} className="rounded border border-slate-200 bg-white px-2 py-1 text-xs dark:border-slate-700 dark:bg-slate-900">
              {ROWS_OPTIONS.map((n) => <option key={n} value={n}>{n}</option>)}
            </select>
          </div>
        </div>
      )}
    </>
  );
}
