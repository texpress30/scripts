"use client";

import { useEffect, useState } from "react";
import { FileText, Film, ImageIcon, Lock } from "lucide-react";

import { getMediaAccessUrl, type StorageMediaListItem, type StorageMediaSource } from "@/lib/storage-client";
import { cn } from "@/lib/utils";

type FileCardProps = {
  clientId: number;
  file: StorageMediaListItem;
  selected?: boolean;
  onClick?: (file: StorageMediaListItem) => void;
};

const KIND_ICON: Record<string, typeof ImageIcon> = {
  image: ImageIcon,
  video: Film,
  document: FileText,
};

function isSystemSource(source: StorageMediaSource | string): boolean {
  return source === "enriched_catalog" || source === "backend_ingest" || source === "platform_sync";
}

export function FileCard({ clientId, file, selected, onClick }: FileCardProps) {
  const [thumbnailUrl, setThumbnailUrl] = useState<string | null>(null);
  const [thumbError, setThumbError] = useState(false);

  useEffect(() => {
    if (file.kind !== "image") {
      setThumbnailUrl(null);
      return;
    }
    let cancelled = false;
    (async () => {
      try {
        const response = await getMediaAccessUrl({
          clientId,
          mediaId: file.media_id,
          disposition: "inline",
        });
        if (!cancelled) setThumbnailUrl(response.url);
      } catch {
        if (!cancelled) setThumbError(true);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [clientId, file.media_id, file.kind]);

  const Icon = KIND_ICON[file.kind] ?? FileText;
  const label = file.display_name || file.original_filename;
  const isSystem = isSystemSource(file.source);

  return (
    <button
      type="button"
      onClick={() => onClick?.(file)}
      className={cn(
        "group relative flex h-44 w-full flex-col overflow-hidden rounded-lg border text-left transition-colors",
        selected
          ? "border-indigo-400 ring-2 ring-indigo-400/40"
          : "border-slate-200 hover:border-slate-300 dark:border-slate-700 dark:hover:border-slate-600",
      )}
      title={label}
    >
      <div className="relative flex-1 bg-slate-50 dark:bg-slate-800">
        {file.kind === "image" && thumbnailUrl && !thumbError ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={thumbnailUrl}
            alt={label}
            className="h-full w-full object-cover"
            onError={() => setThumbError(true)}
          />
        ) : (
          <div className="flex h-full w-full items-center justify-center">
            <Icon className="h-12 w-12 text-slate-400 dark:text-slate-500" />
          </div>
        )}
        {isSystem && (
          <div
            className="absolute left-2 top-2 inline-flex items-center gap-1 rounded-md bg-indigo-50 px-2 py-0.5 text-[10px] font-medium text-indigo-700"
            title="Asset generat automat din pipeline-ul de Enriched Catalog"
          >
            <Lock className="h-3 w-3" />
            Agency
          </div>
        )}
      </div>
      <div className="flex items-center gap-2 border-t border-slate-200 bg-white px-2 py-1.5 dark:border-slate-700 dark:bg-slate-900">
        <span className="truncate text-xs font-medium text-slate-700 dark:text-slate-200">{label}</span>
      </div>
    </button>
  );
}
