"use client";

import { useEffect, useState } from "react";
import { FileText, Film, Headphones, ImageIcon, LayoutGrid } from "lucide-react";

import { fetchMediaBlob, type StorageKind } from "@/lib/storage-client";
import { cn } from "@/lib/utils";

type MediaThumbnailProps = {
  clientId: number;
  mediaId: string;
  kind: StorageKind | string;
  displayName: string;
  sizeClassName?: string;
};

const KIND_ICON: Record<string, typeof ImageIcon> = {
  image: ImageIcon,
  video: Film,
  document: FileText,
  audio: Headphones,
  other: LayoutGrid,
};

/**
 * Small reusable thumbnail that lazily fetches a media image through the
 * backend-proxy endpoint (`/storage/media/:id/content`), wraps the returned
 * Blob in an object URL, and displays it inside an `<img>`. Falls back to a
 * category icon for non-image kinds or when the fetch fails.
 */
export function MediaThumbnail({
  clientId,
  mediaId,
  kind,
  displayName,
  sizeClassName = "h-full w-full",
}: MediaThumbnailProps) {
  const [url, setUrl] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    if (kind !== "image") {
      setUrl(null);
      return;
    }
    let cancelled = false;
    let createdObjectUrl: string | null = null;
    (async () => {
      try {
        const blob = await fetchMediaBlob({ clientId, mediaId });
        if (cancelled) return;
        createdObjectUrl = URL.createObjectURL(blob);
        setUrl(createdObjectUrl);
      } catch {
        if (!cancelled) setFailed(true);
      }
    })();
    return () => {
      cancelled = true;
      if (createdObjectUrl) URL.revokeObjectURL(createdObjectUrl);
    };
  }, [clientId, mediaId, kind]);

  const Icon = KIND_ICON[kind] ?? FileText;

  if (kind === "image" && url && !failed) {
    return (
      // eslint-disable-next-line @next/next/no-img-element
      <img
        src={url}
        alt={displayName}
        className={cn("max-h-full max-w-full object-contain", sizeClassName)}
        onError={() => setFailed(true)}
      />
    );
  }

  return (
    <div className="flex h-full w-full items-center justify-center">
      <Icon className="h-10 w-10 max-h-full max-w-full text-slate-400 dark:text-slate-500" />
    </div>
  );
}
