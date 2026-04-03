"use client";

import { useState, useRef, useEffect } from "react";
import Link from "next/link";
import { MoreVertical, Eye, Pencil, RefreshCw, Trash2 } from "lucide-react";
import type { FeedSource, CatalogType } from "@/lib/types/feed-management";
import { SourceTypeIcon } from "./SourceTypeIcon";
import { FeedSourceStatusBadge } from "./FeedSourceStatusBadge";
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
}: {
  source: FeedSource;
  onSync: (id: string) => void;
  onDelete: (id: string) => void;
}) {
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
      </td>
      <td className="px-4 py-3">
        <SourceTypeIcon type={source.source_type} showLabel />
      </td>
      <td className="px-4 py-3">
        <CatalogTypeBadge type={source.catalog_type} />
      </td>
      <td className="px-4 py-3">
        <FeedSourceStatusBadge status={source.status} />
      </td>
      <td className="px-4 py-3 text-slate-600 dark:text-slate-400">
        {formatDate(source.last_sync)}
      </td>
      <td className="px-4 py-3 text-slate-600 dark:text-slate-400">
        {(source.product_count ?? 0).toLocaleString()}
      </td>
      <td className="px-4 py-3">
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
      </td>
    </tr>
  );
}
