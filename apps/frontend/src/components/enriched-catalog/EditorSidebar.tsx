"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { Rss, Image, Shapes, BookOpen, Layers, Search, ChevronLeft, ChevronRight, Loader2, Upload, RefreshCw, SlidersHorizontal, Check, Shuffle, Eraser, Folder, X } from "lucide-react";
import { cn } from "@/lib/utils";
import { fetchMediaBlob, listFolders, listMedia, type StorageFolder, type StorageMediaListItem } from "@/lib/storage-client";

export type SidebarTab = "source_feed" | "image_assets" | "graphic_assets" | "library" | "layers";

const SIDEBAR_TABS: { key: SidebarTab; label: string; icon: typeof Rss }[] = [
  { key: "source_feed", label: "Source Feed", icon: Rss },
  { key: "image_assets", label: "Images", icon: Image },
  { key: "graphic_assets", label: "Graphics", icon: Shapes },
  { key: "library", label: "Elemente Publice", icon: BookOpen },
  { key: "layers", label: "Layers", icon: Layers },
];

interface EditorSidebarProps {
  activeTab: SidebarTab;
  onTabChange: (tab: SidebarTab) => void;
  collapsed: boolean;
  onToggleCollapse: () => void;
  children: React.ReactNode;
}

export function EditorSidebar({ activeTab, onTabChange, collapsed, onToggleCollapse, children }: EditorSidebarProps) {
  return (
    <div className="flex h-full border-r border-slate-200 dark:border-slate-700">
      {/* Icon rail */}
      <div className="flex w-12 flex-col items-center gap-1 border-r border-slate-200 bg-slate-50 py-2 dark:border-slate-700 dark:bg-slate-900">
        {SIDEBAR_TABS.map((tab) => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.key;
          return (
            <button
              key={tab.key}
              onClick={() => { onTabChange(tab.key); if (collapsed) onToggleCollapse(); }}
              className={cn(
                "flex h-10 w-10 items-center justify-center rounded-lg transition",
                isActive
                  ? "bg-indigo-100 text-indigo-700 dark:bg-indigo-900/30 dark:text-indigo-400"
                  : "text-slate-500 hover:bg-slate-200 hover:text-slate-700 dark:text-slate-400 dark:hover:bg-slate-800 dark:hover:text-slate-300",
              )}
              title={tab.label}
            >
              <Icon className="h-5 w-5" />
            </button>
          );
        })}

        <div className="mt-auto">
          <button
            onClick={onToggleCollapse}
            className="flex h-8 w-8 items-center justify-center rounded text-slate-400 hover:text-slate-600 dark:hover:text-slate-300"
          >
            {collapsed ? <ChevronRight className="h-4 w-4" /> : <ChevronLeft className="h-4 w-4" />}
          </button>
        </div>
      </div>

      {/* Panel content */}
      {!collapsed && (
        <div className="flex w-64 flex-col bg-white dark:bg-slate-800">
          <div className="border-b border-slate-200 px-3 py-2.5 dark:border-slate-700">
            <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
              {SIDEBAR_TABS.find((t) => t.key === activeTab)?.label}
            </h3>
          </div>
          <div className="flex-1 overflow-y-auto">
            {children}
          </div>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Source Feed Panel
// ---------------------------------------------------------------------------

interface SourceFeedPanelProps {
  products: Record<string, unknown>[];
  columns: { key: string; label: string; type: string }[];
  isLoading: boolean;
  currentProductIndex: number;
  onProductChange: (index: number) => void;
  totalProducts: number;
  onFieldClick: (fieldKey: string, value: string) => void;
}

export function SourceFeedPanel({
  products, columns, isLoading, currentProductIndex, onProductChange, totalProducts, onFieldClick,
}: SourceFeedPanelProps) {
  const [search, setSearch] = useState("");
  const [showFilterMenu, setShowFilterMenu] = useState(false);
  const [selectedFields, setSelectedFields] = useState<Set<string>>(() => new Set(columns.map((c) => c.key)));
  const product = products[currentProductIndex] ?? {};

  // Keep selectedFields in sync when columns change (e.g. new feed loaded)
  const columnsKeyRef = columns.map((c) => c.key).join(",");
  const [prevColumnsKey, setPrevColumnsKey] = useState(columnsKeyRef);
  if (columnsKeyRef !== prevColumnsKey) {
    setPrevColumnsKey(columnsKeyRef);
    setSelectedFields(new Set(columns.map((c) => c.key)));
  }

  // Group columns by category for the filter
  const imageColKeys = columns.filter((c) => c.type === "image" || c.type === "url" && c.key.includes("image")).map((c) => c.key);
  const priceColKeys = columns.filter((c) => c.type === "price" || c.key.includes("price")).map((c) => c.key);
  const otherColKeys = columns.filter((c) => !imageColKeys.includes(c.key) && !priceColKeys.includes(c.key)).map((c) => c.key);

  const allSelected = selectedFields.size === columns.length;
  const groupAllSelected = (keys: string[]) => keys.length > 0 && keys.every((k) => selectedFields.has(k));
  const groupNoneSelected = (keys: string[]) => keys.length > 0 && keys.every((k) => !selectedFields.has(k));

  const toggleAll = () => {
    if (allSelected) setSelectedFields(new Set());
    else setSelectedFields(new Set(columns.map((c) => c.key)));
  };

  const toggleGroup = (keys: string[]) => {
    setSelectedFields((prev) => {
      const next = new Set(prev);
      const allIn = keys.every((k) => next.has(k));
      keys.forEach((k) => { if (allIn) next.delete(k); else next.add(k); });
      return next;
    });
  };

  const toggleField = (key: string) => {
    setSelectedFields((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  };

  const filteredColumns = columns.filter((col) => {
    const matchesSearch = !search || col.key.toLowerCase().includes(search.toLowerCase()) || col.label.toLowerCase().includes(search.toLowerCase());
    const matchesFilter = selectedFields.has(col.key);
    return matchesSearch && matchesFilter;
  });

  // Group columns by type
  const imageColumns = filteredColumns.filter((c) => c.type === "image" || c.type === "url" && c.key.includes("image"));
  const priceColumns = filteredColumns.filter((c) => c.type === "price" || c.key.includes("price"));
  const textColumns = filteredColumns.filter((c) => !imageColumns.includes(c) && !priceColumns.includes(c));

  if (isLoading) {
    return (
      <div className="flex h-40 items-center justify-center">
        <Loader2 className="h-5 w-5 animate-spin text-slate-400" />
      </div>
    );
  }

  if (products.length === 0) {
    return (
      <div className="p-3 text-center text-xs text-slate-400">
        No products in feed. Import products from Feed Management first.
      </div>
    );
  }

  const handleShuffle = () => {
    if (totalProducts <= 1) return;
    let next = currentProductIndex;
    while (next === currentProductIndex) {
      next = Math.floor(Math.random() * totalProducts);
    }
    onProductChange(next);
  };

  return (
    <div className="p-2">
      {/* Shuffle hint */}
      <div className="mb-2 flex items-center gap-2 rounded bg-slate-50 px-2 py-1.5 dark:bg-slate-900">
        <button
          onClick={handleShuffle}
          disabled={totalProducts <= 1}
          className="flex items-center gap-1.5 rounded px-2 py-1 text-xs text-indigo-600 hover:bg-indigo-50 disabled:opacity-30 dark:text-indigo-400 dark:hover:bg-indigo-900/20"
          title="Shuffle through different product rows in the source feed"
        >
          <Shuffle className="h-3.5 w-3.5" />
          Shuffle
        </button>
        <div className="ml-auto flex items-center gap-1">
          <button
            onClick={() => onProductChange(Math.max(0, currentProductIndex - 1))}
            disabled={currentProductIndex === 0}
            className="rounded p-0.5 text-slate-400 hover:text-slate-600 disabled:opacity-30"
          >
            <ChevronLeft className="h-3.5 w-3.5" />
          </button>
          <span className="text-[10px] text-slate-400 dark:text-slate-500">
            {currentProductIndex + 1}/{totalProducts}
          </span>
          <button
            onClick={() => onProductChange(Math.min(totalProducts - 1, currentProductIndex + 1))}
            disabled={currentProductIndex >= totalProducts - 1}
            className="rounded p-0.5 text-slate-400 hover:text-slate-600 disabled:opacity-30"
          >
            <ChevronRight className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>

      {/* Search + Filter */}
      <div className="relative mb-3 flex items-center gap-1.5">
        <div className="relative flex-1">
          <Search className="absolute left-2 top-2 h-3.5 w-3.5 text-slate-400" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search fields..."
            className="mcc-input w-full rounded border py-1.5 pl-7 pr-2 text-xs"
          />
        </div>
        <div className="relative">
          <button
            onClick={() => setShowFilterMenu(!showFilterMenu)}
            className={cn(
              "flex h-[30px] w-[30px] items-center justify-center rounded border transition",
              !allSelected
                ? "border-indigo-400 bg-indigo-50 text-indigo-600 dark:border-indigo-500 dark:bg-indigo-900/30 dark:text-indigo-400"
                : "border-slate-200 text-slate-400 hover:border-slate-300 hover:text-slate-600 dark:border-slate-600 dark:hover:border-slate-500 dark:hover:text-slate-300",
            )}
            title="Filter fields"
          >
            <SlidersHorizontal className="h-3.5 w-3.5" />
          </button>
          {showFilterMenu && (
            <>
              <div className="fixed inset-0 z-10" onClick={() => setShowFilterMenu(false)} />
              <div className="absolute right-0 top-full z-20 mt-1 max-h-72 w-52 overflow-y-auto rounded-md border border-slate-200 bg-white py-1 shadow-lg dark:border-slate-600 dark:bg-slate-700">
                {/* All Fields */}
                <button
                  onClick={toggleAll}
                  className="flex w-full items-center gap-2 border-b border-slate-100 px-3 py-2 text-left text-xs font-medium text-slate-700 hover:bg-slate-50 dark:border-slate-600 dark:text-slate-300 dark:hover:bg-slate-600"
                >
                  <div className={cn(
                    "flex h-3.5 w-3.5 shrink-0 items-center justify-center rounded-sm border",
                    allSelected ? "border-indigo-500 bg-indigo-500 text-white" : "border-slate-300 dark:border-slate-500",
                  )}>
                    {allSelected && <Check className="h-2.5 w-2.5" />}
                  </div>
                  <span className="h-2 w-2 rounded-full bg-indigo-500" />
                  All Fields
                  <span className="ml-auto text-[9px] text-slate-400">{selectedFields.size}/{columns.length}</span>
                </button>

                {/* Images group */}
                {imageColKeys.length > 0 && (
                  <>
                    <button
                      onClick={() => toggleGroup(imageColKeys)}
                      className="flex w-full items-center gap-2 px-3 py-1.5 text-left text-xs font-medium text-slate-600 hover:bg-slate-50 dark:text-slate-400 dark:hover:bg-slate-600"
                    >
                      <div className={cn(
                        "flex h-3.5 w-3.5 shrink-0 items-center justify-center rounded-sm border",
                        groupAllSelected(imageColKeys) ? "border-emerald-500 bg-emerald-500 text-white" : groupNoneSelected(imageColKeys) ? "border-slate-300 dark:border-slate-500" : "border-emerald-500 bg-emerald-200 dark:bg-emerald-800",
                      )}>
                        {groupAllSelected(imageColKeys) && <Check className="h-2.5 w-2.5" />}
                      </div>
                      <span className="h-2 w-2 rounded-full bg-emerald-500" />
                      Images
                    </button>
                    {imageColKeys.map((key) => (
                      <button key={key} onClick={() => toggleField(key)} className="flex w-full items-center gap-2 pl-7 pr-3 py-1 text-left text-xs text-slate-700 hover:bg-slate-50 dark:text-slate-300 dark:hover:bg-slate-600">
                        <div className={cn("flex h-3.5 w-3.5 shrink-0 items-center justify-center rounded-sm border", selectedFields.has(key) ? "border-indigo-500 bg-indigo-500 text-white" : "border-slate-300 dark:border-slate-500")}>
                          {selectedFields.has(key) && <Check className="h-2.5 w-2.5" />}
                        </div>
                        <span className="truncate">{key}</span>
                      </button>
                    ))}
                  </>
                )}

                {/* Price group */}
                {priceColKeys.length > 0 && (
                  <>
                    <button
                      onClick={() => toggleGroup(priceColKeys)}
                      className="flex w-full items-center gap-2 px-3 py-1.5 text-left text-xs font-medium text-slate-600 hover:bg-slate-50 dark:text-slate-400 dark:hover:bg-slate-600"
                    >
                      <div className={cn(
                        "flex h-3.5 w-3.5 shrink-0 items-center justify-center rounded-sm border",
                        groupAllSelected(priceColKeys) ? "border-amber-500 bg-amber-500 text-white" : groupNoneSelected(priceColKeys) ? "border-slate-300 dark:border-slate-500" : "border-amber-500 bg-amber-200 dark:bg-amber-800",
                      )}>
                        {groupAllSelected(priceColKeys) && <Check className="h-2.5 w-2.5" />}
                      </div>
                      <span className="h-2 w-2 rounded-full bg-amber-500" />
                      Price
                    </button>
                    {priceColKeys.map((key) => (
                      <button key={key} onClick={() => toggleField(key)} className="flex w-full items-center gap-2 pl-7 pr-3 py-1 text-left text-xs text-slate-700 hover:bg-slate-50 dark:text-slate-300 dark:hover:bg-slate-600">
                        <div className={cn("flex h-3.5 w-3.5 shrink-0 items-center justify-center rounded-sm border", selectedFields.has(key) ? "border-indigo-500 bg-indigo-500 text-white" : "border-slate-300 dark:border-slate-500")}>
                          {selectedFields.has(key) && <Check className="h-2.5 w-2.5" />}
                        </div>
                        <span className="truncate">{key}</span>
                      </button>
                    ))}
                  </>
                )}

                {/* Attributes / Other group */}
                {otherColKeys.length > 0 && (
                  <>
                    <button
                      onClick={() => toggleGroup(otherColKeys)}
                      className="flex w-full items-center gap-2 px-3 py-1.5 text-left text-xs font-medium text-slate-600 hover:bg-slate-50 dark:text-slate-400 dark:hover:bg-slate-600"
                    >
                      <div className={cn(
                        "flex h-3.5 w-3.5 shrink-0 items-center justify-center rounded-sm border",
                        groupAllSelected(otherColKeys) ? "border-violet-500 bg-violet-500 text-white" : groupNoneSelected(otherColKeys) ? "border-slate-300 dark:border-slate-500" : "border-violet-500 bg-violet-200 dark:bg-violet-800",
                      )}>
                        {groupAllSelected(otherColKeys) && <Check className="h-2.5 w-2.5" />}
                      </div>
                      <span className="h-2 w-2 rounded-full bg-violet-500" />
                      Attributes
                    </button>
                    {otherColKeys.map((key) => (
                      <button key={key} onClick={() => toggleField(key)} className="flex w-full items-center gap-2 pl-7 pr-3 py-1 text-left text-xs text-slate-700 hover:bg-slate-50 dark:text-slate-300 dark:hover:bg-slate-600">
                        <div className={cn("flex h-3.5 w-3.5 shrink-0 items-center justify-center rounded-sm border", selectedFields.has(key) ? "border-indigo-500 bg-indigo-500 text-white" : "border-slate-300 dark:border-slate-500")}>
                          {selectedFields.has(key) && <Check className="h-2.5 w-2.5" />}
                        </div>
                        <span className="truncate">{key}</span>
                      </button>
                    ))}
                  </>
                )}
              </div>
            </>
          )}
        </div>
      </div>

      {/* Image fields */}
      {imageColumns.length > 0 && (
        <div className="mb-3">
          <p className="mb-1.5 text-[10px] font-semibold uppercase tracking-wider text-slate-400">Images</p>
          {imageColumns.map((col) => {
            const val = String(product[col.key] ?? "");
            return (
              <div key={col.key} className="mb-2">
                <p className="text-[10px] font-medium text-teal-600 dark:text-teal-400">{col.key}</p>
                {val && val.startsWith("http") ? (
                  <div className="group relative mt-1">
                    <button
                      onClick={() => onFieldClick(col.key, val)}
                      draggable
                      onDragStart={(e) => { e.dataTransfer.setData("application/x-feed-field", JSON.stringify({ key: col.key, value: val })); e.dataTransfer.effectAllowed = "copy"; }}
                      className="w-full cursor-grab text-left active:cursor-grabbing"
                      title={`Click or drag to add {{${col.key}}} to canvas`}
                    >
                      <img src={val} alt={col.key} className="h-24 w-full rounded border object-contain bg-slate-50 dark:bg-slate-900" />
                    </button>
                    <div className="absolute bottom-1 right-1 flex gap-1 opacity-0 transition group-hover:opacity-100">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          onFieldClick(col.key + "__nobg", val);
                        }}
                        className="flex items-center gap-1 rounded bg-white/90 px-1.5 py-0.5 text-[9px] font-medium text-slate-600 shadow-sm backdrop-blur hover:bg-white dark:bg-slate-800/90 dark:text-slate-300 dark:hover:bg-slate-800"
                        title="Remove background and add to canvas"
                      >
                        <Eraser className="h-3 w-3" />
                        Remove BG
                      </button>
                    </div>
                  </div>
                ) : (
                  <button
                    onClick={() => onFieldClick(col.key, val)}
                    className="w-full text-left"
                    title={`Click to add {{${col.key}}} to canvas`}
                  >
                    <p className="truncate text-[10px] text-slate-500">{val || "—"}</p>
                  </button>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* Price fields */}
      {priceColumns.length > 0 && (
        <div className="mb-3">
          <p className="mb-1.5 text-[10px] font-semibold uppercase tracking-wider text-slate-400">Price</p>
          <div className="grid grid-cols-2 gap-1.5">
            {priceColumns.map((col) => (
              <button
                key={col.key}
                onClick={() => onFieldClick(col.key, String(product[col.key] ?? ""))}
                draggable
                onDragStart={(e) => { e.dataTransfer.setData("application/x-feed-field", JSON.stringify({ key: col.key, value: String(product[col.key] ?? "") })); e.dataTransfer.effectAllowed = "copy"; }}
                className="cursor-grab rounded border border-slate-200 p-2 text-left hover:border-indigo-300 hover:bg-indigo-50 active:cursor-grabbing dark:border-slate-600 dark:hover:border-indigo-600 dark:hover:bg-indigo-900/20"
                title={`Click or drag to add {{${col.key}}} to canvas`}
              >
                <p className="text-[10px] font-medium text-teal-600 dark:text-teal-400">{col.key}</p>
                <p className="text-xs font-medium text-slate-700 dark:text-slate-300">
                  {String(product[col.key] ?? "—")}
                </p>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Text fields */}
      {textColumns.length > 0 && (
        <div className="mb-3">
          <p className="mb-1.5 text-[10px] font-semibold uppercase tracking-wider text-slate-400">Attributes</p>
          <div className="grid grid-cols-2 gap-1.5">
            {textColumns.map((col) => (
              <button
                key={col.key}
                onClick={() => onFieldClick(col.key, String(product[col.key] ?? ""))}
                draggable
                onDragStart={(e) => { e.dataTransfer.setData("application/x-feed-field", JSON.stringify({ key: col.key, value: String(product[col.key] ?? "") })); e.dataTransfer.effectAllowed = "copy"; }}
                className="cursor-grab rounded border border-slate-200 p-2 text-left hover:border-indigo-300 hover:bg-indigo-50 active:cursor-grabbing dark:border-slate-600 dark:hover:border-indigo-600 dark:hover:bg-indigo-900/20"
                title={`Click or drag to add {{${col.key}}} to canvas`}
              >
                <p className="text-[10px] font-medium text-teal-600 dark:text-teal-400">{col.key}</p>
                <p className="line-clamp-2 text-[10px] text-slate-600 dark:text-slate-400">
                  {String(product[col.key] ?? "—")}
                </p>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Placeholder panels for Image Assets, Graphic Assets, Library
// ---------------------------------------------------------------------------

export function ImageAssetsPanel() {
  return (
    <div className="p-3">
      <p className="mb-3 text-xs text-slate-500 dark:text-slate-400">
        Upload images to use in your templates.
      </p>
      <button className="wm-btn-primary w-full rounded-md px-3 py-2 text-xs font-medium text-white">
        Upload Image
      </button>
      <p className="mt-4 text-center text-[10px] text-slate-400">No images uploaded yet.</p>
    </div>
  );
}

export function GraphicAssetsPanel() {
  const [searchGraphics, setSearchGraphics] = useState("");
  const [activeGraphicTab, setActiveGraphicTab] = useState<"all" | "tags">("all");
  const fileInputRef = useRef<HTMLInputElement>(null);

  return (
    <div className="flex h-full flex-col p-3">
      {/* All / Tags tabs */}
      <div className="mb-3 flex rounded-md border border-slate-200 dark:border-slate-600">
        <button
          onClick={() => setActiveGraphicTab("all")}
          className={cn(
            "flex-1 rounded-l-md px-3 py-1.5 text-xs font-medium transition",
            activeGraphicTab === "all"
              ? "bg-indigo-100 text-indigo-700 dark:bg-indigo-900/30 dark:text-indigo-400"
              : "text-slate-500 hover:bg-slate-50 dark:text-slate-400 dark:hover:bg-slate-700",
          )}
        >
          All
        </button>
        <button
          onClick={() => setActiveGraphicTab("tags")}
          className={cn(
            "flex-1 rounded-r-md px-3 py-1.5 text-xs font-medium transition",
            activeGraphicTab === "tags"
              ? "bg-indigo-100 text-indigo-700 dark:bg-indigo-900/30 dark:text-indigo-400"
              : "text-slate-500 hover:bg-slate-50 dark:text-slate-400 dark:hover:bg-slate-700",
          )}
        >
          Tags
        </button>
      </div>

      {/* Search */}
      <div className="relative mb-3">
        <Search className="absolute left-2 top-2 h-3.5 w-3.5 text-slate-400" />
        <input
          type="text"
          value={searchGraphics}
          onChange={(e) => setSearchGraphics(e.target.value)}
          placeholder="Search"
          className="mcc-input w-full rounded border py-1.5 pl-7 pr-2 text-xs"
        />
      </div>

      {/* Upload button */}
      <button
        onClick={() => fileInputRef.current?.click()}
        className="wm-btn-primary mb-4 flex w-full items-center justify-center gap-2 rounded-md px-3 py-2 text-xs font-medium text-white"
      >
        <Upload className="h-3.5 w-3.5" /> Upload Graphics
      </button>
      <input ref={fileInputRef} type="file" accept=".svg,.png,.jpg,.jpeg,.webp" multiple className="hidden" />

      {/* Empty state */}
      <div className="flex flex-1 flex-col items-center justify-center text-center">
        <div className="mb-3 text-slate-300 dark:text-slate-600">
          <Shapes className="mx-auto h-16 w-16" />
        </div>
        <p className="text-[11px] text-slate-400 dark:text-slate-500">
          Graphic assets are SVG files used for fleshing out your designs. Drag graphics from your library to the canvas to edit color and size.
        </p>
      </div>

      {/* Bottom: Browse ready-to-use Assets */}
      <div className="mt-4 border-t border-slate-200 pt-3 dark:border-slate-700">
        <div className="mb-2 flex items-center justify-between">
          <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
            Browse ready-to-use Assets
          </p>
          <button className="rounded p-0.5 text-slate-400 hover:text-slate-600 dark:hover:text-slate-300">
            <RefreshCw className="h-3 w-3" />
          </button>
        </div>
        <div className="grid grid-cols-3 gap-2">
          {[
            { label: "Highlight", emoji: "🔆" },
            { label: "Texture", emoji: "🌿" },
            { label: "Illustration", emoji: "🎨" },
          ].map((asset) => (
            <button
              key={asset.label}
              className="flex flex-col items-center gap-1 rounded-lg border border-slate-200 p-2 text-center hover:border-indigo-300 hover:bg-indigo-50 dark:border-slate-600 dark:hover:border-indigo-600 dark:hover:bg-indigo-900/20"
            >
              <span className="text-2xl">{asset.emoji}</span>
              <span className="text-[9px] text-slate-500 dark:text-slate-400">{asset.label}</span>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Library Panel — Elemente Publice
// Lists category folders that live under a top-level "Public Elements" folder
// in the agency media library. Clicking a category opens an extended panel
// with the files (images / SVGs) in that folder; clicking a file inserts it
// onto the canvas via `onInsertImage`.
// ---------------------------------------------------------------------------

const PUBLIC_ELEMENTS_ROOT_NAME = "Public Elements";

type LibraryPanelProps = {
  clientId: number | null;
  onInsertImage: (url: string, displayName: string) => void;
};

function LibraryFileTile({ clientId, file, onInsert }: {
  clientId: number;
  file: StorageMediaListItem;
  onInsert: (url: string, name: string) => void;
}) {
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let cancelled = false;
    let createdObjectUrl: string | null = null;
    (async () => {
      try {
        const blob = await fetchMediaBlob({ clientId, mediaId: file.media_id });
        if (cancelled) return;
        createdObjectUrl = URL.createObjectURL(blob);
        setPreviewUrl(createdObjectUrl);
      } catch {
        if (!cancelled) setFailed(true);
      }
    })();
    return () => {
      cancelled = true;
      if (createdObjectUrl) URL.revokeObjectURL(createdObjectUrl);
    };
  }, [clientId, file.media_id]);

  const label = file.display_name || file.original_filename;

  return (
    <button
      type="button"
      onClick={() => {
        if (previewUrl) onInsert(previewUrl, label);
      }}
      disabled={!previewUrl}
      className={cn(
        "group relative aspect-square overflow-hidden rounded-md border border-slate-200 bg-slate-50 p-1.5 text-left transition hover:border-indigo-300 hover:bg-indigo-50 dark:border-slate-700 dark:bg-slate-800 dark:hover:border-indigo-600 dark:hover:bg-indigo-950/30",
        !previewUrl && "cursor-not-allowed opacity-60",
      )}
      title={label}
    >
      {previewUrl && !failed ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={previewUrl}
          alt={label}
          className="h-full w-full object-contain"
          onError={() => setFailed(true)}
          draggable
          onDragStart={(event) => {
            event.dataTransfer.setData("application/x-media-image", JSON.stringify({ url: previewUrl, name: label }));
            event.dataTransfer.effectAllowed = "copy";
          }}
        />
      ) : (
        <div className="flex h-full w-full items-center justify-center text-slate-300">
          <Image className="h-6 w-6" />
        </div>
      )}
    </button>
  );
}

export function LibraryPanel({ clientId, onInsertImage }: LibraryPanelProps) {
  const [publicRootId, setPublicRootId] = useState<string | null>(null);
  const [categories, setCategories] = useState<StorageFolder[]>([]);
  const [loadingCategories, setLoadingCategories] = useState(false);
  const [categoriesError, setCategoriesError] = useState<string>("");

  const [activeCategory, setActiveCategory] = useState<StorageFolder | null>(null);
  const [categoryFiles, setCategoryFiles] = useState<StorageMediaListItem[]>([]);
  const [loadingFiles, setLoadingFiles] = useState(false);
  const [filesError, setFilesError] = useState<string>("");
  const [fileSearch, setFileSearch] = useState("");

  // Load root → find "Public Elements" → list its children
  useEffect(() => {
    if (!clientId) {
      setCategories([]);
      setPublicRootId(null);
      setCategoriesError("");
      return;
    }
    let cancelled = false;
    setLoadingCategories(true);
    setCategoriesError("");
    (async () => {
      try {
        const rootFolders = await listFolders({ clientId, parentFolderId: null });
        if (cancelled) return;
        const publicRoot = rootFolders.items.find(
          (folder) => folder.name.trim().toLowerCase() === PUBLIC_ELEMENTS_ROOT_NAME.toLowerCase(),
        );
        if (!publicRoot) {
          setPublicRootId(null);
          setCategories([]);
          setCategoriesError(
            `Niciun folder "${PUBLIC_ELEMENTS_ROOT_NAME}" nu a fost găsit în Stocare Media a agenției. Creează-l și populează-l cu sub-foldere (Emoticoane, Forme, Ilustrații, ...) pentru a-l vedea aici.`,
          );
          return;
        }
        setPublicRootId(publicRoot.folder_id);
        const childFolders = await listFolders({ clientId, parentFolderId: publicRoot.folder_id });
        if (cancelled) return;
        setCategories(childFolders.items);
      } catch (err) {
        if (cancelled) return;
        setCategories([]);
        setCategoriesError(err instanceof Error ? err.message : "Nu am putut încărca categoriile.");
      } finally {
        if (!cancelled) setLoadingCategories(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [clientId]);

  // Load files whenever the user opens a category
  useEffect(() => {
    if (!clientId || !activeCategory) {
      setCategoryFiles([]);
      setFilesError("");
      return;
    }
    let cancelled = false;
    setLoadingFiles(true);
    setFilesError("");
    setFileSearch("");
    (async () => {
      try {
        const response = await listMedia({
          clientId,
          folderId: activeCategory.folder_id,
          kind: "image",
          limit: 100,
          sort: "name_asc",
        });
        if (cancelled) return;
        setCategoryFiles(response.items);
      } catch (err) {
        if (cancelled) return;
        setCategoryFiles([]);
        setFilesError(err instanceof Error ? err.message : "Nu am putut încărca fișierele.");
      } finally {
        if (!cancelled) setLoadingFiles(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [clientId, activeCategory]);

  const filteredFiles = useMemo(() => {
    const token = fileSearch.trim().toLowerCase();
    if (token === "") return categoryFiles;
    return categoryFiles.filter((file) => {
      const label = (file.display_name || file.original_filename || "").toLowerCase();
      return label.includes(token);
    });
  }, [categoryFiles, fileSearch]);

  if (!clientId) {
    return (
      <div className="p-3 text-center text-xs text-slate-400">
        Nu am putut identifica contul de stocare al agenției. Încarcă un logo în Setări → Company pentru a inițializa spațiul de stocare.
      </div>
    );
  }

  // --- Extended panel: files inside a category ---
  if (activeCategory) {
    return (
      <div className="flex h-full flex-col">
        <div className="flex items-start justify-between gap-2 border-b border-slate-200 px-3 py-2.5 dark:border-slate-700">
          <div className="min-w-0 flex-1">
            <h4 className="truncate text-sm font-bold uppercase tracking-wide text-slate-900 dark:text-slate-100">
              {activeCategory.name}
            </h4>
            <p className="mt-0.5 text-[10px] text-slate-400">
              {categoryFiles.length} fișier{categoryFiles.length === 1 ? "" : "e"}
            </p>
          </div>
          <button
            type="button"
            onClick={() => setActiveCategory(null)}
            className="shrink-0 rounded p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-600 dark:hover:bg-slate-700"
            title="Înapoi la Elemente Publice"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="border-b border-slate-200 px-3 py-2 dark:border-slate-700">
          <div className="relative">
            <Search className="absolute left-2 top-2 h-3.5 w-3.5 text-slate-400" />
            <input
              type="search"
              value={fileSearch}
              onChange={(event) => setFileSearch(event.target.value)}
              placeholder="Caută în categorie..."
              className="mcc-input w-full rounded border py-1.5 pl-7 pr-2 text-xs"
            />
          </div>
        </div>

        <div className="flex-1 overflow-y-auto p-3">
          {loadingFiles ? (
            <div className="flex h-20 items-center justify-center text-xs text-slate-400">
              <Loader2 className="mr-2 h-4 w-4 animate-spin" /> Se încarcă...
            </div>
          ) : filesError ? (
            <p className="text-center text-xs text-red-500">{filesError}</p>
          ) : filteredFiles.length === 0 ? (
            <p className="text-center text-xs text-slate-400">Niciun fișier în această categorie.</p>
          ) : (
            <div className="grid grid-cols-2 gap-2">
              {filteredFiles.map((file) => (
                <LibraryFileTile
                  key={file.media_id}
                  clientId={clientId}
                  file={file}
                  onInsert={onInsertImage}
                />
              ))}
            </div>
          )}
        </div>
      </div>
    );
  }

  // --- Top-level: list categories ---
  return (
    <div className="p-2">
      {loadingCategories ? (
        <div className="flex h-20 items-center justify-center text-xs text-slate-400">
          <Loader2 className="mr-2 h-4 w-4 animate-spin" /> Se încarcă...
        </div>
      ) : categoriesError ? (
        <p className="p-2 text-center text-xs text-slate-400">{categoriesError}</p>
      ) : categories.length === 0 ? (
        <p className="p-2 text-center text-xs text-slate-400">
          Folderul "Public Elements" este gol. Adaugă sub-foldere din Stocare Media pentru a le vedea aici.
        </p>
      ) : (
        <div className="space-y-1">
          {categories.map((folder) => (
            <button
              key={folder.folder_id}
              type="button"
              onClick={() => setActiveCategory(folder)}
              className="flex w-full items-center gap-2 rounded border border-slate-200 px-2.5 py-2 text-left text-xs hover:border-indigo-300 hover:bg-indigo-50 dark:border-slate-600 dark:hover:border-indigo-600 dark:hover:bg-indigo-950/30"
              title={folder.name}
            >
              <Folder className="h-4 w-4 shrink-0 text-slate-400" />
              <span className="flex-1 truncate font-medium text-slate-700 dark:text-slate-200">{folder.name}</span>
              <ChevronRight className="h-3.5 w-3.5 shrink-0 text-slate-400" />
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
