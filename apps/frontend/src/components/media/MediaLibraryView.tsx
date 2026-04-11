"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { ChevronRight, FolderPlus, Home, Loader2, Search } from "lucide-react";

import { useMediaLibrary } from "@/lib/hooks/useMediaLibrary";
import {
  createFolder,
  deleteFolder,
  listFolders,
  renameFolder,
  type StorageFolder,
  type StorageKind,
  type StorageMediaListItem,
  type StorageMediaSort,
} from "@/lib/storage-client";

import { CreateFolderModal } from "./CreateFolderModal";
import { FileCard } from "./FileCard";
import { FolderCard } from "./FolderCard";
import { MediaPreviewModal } from "./MediaPreviewModal";
import { MediaUploadZone } from "./MediaUploadZone";

type BreadcrumbEntry = {
  folder_id: string | null;
  name: string;
};

type MediaLibraryViewProps = {
  clientId: number;
  /** When `embed=true`, renders without the large outer card wrapper — used
   *  inside `<MediaPicker />`. */
  embed?: boolean;
  /** Called when a file is clicked (picker mode). Default behaviour: open the
   *  preview modal. */
  onFileSelect?: (file: StorageMediaListItem) => void;
  /** Restrict the listing to a specific media kind (e.g. `image` for a logo
   *  picker). */
  kindFilter?: StorageKind;
  /** If true, the upload + create-folder + delete actions are hidden — used
   *  for read-only pickers. */
  readOnly?: boolean;
};

