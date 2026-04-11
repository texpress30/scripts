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
        className={cn("object-cover", sizeClassName)}
        onError={() => setFailed(true)}
      />
    );
  }

  return (
    <div className={cn("flex items-center justify-center", sizeClassName)}>
      <Icon className="h-1/2 w-1/2 max-h-10 max-w-10 text-slate-400 dark:text-slate-500" />
    </div>
  );
}
