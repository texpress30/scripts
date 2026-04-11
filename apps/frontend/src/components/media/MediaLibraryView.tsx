"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Check,
  ChevronDown,
  ChevronRight,
  Cloud,
  FileText,
  Film,
  FolderPlus,
  Grid3x3,
  Home,
  Image as ImageIcon,
  LayoutGrid,
  List,
  Loader2,
  Music,
  MoreVertical,
  Search,
  Trash2,
} from "lucide-react";

import { useMediaLibrary } from "@/lib/hooks/useMediaLibrary";
import {
  createFolder,
  deleteFolder,
  getFolderAncestors,
  getMediaSummary,
  renameFolder,
  type StorageFolder,
  type StorageKind,
  type StorageMediaListItem,
  type StorageMediaSort,
} from "@/lib/storage-client";
import { cn } from "@/lib/utils";

import { CreateFolderModal } from "./CreateFolderModal";
import { FileCard } from "./FileCard";
import { FolderCard } from "./FolderCard";
import { MediaPreviewModal } from "./MediaPreviewModal";
import { MediaThumbnail } from "./MediaThumbnail";
import { MediaUploadZone } from "./MediaUploadZone";

type BreadcrumbEntry = {
  folder_id: string | null;
  name: string;
};

type KindFilterValue = StorageKind | "all";
type ViewMode = "grid" | "list";

type MediaLibraryViewProps = {
  clientId: number;
  /** Render the header row with title + action buttons. */
  showHeader?: boolean;
  /** When `embed=true`, skip the outer card wrapper — used inside pickers. */
  embed?: boolean;
  /** Click handler for files (picker mode). When set, clicking a file does
   *  NOT open the preview modal. */
  onFileSelect?: (file: StorageMediaListItem) => void;
  /** Force a specific kind filter (and hide the selector). */
  kindFilter?: StorageKind;
  /** Hide upload/delete/create-folder actions. */
  readOnly?: boolean;
};