export function MediaLibraryView({
  clientId,
  embed = false,
  onFileSelect,
  kindFilter,
  readOnly = false,
}: MediaLibraryViewProps) {
  const [breadcrumbs, setBreadcrumbs] = useState<BreadcrumbEntry[]>([{ folder_id: null, name: "Home" }]);
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [sort, setSort] = useState<StorageMediaSort>("newest");
  const [kind, setKind] = useState<StorageKind | "all">(kindFilter ?? "all");
  const [createFolderOpen, setCreateFolderOpen] = useState(false);
  const [renameTarget, setRenameTarget] = useState<StorageFolder | null>(null);
  const [folderMutationError, setFolderMutationError] = useState("");
  const [folderMutationBusy, setFolderMutationBusy] = useState(false);
  const [toast, setToast] = useState<string>("");
  const [errorBanner, setErrorBanner] = useState<string>("");
  const [previewFile, setPreviewFile] = useState<StorageMediaListItem | null>(null);

  const currentFolderId = breadcrumbs[breadcrumbs.length - 1]?.folder_id ?? null;

  useEffect(() => {
    const handle = window.setTimeout(() => setDebouncedSearch(search.trim()), 250);
    return () => window.clearTimeout(handle);
  }, [search]);

  const resolvedKind = kind === "all" ? undefined : kind;

  const {
    folders,
    files,
    total,
    loading,
    error: libraryError,
    refresh,
  } = useMediaLibrary({
    clientId,
    folderId: currentFolderId,
    kind: resolvedKind,
    search: debouncedSearch || undefined,
    sort,
  });

  useEffect(() => {
    if (libraryError) setErrorBanner(libraryError);
  }, [libraryError]);

  useEffect(() => {
    if (!toast) return;
    const handle = window.setTimeout(() => setToast(""), 2500);
    return () => window.clearTimeout(handle);
  }, [toast]);

  const enterFolder = useCallback((folder: StorageFolder) => {
    setBreadcrumbs((prev) => [...prev, { folder_id: folder.folder_id, name: folder.name }]);
  }, []);

  const jumpTo = useCallback((index: number) => {
    setBreadcrumbs((prev) => prev.slice(0, index + 1));
  }, []);

  const openCreate = useCallback(() => {
    setFolderMutationError("");
    setCreateFolderOpen(true);
  }, []);

  const submitCreateFolder = useCallback(
    async (name: string) => {
      setFolderMutationBusy(true);
      setFolderMutationError("");
      try {
        await createFolder({ clientId, name, parentFolderId: currentFolderId });
        setCreateFolderOpen(false);
        setToast(`Folder "${name}" creat.`);
        refresh();
      } catch (err) {
        setFolderMutationError(err instanceof Error ? err.message : "Nu am putut crea folderul.");
      } finally {
        setFolderMutationBusy(false);
      }
    },
    [clientId, currentFolderId, refresh],
  );

  const submitRenameFolder = useCallback(
    async (name: string) => {
      if (!renameTarget) return;
      setFolderMutationBusy(true);
      setFolderMutationError("");
      try {
        await renameFolder({
          clientId,
          folderId: renameTarget.folder_id,
          name,
        });
        setRenameTarget(null);
        setToast(`Folder redenumit în "${name}".`);
        // If the renamed folder is in the breadcrumb path, update it.
        setBreadcrumbs((prev) =>
          prev.map((entry) =>
            entry.folder_id === renameTarget.folder_id ? { ...entry, name } : entry,
          ),
        );
        refresh();
      } catch (err) {
        setFolderMutationError(err instanceof Error ? err.message : "Nu am putut redenumi folderul.");
      } finally {
        setFolderMutationBusy(false);
      }
    },
    [clientId, renameTarget, refresh],
  );

  const handleDeleteFolder = useCallback(
    async (folder: StorageFolder) => {
      if (!window.confirm(`Ștergi folderul "${folder.name}"? Trebuie să fie gol în prealabil.`)) return;
      try {
        await deleteFolder({ clientId, folderId: folder.folder_id });
        setToast(`Folder șters.`);
        refresh();
      } catch (err) {
        const message = err instanceof Error ? err.message : "Nu am putut șterge folderul.";
        setErrorBanner(message);
      }
    },
    [clientId, refresh],
  );

  const hasFolders = folders.length > 0;
  const hasFiles = files.length > 0;
  const isEmpty = !loading && !hasFolders && !hasFiles;

  const kindOptions: Array<{ value: StorageKind | "all"; label: string }> = useMemo(
    () => [
      { value: "all", label: "Toate" },
      { value: "image", label: "Imagini" },
      { value: "video", label: "Video" },
      { value: "document", label: "Documente" },
    ],
    [],
  );

  const sortOptions: Array<{ value: StorageMediaSort; label: string }> = useMemo(
    () => [
      { value: "newest", label: "Modificat: Cele mai noi" },
      { value: "oldest", label: "Modificat: Cele mai vechi" },
      { value: "name_asc", label: "Nume A-Z" },
      { value: "name_desc", label: "Nume Z-A" },
    ],
    [],
  );

  const content = (
    <>
      {errorBanner ? (
        <div className="mb-3 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
          {errorBanner}
          <button
            type="button"
            onClick={() => setErrorBanner("")}
            className="ml-2 text-xs underline hover:no-underline"
          >
            închide
          </button>
        </div>
      ) : null}
      {toast ? (
        <div className="mb-3 rounded-md border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-700">
          {toast}
        </div>
      ) : null}

      <div className="mb-3 flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <nav className="flex items-center gap-1 text-xs text-slate-500 dark:text-slate-400">
          {breadcrumbs.map((entry, index) => (
            <span key={`${entry.folder_id ?? "root"}-${index}`} className="flex items-center gap-1">
              <button
                type="button"
                onClick={() => jumpTo(index)}
                className={
                  index === breadcrumbs.length - 1
                    ? "font-medium text-slate-900 dark:text-slate-100"
                    : "hover:text-slate-700 hover:underline dark:hover:text-slate-200"
                }
              >
                {index === 0 ? (
                  <span className="inline-flex items-center gap-1">
                    <Home className="h-3 w-3" />
                    {entry.name}
                  </span>
                ) : (
                  entry.name
                )}
              </button>
              {index < breadcrumbs.length - 1 && <ChevronRight className="h-3 w-3 text-slate-400" />}
            </span>
          ))}
        </nav>
        <div className="flex flex-wrap items-center gap-2">
          <div className="relative">
            <Search className="pointer-events-none absolute left-2 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
            <input
              type="search"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Caută fișiere..."
              className="wm-input h-9 w-56 pl-8 text-sm"
            />
          </div>
          <select
            value={sort}
            onChange={(event) => setSort(event.target.value as StorageMediaSort)}
            className="wm-input h-9 w-56 text-sm"
          >
            {sortOptions.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
          {!kindFilter && (
            <select
              value={kind}
              onChange={(event) => setKind(event.target.value as StorageKind | "all")}
              className="wm-input h-9 w-32 text-sm"
            >
              {kindOptions.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          )}
          {!readOnly && (
            <>
              <button
                type="button"
                onClick={openCreate}
                className="wm-btn-secondary inline-flex items-center gap-1.5 text-sm"
              >
                <FolderPlus className="h-4 w-4" />
                Folder nou
              </button>
              <MediaUploadZone
                clientId={clientId}
                folderId={currentFolderId}
                onUploaded={() => {
                  setToast("Fișier încărcat.");
                  refresh();
                }}
                onError={(message) => setErrorBanner(message)}
              />
            </>
          )}
        </div>
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-10 text-sm text-slate-500">
          <Loader2 className="mr-2 h-4 w-4 animate-spin" />
          Se încarcă fișierele media...
        </div>
      ) : null}

      {!loading && hasFolders ? (
        <div>
          <p className="mb-2 text-xs font-medium uppercase text-slate-500 dark:text-slate-400">Folders</p>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5">
            {folders.map((folder) => (
              <FolderCard
                key={folder.folder_id}
                folder={folder}
                onOpen={enterFolder}
                onRename={
                  readOnly
                    ? undefined
                    : (target) => {
                        setFolderMutationError("");
                        setRenameTarget(target);
                      }
                }
                onDelete={readOnly ? undefined : handleDeleteFolder}
              />
            ))}
          </div>
        </div>
      ) : null}

      {!loading && hasFiles ? (
        <div className="mt-5">
          <p className="mb-2 text-xs font-medium uppercase text-slate-500 dark:text-slate-400">
            Files ({total})
          </p>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5">
            {files.map((file) => (
              <FileCard
                key={file.media_id}
                clientId={clientId}
                file={file}
                onClick={onFileSelect ?? ((target) => setPreviewFile(target))}
              />
            ))}
          </div>
        </div>
      ) : null}

      {isEmpty ? (
        <div className="flex flex-col items-center justify-center rounded-md border border-dashed border-slate-300 py-16 text-sm text-slate-500 dark:border-slate-700 dark:text-slate-400">
          <p>Niciun fișier în acest folder.</p>
          {!readOnly && (
            <p className="mt-1 text-xs">Folosește butonul Upload pentru a adăuga primul fișier.</p>
          )}
        </div>
      ) : null}
    </>
  );

  return (
    <>
      {embed ? content : <div className="wm-card p-5">{content}</div>}

      <CreateFolderModal
        open={createFolderOpen}
        title={`Creează folder${breadcrumbs[breadcrumbs.length - 1]?.name && breadcrumbs.length > 1 ? ` în "${breadcrumbs[breadcrumbs.length - 1].name}"` : ""}`}
        submitLabel="Creează"
        submitting={folderMutationBusy}
        error={folderMutationError}
        onClose={() => setCreateFolderOpen(false)}
        onSubmit={submitCreateFolder}
      />
      <CreateFolderModal
        open={renameTarget !== null}
        title={`Redenumește "${renameTarget?.name ?? ""}"`}
        initialName={renameTarget?.name ?? ""}
        submitLabel="Salvează"
        submitting={folderMutationBusy}
        error={folderMutationError}
        onClose={() => setRenameTarget(null)}
        onSubmit={submitRenameFolder}
      />
      {!onFileSelect && (
        <MediaPreviewModal
          clientId={clientId}
          file={previewFile}
          onClose={() => setPreviewFile(null)}
          onChanged={refresh}
          onError={(message) => setErrorBanner(message)}
        />
      )}
    </>
  );
}
