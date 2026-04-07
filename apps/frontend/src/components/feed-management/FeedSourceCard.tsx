"use client";

import { useState, useRef, useEffect } from "react";
import Link from "next/link";
import { MoreVertical, Eye, Pencil, RefreshCw, Trash2, Download, PlugZap, Loader2 } from "lucide-react";
import type { FeedSource, CatalogType } from "@/lib/types/feed-management";
import { SourceTypeIcon } from "./SourceTypeIcon";
import { FeedConnectionStatusBadge } from "./FeedSourceStatusBadge";
import { Package, Car, Home, Building, Plane, Film, MapPin, Briefcase } from "lucide-react";

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

function CatalogTypeBadge({ type }: { type: CatalogType }) {
  const cfg = CATALOG_CONFIG[type] ?? CATALOG_CONFIG.product;
  const Icon = cfg.icon;
  return (
    <span className="inline-flex items-center gap-1.5 text-sm">
      <Icon className={`h-4 w-4 ${cfg.color}`} />
      <span className="text-slate-700 dark:text-slate-300">{cfg.label}</span>
    </span>
  );
}

function formatDate(value: string | null): string {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString();
}

export function FeedSourceCard({
  source,
  onSync,
  onDelete,
  onImport,
  onReconnect,
  isSyncing = false,
  isImporting = false,
  isReconnecting = false,
}: {
  source: FeedSource;
  onSync: (id: string) => void;
  onDelete: (id: string) => void;
  onImport?: (id: string) => void;
  onReconnect?: (id: string) => void;
  isSyncing?: boolean;
  isImporting?: boolean;
  isReconnecting?: boolean;
}) {
  const isShopify = source.source_type === "shopify";
  const connectionStatus = source.connection_status ?? "pending";
  const canImport = isShopify && connectionStatus === "connected";
  const needsReconnect = isShopify && (connectionStatus === "error" || connectionStatus === "disconnected");
  const [menuOpen, setMenuOpen] = useState(false);
  const btnRef = useRef<HTMLButtonElement>(null);
  const [pos, setPos] = useState({ top: 0, left: 0 });

  useEffect(() => {
    if (menuOpen && btnRef.current) {
      const rect = btnRef.current.getBoundingClientRect();
      setPos({ top: rect.bottom + 4, left: rect.right - 160 });
    }
  }, [menuOpen]);

  return (
    <tr className="border-t border-slate-100 dark:border-slate-800">
      <td className="px-4 py-3">
        <Link
          href={`/agency/feed-management/sources/${source.id}`}
          className="font-medium text-indigo-700 hover:underline dark:text-indigo-400"
        >
          {source.name}
        </Link>
        {isShopify && source.shop_domain ? (
          <div className="mt-0.5 text-xs text-slate-500 dark:text-slate-400">{source.shop_domain}</div>
        ) : null}
      </td>
      <td className="px-4 py-3">
        <SourceTypeIcon type={source.source_type} showLabel />
      </td>
      <td className="px-4 py-3">
        <CatalogTypeBadge type={source.catalog_type} />
      </td>
      <td className="px-4 py-3">
        <FeedConnectionStatusBadge status={connectionStatus} />
        {needsReconnect && source.last_error ? (
          <div className="mt-1 max-w-[12rem] truncate text-xs text-red-600 dark:text-red-400" title={source.last_error}>
            {source.last_error}
          </div>
        ) : null}
      </td>
      <td className="px-4 py-3 text-slate-600 dark:text-slate-400">
        {formatDate(source.last_import_at ?? source.last_sync)}
      </td>
      <td className="px-4 py-3 text-slate-600 dark:text-slate-400">
        {(source.product_count ?? 0).toLocaleString()}
      </td>
      <td className="px-4 py-3">
        <div className="flex items-center gap-1">
        {canImport && onImport ? (
          <button
            type="button"
            onClick={() => onImport(source.id)}
            disabled={isImporting}
            className="inline-flex items-center gap-1 rounded px-2 py-1 text-xs font-medium text-emerald-700 hover:bg-emerald-50 disabled:opacity-50 dark:text-emerald-400 dark:hover:bg-emerald-900/20"
            title="Importă produse"
          >
            {isImporting ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Download className="h-3.5 w-3.5" />}
            {isImporting ? "Se importă..." : "Importă"}
          </button>
        ) : null}
        {needsReconnect && onReconnect ? (
          <button
            type="button"
            onClick={() => onReconnect(source.id)}
            disabled={isReconnecting}
            className="inline-flex items-center gap-1 rounded px-2 py-1 text-xs font-medium text-amber-700 hover:bg-amber-50 disabled:opacity-50 dark:text-amber-400 dark:hover:bg-amber-900/20"
            title="Reconectează"
          >
            {isReconnecting ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <PlugZap className="h-3.5 w-3.5" />}
            Reconectează
          </button>
        ) : null}
        <button
          type="button"
          onClick={() => onSync(source.id)}
          disabled={isSyncing}
          className={`rounded p-1.5 ${isSyncing ? "text-indigo-500" : "text-slate-500 hover:bg-indigo-50 hover:text-indigo-600 dark:hover:bg-indigo-900/20 dark:hover:text-indigo-400"}`}
          title={isSyncing ? "Syncing..." : "Sync Now"}
        >
          <RefreshCw className={`h-4 w-4 ${isSyncing ? "animate-spin" : ""}`} />
        </button>
        <button
          ref={btnRef}
          type="button"
          onClick={() => setMenuOpen((prev) => !prev)}
          className="rounded p-1 text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-800"
          aria-label="Acțiuni"
        >
          <MoreVertical className="h-4 w-4" />
        </button>

        {menuOpen ? (
          <>
            <div className="fixed inset-0 z-40" onClick={() => setMenuOpen(false)} />
            <div
              className="fixed z-50 w-40 rounded-lg border border-slate-200 bg-white py-1 shadow-lg dark:border-slate-700 dark:bg-slate-900"
              style={{ top: pos.top, left: pos.left }}
            >
              <Link
                href={`/agency/feed-management/sources/${source.id}`}
                className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-slate-700 hover:bg-slate-50 dark:text-slate-300 dark:hover:bg-slate-800"
                onClick={() => setMenuOpen(false)}
              >
                <Eye className="h-4 w-4" /> View
              </Link>
              <Link
                href={`/agency/feed-management/sources/${source.id}`}
                className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-slate-700 hover:bg-slate-50 dark:text-slate-300 dark:hover:bg-slate-800"
                onClick={() => setMenuOpen(false)}
              >
                <Pencil className="h-4 w-4" /> Edit
              </Link>
              <button
                type="button"
                onClick={() => {
                  setMenuOpen(false);
                  onSync(source.id);
                }}
                className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-slate-700 hover:bg-slate-50 dark:text-slate-300 dark:hover:bg-slate-800"
              >
                <RefreshCw className="h-4 w-4" /> Sync Now
              </button>
              <button
                type="button"
                onClick={() => {
                  setMenuOpen(false);
                  onDelete(source.id);
                }}
                className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-red-600 hover:bg-red-50 dark:text-red-400 dark:hover:bg-red-900/20"
              >
                <Trash2 className="h-4 w-4" /> Delete
              </button>
            </div>
          </>
        ) : null}
        </div>
      </td>
    </tr>
  );
}
