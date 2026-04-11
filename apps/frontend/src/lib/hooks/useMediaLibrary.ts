import { useCallback, useEffect, useState } from "react";

import {
  listFolders,
  listMedia,
  type StorageFolder,
  type StorageKind,
  type StorageMediaListItem,
  type StorageMediaSort,
} from "@/lib/storage-client";

type UseMediaLibraryParams = {
  clientId: number;
  folderId: string | null;      // null = root
  kind?: StorageKind;
  search?: string;
  sort?: StorageMediaSort;
  limit?: number;
  offset?: number;
};

type UseMediaLibraryState = {
  folders: StorageFolder[];
  files: StorageMediaListItem[];
  total: number;
  loading: boolean;
  error: string;
  refresh: () => void;
};

function foldersEqual(a: StorageFolder[], b: StorageFolder[]): boolean {
  if (a.length !== b.length) return false;
  for (let i = 0; i < a.length; i += 1) {
    if (a[i].folder_id !== b[i].folder_id) return false;
  }
  return true;
}

/**
 * Lists both folders (children of the current folder) and files belonging to
 * that folder for a sub-account's media library. The "root" level is signaled
 * with `folderId = null`. Refetches automatically when any parameter changes.
 */
export function useMediaLibrary({
  clientId,
  folderId,
  kind,
  search,
  sort,
  limit = 60,
  offset = 0,
}: UseMediaLibraryParams): UseMediaLibraryState {
  const [folders, setFolders] = useState<StorageFolder[]>([]);
  const [files, setFiles] = useState<StorageMediaListItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [refreshKey, setRefreshKey] = useState(0);

  const refresh = useCallback(() => setRefreshKey((prev) => prev + 1), []);

  useEffect(() => {
    if (!Number.isFinite(clientId) || clientId <= 0) return;
    let cancelled = false;
    setLoading(true);
    setError("");

    const folderFilter = folderId ?? "root";

    (async () => {
      try {
        const [folderResponse, mediaResponse] = await Promise.all([
          listFolders({ clientId, parentFolderId: folderId }),
          listMedia({
            clientId,
            folderId: folderFilter,
            kind,
            search,
            sort,
            limit,
            offset,
          }),
        ]);
        if (cancelled) return;
        setFolders((previous) =>
          foldersEqual(previous, folderResponse.items) ? previous : folderResponse.items,
        );
        setFiles(mediaResponse.items);
        setTotal(mediaResponse.total);
      } catch (err) {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : "Nu am putut încărca fișierele media.");
        setFolders([]);
        setFiles([]);
        setTotal(0);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [clientId, folderId, kind, search, sort, limit, offset, refreshKey]);

  return { folders, files, total, loading, error, refresh };
}