function formatBytes(bytes: number | null | undefined): string {
  if (!bytes || bytes <= 0) return "0 B";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`;
}

const SHORT_DATE_MONTHS = [
  "Ian",
  "Feb",
  "Mar",
  "Apr",
  "Mai",
  "Iun",
  "Iul",
  "Aug",
  "Sep",
  "Oct",
  "Noi",
  "Dec",
];

function formatShortDate(value: string | null | undefined): string {
  if (!value) return "-";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return "-";
  const month = SHORT_DATE_MONTHS[parsed.getMonth()] || "";
  return `${month} ${parsed.getDate()}, ${parsed.getFullYear()}`;
}

const PAGE_SIZE_OPTIONS = [10, 25, 50, 100];

const SORT_OPTIONS: Array<{ value: StorageMediaSort; label: string }> = [
  { value: "name_asc", label: "Nume: A la Z" },
  { value: "name_desc", label: "Nume: Z la A" },
  { value: "size_asc", label: "Mărime: Crescător" },
  { value: "size_desc", label: "Mărime: Descrescător" },
  { value: "newest", label: "Modificat: Cele mai noi" },
  { value: "oldest", label: "Modificat: Cele mai vechi" },
];

const KIND_OPTIONS: Array<{ value: KindFilterValue; label: string; Icon: typeof ImageIcon }> = [
  { value: "all", label: "Toate", Icon: Grid3x3 },
  { value: "image", label: "Poze", Icon: ImageIcon },
  { value: "video", label: "Videoclipuri", Icon: Film },
  { value: "audio", label: "Audio", Icon: Music },
  { value: "document", label: "Documente", Icon: FileText },
  { value: "other", label: "Altele", Icon: LayoutGrid },
];

function sortLabel(value: StorageMediaSort): string {
  return SORT_OPTIONS.find((option) => option.value === value)?.label ?? "Modificat: Cele mai noi";
}

function kindLabel(value: KindFilterValue): string {
  return KIND_OPTIONS.find((option) => option.value === value)?.label ?? "Toate";
}

export function MediaLibraryView({
  clientId,
  showHeader = true,
  embed = false,
  onFileSelect,
  kindFilter,
  readOnly = false,
}: MediaLibraryViewProps) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  // Only the "main page" usage of MediaLibraryView should drive/read the URL
  // query param. Embedded usages (e.g. inside the MediaPicker modal) keep
  // their own local breadcrumb state so navigating a folder in the picker
  // doesn't pollute the host page's URL.
  const urlSyncEnabled = !embed;
  const urlFolderId = urlSyncEnabled ? searchParams?.get("folder") || null : null;

  const [breadcrumbs, setBreadcrumbs] = useState<BreadcrumbEntry[]>([{ folder_id: null, name: "Home" }]);
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [sort, setSort] = useState<StorageMediaSort>("newest");
  const [kind, setKind] = useState<KindFilterValue>(kindFilter ?? "all");
  const [viewMode, setViewMode] = useState<ViewMode>("grid");
  const [foldersExpanded, setFoldersExpanded] = useState(true);
  const [createFolderOpen, setCreateFolderOpen] = useState(false);
  const [renameTarget, setRenameTarget] = useState<StorageFolder | null>(null);
  const [folderMutationError, setFolderMutationError] = useState("");
  const [folderMutationBusy, setFolderMutationBusy] = useState(false);
  const [toast, setToast] = useState<string>("");
  const [errorBanner, setErrorBanner] = useState<string>("");
  const [previewFile, setPreviewFile] = useState<StorageMediaListItem | null>(null);
  const [sortMenuOpen, setSortMenuOpen] = useState(false);
  const [kindMenuOpen, setKindMenuOpen] = useState(false);
  const [optionsMenuOpen, setOptionsMenuOpen] = useState(false);
  const [summary, setSummary] = useState<{ total_files: number; total_bytes: number } | null>(null);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(() => new Set());
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [pageSizeMenuOpen, setPageSizeMenuOpen] = useState(false);

  const currentFolderId = breadcrumbs[breadcrumbs.length - 1]?.folder_id ?? null;

  // Restore the breadcrumb from the `?folder=...` query param on mount /
  // whenever it changes (e.g. browser back/forward), by fetching the
  // folder's ancestor chain from the backend.
  useEffect(() => {
    if (!Number.isFinite(clientId) || clientId <= 0) return;
    if (!urlFolderId) {
      setBreadcrumbs([{ folder_id: null, name: "Home" }]);
      return;
    }
    // Avoid re-fetching if we already have the right folder in state.
    const lastEntry = breadcrumbs[breadcrumbs.length - 1];
    if (lastEntry && lastEntry.folder_id === urlFolderId) return;

    let cancelled = false;
    (async () => {
      try {
        const response = await getFolderAncestors({ clientId, folderId: urlFolderId });
        if (cancelled) return;
        const nextBreadcrumbs: BreadcrumbEntry[] = [
          { folder_id: null, name: "Home" },
          ...response.items.map((folder) => ({
            folder_id: folder.folder_id,
            name: folder.name,
          })),
        ];
        setBreadcrumbs(nextBreadcrumbs);
      } catch {
        if (!cancelled) setBreadcrumbs([{ folder_id: null, name: "Home" }]);
      }
    })();
    return () => {
      cancelled = true;
    };
    // Intentionally omitting `breadcrumbs` from deps — we only want this
    // effect to react to url/clientId changes, not to every breadcrumb
    // mutation triggered by in-page navigation.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [clientId, urlFolderId]);

  const pushFolderToUrl = useCallback(
    (folderId: string | null) => {
      if (!urlSyncEnabled || !pathname) return;
      const params = new URLSearchParams(searchParams?.toString() ?? "");
      if (folderId) params.set("folder", folderId);
      else params.delete("folder");
      const nextQuery = params.toString();
      const nextUrl = nextQuery ? `${pathname}?${nextQuery}` : pathname;
      router.replace(nextUrl, { scroll: false });
    },
    [pathname, router, searchParams, urlSyncEnabled],
  );

  useEffect(() => {
    const handle = window.setTimeout(() => setDebouncedSearch(search.trim()), 250);
    return () => window.clearTimeout(handle);
  }, [search]);

  const resolvedKind: StorageKind | undefined = kind === "all" ? undefined : kind;

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
    limit: pageSize,
    offset: (page - 1) * pageSize,
  });

  // Reset to page 1 when any filter / navigation changes so the pagination
  // doesn't point at an empty page of the new result set.
  useEffect(() => {
    setPage(1);
  }, [currentFolderId, debouncedSearch, sort, kind, pageSize]);

  // Drop stale selections when the visible rows change.
  useEffect(() => {
    setSelectedIds((prev) => {
      if (prev.size === 0) return prev;
      const visible = new Set(files.map((file) => file.media_id));
      const next = new Set<string>();
      prev.forEach((id) => {
        if (visible.has(id)) next.add(id);
      });
      return next.size === prev.size ? prev : next;
    });
  }, [files]);

  const totalPages = Math.max(1, Math.ceil((total || 0) / pageSize));
  const canGoPrev = page > 1;
  const canGoNext = page < totalPages;

  useEffect(() => {
    if (libraryError) setErrorBanner(libraryError);
  }, [libraryError]);

  useEffect(() => {
    if (!toast) return;
    const handle = window.setTimeout(() => setToast(""), 2500);
    return () => window.clearTimeout(handle);
  }, [toast]);

  const refreshSummary = useCallback(() => {
    if (!Number.isFinite(clientId) || clientId <= 0) return;
    let cancelled = false;
    (async () => {
      try {
        const result = await getMediaSummary({ clientId });
        if (!cancelled) setSummary(result);
      } catch {
        if (!cancelled) setSummary(null);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [clientId]);

  useEffect(() => {
    refreshSummary();
  }, [refreshSummary]);

  const enterFolder = useCallback(
    (folder: StorageFolder) => {
      setBreadcrumbs((prev) => [...prev, { folder_id: folder.folder_id, name: folder.name }]);
      pushFolderToUrl(folder.folder_id);
    },
    [pushFolderToUrl],
  );

  const jumpTo = useCallback(
    (index: number) => {
      setBreadcrumbs((prev) => {
        const next = prev.slice(0, index + 1);
        const target = next[next.length - 1];
        pushFolderToUrl(target?.folder_id ?? null);
        return next;
      });
    },
    [pushFolderToUrl],
  );

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
        await renameFolder({ clientId, folderId: renameTarget.folder_id, name });
        setRenameTarget(null);
        setToast(`Folder redenumit în "${name}".`);
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
      if (!window.confirm(`Ștergi folderul "${folder.name}"? Trebuie să fie gol.`)) return;
      try {
        await deleteFolder({ clientId, folderId: folder.folder_id });
        setToast("Folder șters.");
        refresh();
      } catch (err) {
        setErrorBanner(err instanceof Error ? err.message : "Nu am putut șterge folderul.");
      }
    },
    [clientId, refresh],
  );

  const hasFolders = folders.length > 0;
  const hasFiles = files.length > 0;
  const isEmpty = !loading && !hasFolders && !hasFiles;
  const storageLabel = summary ? `Stocare ${formatBytes(summary.total_bytes)} utilizați` : "Stocare ...";

  const header = showHeader ? (
    <div className="mb-5 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
      <h1 className="text-xl font-semibold text-slate-900 dark:text-slate-100">Stocare Media</h1>
      {!readOnly && (
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={openCreate}
            title="Folder nou"
            className="inline-flex h-9 w-9 items-center justify-center rounded-lg border border-slate-200 bg-white text-slate-600 hover:bg-slate-50 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300 dark:hover:bg-slate-800"
          >
            <FolderPlus className="h-4 w-4" />
          </button>
          <MediaUploadZone
            clientId={clientId}
            folderId={currentFolderId}
            onUploaded={() => {
              setToast("Fișier încărcat.");
              refresh();
              refreshSummary();
            }}
            onError={(message) => setErrorBanner(message)}
            label="Încarcă"
          />
          <div className="relative">
            <button
              type="button"
              onClick={() => setOptionsMenuOpen((prev) => !prev)}
              className="inline-flex h-9 w-9 items-center justify-center rounded-lg border border-slate-200 bg-white text-slate-600 hover:bg-slate-50 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300 dark:hover:bg-slate-800"
              aria-label="Mai multe opțiuni"
            >
              <MoreVertical className="h-4 w-4" />
            </button>
            {optionsMenuOpen && (
              <>
                <div className="fixed inset-0 z-30" onClick={() => setOptionsMenuOpen(false)} />
                <div className="absolute right-0 top-full z-40 mt-1 w-64 overflow-hidden rounded-lg border border-slate-200 bg-white shadow-lg dark:border-slate-700 dark:bg-slate-900">
                  <button
                    type="button"
                    disabled
                    className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-slate-500 disabled:cursor-not-allowed dark:text-slate-400"
                    title="În curând"
                  >
                    <Trash2 className="h-4 w-4" />
                    Coș de gunoi
                  </button>
                  <div className="flex w-full items-center gap-2 border-t border-slate-100 px-3 py-2 text-sm text-slate-600 dark:border-slate-800 dark:text-slate-300">
                    <Cloud className="h-4 w-4" />
                    {storageLabel}
                  </div>
                </div>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  ) : null;

  const toolbar = (
    <div className="mb-4 flex flex-wrap items-center gap-2">
      <button
        type="button"
        className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200 dark:hover:bg-slate-800"
        title="Scope: My Media"
      >
        Media Mea
        <ChevronDown className="h-4 w-4 text-slate-400" />
      </button>

      <div className="relative min-w-0 flex-1">
        <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
        <input
          type="search"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          placeholder="Caută fișiere media sau explorează imagini stock."
          className="wm-input h-9 pl-9 text-sm"
        />
      </div>

      {!kindFilter && (
        <div className="relative">
          <button
            type="button"
            onClick={() => {
              setSortMenuOpen((prev) => !prev);
              setKindMenuOpen(false);
            }}
            className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-sm text-slate-700 hover:bg-slate-50 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200 dark:hover:bg-slate-800"
          >
            {sortLabel(sort)}
            <ChevronDown className="h-4 w-4 text-slate-400" />
          </button>
          {sortMenuOpen && (
            <>
              <div className="fixed inset-0 z-30" onClick={() => setSortMenuOpen(false)} />
              <div className="absolute right-0 top-full z-40 mt-1 w-56 overflow-hidden rounded-lg border border-slate-200 bg-white shadow-lg dark:border-slate-700 dark:bg-slate-900">
                {SORT_OPTIONS.map((option) => {
                  const active = option.value === sort;
                  return (
                    <button
                      key={option.value}
                      type="button"
                      onClick={() => {
                        setSort(option.value);
                        setSortMenuOpen(false);
                      }}
                      className={cn(
                        "flex w-full items-center justify-between gap-2 px-3 py-2 text-left text-sm",
                        active
                          ? "bg-indigo-50 text-indigo-700 dark:bg-indigo-950/40 dark:text-indigo-300"
                          : "text-slate-700 hover:bg-slate-50 dark:text-slate-200 dark:hover:bg-slate-800",
                      )}
                    >
                      <span>{option.label}</span>
                      {active && <Check className="h-4 w-4 text-indigo-600 dark:text-indigo-400" />}
                    </button>
                  );
                })}
              </div>
            </>
          )}
        </div>
      )}

      {!kindFilter && (
        <div className="relative">
          <button
            type="button"
            onClick={() => {
              setKindMenuOpen((prev) => !prev);
              setSortMenuOpen(false);
            }}
            className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-sm text-slate-700 hover:bg-slate-50 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200 dark:hover:bg-slate-800"
          >
            {kindLabel(kind)}
            <ChevronDown className="h-4 w-4 text-slate-400" />
          </button>
          {kindMenuOpen && (
            <>
              <div className="fixed inset-0 z-30" onClick={() => setKindMenuOpen(false)} />
              <div className="absolute right-0 top-full z-40 mt-1 w-52 overflow-hidden rounded-lg border border-slate-200 bg-white shadow-lg dark:border-slate-700 dark:bg-slate-900">
                {KIND_OPTIONS.map((option) => {
                  const active = option.value === kind;
                  const Icon = option.Icon;
                  return (
                    <button
                      key={option.value}
                      type="button"
                      onClick={() => {
                        setKind(option.value);
                        setKindMenuOpen(false);
                      }}
                      className={cn(
                        "flex w-full items-center gap-2 px-3 py-2 text-left text-sm",
                        active
                          ? "bg-indigo-50 text-indigo-700 dark:bg-indigo-950/40 dark:text-indigo-300"
                          : "text-slate-700 hover:bg-slate-50 dark:text-slate-200 dark:hover:bg-slate-800",
                      )}
                    >
                      <Icon className="h-4 w-4 shrink-0" />
                      <span className="flex-1">{option.label}</span>
                      {active && <Check className="h-4 w-4 text-indigo-600 dark:text-indigo-400" />}
                    </button>
                  );
                })}
              </div>
            </>
          )}
        </div>
      )}

      <div className="inline-flex overflow-hidden rounded-lg border border-slate-200 dark:border-slate-700">
        <button
          type="button"
          onClick={() => setViewMode("grid")}
          title="Vizualizare grilă"
          className={cn(
            "inline-flex h-9 w-9 items-center justify-center transition-colors",
            viewMode === "grid"
              ? "bg-indigo-50 text-indigo-700 dark:bg-indigo-950/40 dark:text-indigo-300"
              : "bg-white text-slate-500 hover:bg-slate-50 dark:bg-slate-900 dark:text-slate-400 dark:hover:bg-slate-800",
          )}
        >
          <LayoutGrid className="h-4 w-4" />
        </button>
        <button
          type="button"
          onClick={() => setViewMode("list")}
          title="Vizualizare listă"
          className={cn(
            "inline-flex h-9 w-9 items-center justify-center border-l border-slate-200 transition-colors dark:border-slate-700",
            viewMode === "list"
              ? "bg-indigo-50 text-indigo-700 dark:bg-indigo-950/40 dark:text-indigo-300"
              : "bg-white text-slate-500 hover:bg-slate-50 dark:bg-slate-900 dark:text-slate-400 dark:hover:bg-slate-800",
          )}
        >
          <List className="h-4 w-4" />
        </button>
      </div>
    </div>
  );

  const breadcrumb = (
    <nav className="mb-3 flex items-center gap-1 text-xs text-slate-500 dark:text-slate-400">
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
  );

  const foldersSection = hasFolders ? (
    <div className="mb-5">
      <button
        type="button"
        onClick={() => setFoldersExpanded((prev) => !prev)}
        className="mb-2 inline-flex items-center gap-1 text-sm font-medium text-slate-700 hover:text-slate-900 dark:text-slate-300 dark:hover:text-slate-100"
      >
        Dosare
        <ChevronDown
          className={cn(
            "h-4 w-4 transition-transform",
            !foldersExpanded && "-rotate-90",
          )}
        />
      </button>
      {foldersExpanded && (
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
      )}
    </div>
  ) : null;

  const allVisibleSelected =
    files.length > 0 && files.every((file) => selectedIds.has(file.media_id));

  const toggleSelectAll = () => {
    setSelectedIds((prev) => {
      if (files.length === 0) return prev;
      if (files.every((file) => prev.has(file.media_id))) {
        const next = new Set(prev);
        files.forEach((file) => next.delete(file.media_id));
        return next;
      }
      const next = new Set(prev);
      files.forEach((file) => next.add(file.media_id));
      return next;
    });
  };

  const toggleRowSelected = (mediaId: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(mediaId)) next.delete(mediaId);
      else next.add(mediaId);
      return next;
    });
  };

  const openFileAction = (file: StorageMediaListItem) =>
    (onFileSelect ?? ((target) => setPreviewFile(target)))(file);

  const filesSection = hasFiles ? (
    <div>
      <p className="mb-2 text-sm font-medium text-slate-700 dark:text-slate-300">Fișiere ({total})</p>
      {viewMode === "grid" ? (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5">
          {files.map((file) => (
            <FileCard
              key={file.media_id}
              clientId={clientId}
              file={file}
              selected={selectedIds.has(file.media_id)}
              onClick={openFileAction}
            />
          ))}
        </div>
      ) : (
        <div className="overflow-hidden rounded-lg border border-slate-200 dark:border-slate-700">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-xs font-medium uppercase text-slate-500 dark:bg-slate-800/60 dark:text-slate-400">
              <tr>
                <th className="w-10 px-3 py-2">
                  <input
                    type="checkbox"
                    aria-label="Selectează tot"
                    checked={allVisibleSelected}
                    onChange={toggleSelectAll}
                    className="h-4 w-4 cursor-pointer rounded border-slate-300 text-indigo-600 focus:ring-indigo-500"
                  />
                </th>
                <th className="w-16 px-3 py-2 text-left">Media</th>
                <th className="px-3 py-2 text-left">Nume</th>
                <th className="w-36 px-3 py-2 text-left">Actualizat la</th>
                <th className="w-28 px-3 py-2 text-left">Mărime</th>
                <th className="w-28 px-3 py-2 text-left">Dimensiuni</th>
                <th className="w-16 px-3 py-2 text-right">Acțiuni</th>
              </tr>
            </thead>
            <tbody>
              {files.map((file) => {
                const label = file.display_name || file.original_filename;
                const isSelected = selectedIds.has(file.media_id);
                return (
                  <tr
                    key={file.media_id}
                    className={cn(
                      "border-t border-slate-200 text-slate-700 transition-colors dark:border-slate-700 dark:text-slate-200",
                      isSelected
                        ? "bg-indigo-50/60 dark:bg-indigo-950/30"
                        : "hover:bg-slate-50 dark:hover:bg-slate-800",
                    )}
                  >
                    <td
                      className="w-10 px-3 py-2 align-middle"
                      onClick={(event) => event.stopPropagation()}
                    >
                      <input
                        type="checkbox"
                        aria-label={`Selectează ${label}`}
                        checked={isSelected}
                        onChange={() => toggleRowSelected(file.media_id)}
                        className="h-4 w-4 cursor-pointer rounded border-slate-300 text-indigo-600 focus:ring-indigo-500"
                      />
                    </td>
                    <td className="w-16 px-3 py-2 align-middle">
                      <button
                        type="button"
                        onClick={() => openFileAction(file)}
                        className="block h-11 w-11 overflow-hidden rounded-md border border-slate-200 bg-slate-50 dark:border-slate-700 dark:bg-slate-800"
                        title={label}
                      >
                        <MediaThumbnail
                          clientId={clientId}
                          mediaId={file.media_id}
                          kind={file.kind}
                          displayName={label}
                        />
                      </button>
                    </td>
                    <td className="px-3 py-2 align-middle">
                      <button
                        type="button"
                        onClick={() => openFileAction(file)}
                        className="truncate text-left text-sm font-medium text-slate-800 hover:text-indigo-700 dark:text-slate-100 dark:hover:text-indigo-300"
                        title={label}
                      >
                        {label}
                      </button>
                    </td>
                    <td className="px-3 py-2 align-middle text-xs text-slate-500 dark:text-slate-400">
                      {formatShortDate(file.uploaded_at || file.created_at)}
                    </td>
                    <td className="px-3 py-2 align-middle text-xs text-slate-500 dark:text-slate-400">
                      {formatBytes(file.size_bytes)}
                    </td>
                    <td className="px-3 py-2 align-middle text-xs text-slate-500 dark:text-slate-400">-</td>
                    <td
                      className="px-3 py-2 align-middle text-right"
                      onClick={(event) => event.stopPropagation()}
                    >
                      <button
                        type="button"
                        onClick={() => openFileAction(file)}
                        className="inline-flex h-8 w-8 items-center justify-center rounded-md text-slate-400 hover:bg-slate-100 hover:text-slate-600 dark:hover:bg-slate-800 dark:hover:text-slate-200"
                        aria-label={`Acțiuni pentru ${label}`}
                      >
                        <MoreVertical className="h-4 w-4" />
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {total > 0 && (
        <div className="mt-3 flex flex-wrap items-center justify-end gap-2 text-sm">
          <button
            type="button"
            onClick={() => canGoPrev && setPage((prev) => Math.max(1, prev - 1))}
            disabled={!canGoPrev}
            className="inline-flex h-8 items-center rounded-md border border-slate-200 bg-white px-3 text-slate-700 transition-colors hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200 dark:hover:bg-slate-800"
          >
            Precedent
          </button>
          <span className="inline-flex h-8 items-center rounded-md border border-indigo-300 bg-indigo-50 px-3 font-medium text-indigo-700 dark:border-indigo-700 dark:bg-indigo-950/40 dark:text-indigo-300">
            {page}
          </span>
          <button
            type="button"
            onClick={() => canGoNext && setPage((prev) => Math.min(totalPages, prev + 1))}
            disabled={!canGoNext}
            className="inline-flex h-8 items-center rounded-md border border-slate-200 bg-white px-3 text-slate-700 transition-colors hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200 dark:hover:bg-slate-800"
          >
            Următorul
          </button>
          <div className="relative">
            <button
              type="button"
              onClick={() => setPageSizeMenuOpen((prev) => !prev)}
              className="inline-flex h-8 items-center gap-1.5 rounded-md border border-slate-200 bg-white px-3 text-slate-700 transition-colors hover:bg-slate-50 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200 dark:hover:bg-slate-800"
            >
              {pageSize} / pagină
              <ChevronDown className="h-3.5 w-3.5 text-slate-400" />
            </button>
            {pageSizeMenuOpen && (
              <>
                <div className="fixed inset-0 z-30" onClick={() => setPageSizeMenuOpen(false)} />
                <div className="absolute bottom-full right-0 z-40 mb-1 w-32 overflow-hidden rounded-md border border-slate-200 bg-white shadow-lg dark:border-slate-700 dark:bg-slate-900">
                  {PAGE_SIZE_OPTIONS.map((option) => {
                    const active = option === pageSize;
                    return (
                      <button
                        key={option}
                        type="button"
                        onClick={() => {
                          setPageSize(option);
                          setPageSizeMenuOpen(false);
                        }}
                        className={cn(
                          "flex w-full items-center justify-between px-3 py-2 text-left text-sm",
                          active
                            ? "bg-indigo-50 text-indigo-700 dark:bg-indigo-950/40 dark:text-indigo-300"
                            : "text-slate-700 hover:bg-slate-50 dark:text-slate-200 dark:hover:bg-slate-800",
                        )}
                      >
                        <span>{option} / pagină</span>
                        {active && <Check className="h-4 w-4 text-indigo-600 dark:text-indigo-400" />}
                      </button>
                    );
                  })}
                </div>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  ) : null;

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

      {breadcrumb}
      {toolbar}

      {loading ? (
        <div className="flex items-center justify-center py-10 text-sm text-slate-500">
          <Loader2 className="mr-2 h-4 w-4 animate-spin" />
          Se încarcă fișierele media...
        </div>
      ) : null}

      {!loading && foldersSection}
      {!loading && filesSection}

      {isEmpty ? (
        <div className="flex flex-col items-center justify-center rounded-md border border-dashed border-slate-300 py-16 text-sm text-slate-500 dark:border-slate-700 dark:text-slate-400">
          <p>Niciun fișier în acest folder.</p>
          {!readOnly && (
            <p className="mt-1 text-xs">Folosește butonul Încarcă pentru a adăuga primul fișier.</p>
          )}
        </div>
      ) : null}
    </>
  );

  return (
    <>
      {header}
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
          onChanged={() => {
            refresh();
            refreshSummary();
          }}
          onError={(message) => setErrorBanner(message)}
        />
      )}
    </>
  );
}
