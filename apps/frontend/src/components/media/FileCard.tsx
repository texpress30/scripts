"use client";

import { Lock } from "lucide-react";

import { type StorageMediaListItem, type StorageMediaSource } from "@/lib/storage-client";
import { cn } from "@/lib/utils";

import { MediaThumbnail } from "./MediaThumbnail";

type FileCardProps = {
  clientId: number;
  file: StorageMediaListItem;
  selected?: boolean;
  onClick?: (file: StorageMediaListItem) => void;
};

function isSystemSource(source: StorageMediaSource | string): boolean {
  return source === "enriched_catalog" || source === "backend_ingest" || source === "platform_sync";
}

export function FileCard({ clientId, file, selected, onClick }: FileCardProps) {
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
        <MediaThumbnail
          clientId={clientId}
          mediaId={file.media_id}
          kind={file.kind}
          displayName={label}
        />
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
