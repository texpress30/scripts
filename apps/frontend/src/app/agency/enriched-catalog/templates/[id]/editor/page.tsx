"use client";

import { useRef, useState, useEffect, useCallback, useMemo } from "react";
import { useParams, useRouter } from "next/navigation";
import { ArrowLeft, Save, Loader2, Eye, RefreshCw, Wand2, ZoomIn, ZoomOut, Maximize2, Filter } from "lucide-react";
import dynamic from "next/dynamic";
import { useCreativeTemplate, useFormatSiblings, useCreativeTemplates } from "@/lib/hooks/useCreativeTemplates";
import { useCanvasEditor } from "@/lib/hooks/useCanvasEditor";
import { useBrandPresets } from "@/lib/hooks/useBrandPresets";
import { useFeedManagement } from "@/lib/contexts/FeedManagementContext";
import { useFeedSources } from "@/lib/hooks/useFeedSources";
import { useChannelProducts } from "@/lib/hooks/useChannelProducts";
import { useChannels } from "@/lib/hooks/useMasterFields";
import { usePrimeCutouts, useShufflePool } from "@/lib/hooks/useShufflePool";
import { apiRequest } from "@/lib/api";
import type { CanvasEditorHandle } from "@/components/enriched-catalog/CanvasEditor";
import type { UpdateTemplatePayload } from "@/lib/hooks/useCreativeTemplates";
import type { FabricObject } from "fabric";
import {
  EnrichedFeedFiltersModal,
  applyFeedFilters,
  countCompleteFilters,
  type FeedFilter,
} from "@/components/enriched-catalog/EnrichedFeedFiltersModal";

const CanvasEditor = dynamic(
  () => import("@/components/enriched-catalog/CanvasEditor").then((m) => ({ default: m.CanvasEditor })),
  { ssr: false, loading: () => <div className="flex h-96 items-center justify-center"><Loader2 className="h-6 w-6 animate-spin text-slate-400" /></div> },
);

import { CanvasToolbar } from "@/components/enriched-catalog/CanvasToolbar";
import { PropertyPanel } from "@/components/enriched-catalog/PropertyPanel";
import { BrandPicker } from "@/components/enriched-catalog/BrandPicker";
import {
  EditorSidebar,
  SourceFeedPanel,
  ImageAssetsPanel,
  GraphicAssetsPanel,
  LibraryPanel,
  type SidebarTab,
} from "@/components/enriched-catalog/EditorSidebar";
import { LayerPanel } from "@/components/enriched-catalog/LayerPanel";

function formatDimLabel(w: number, h: number, label?: string | null): string {
  if (label) return label;
  if (w === 1080 && h === 1080) return "Square";
  if (w === 1200 && h === 628) return "Landscape";
  if (w === 1080 && h === 1920) return "Stories";
  return `${w}x${h}`;
}

export default function TemplateEditorPage() {
  const params = useParams();
  const router = useRouter();
  const templateId = params.id as string;
  const canvasRef = useRef<CanvasEditorHandle>(null);

  const { selectedId: subaccountId } = useFeedManagement();
  const { data: template, isLoading: templateLoading } = useCreativeTemplate(templateId);
  const { data: siblings } = useFormatSiblings(templateId);
  const { presets: brandPresets } = useBrandPresets(subaccountId);
  const { templates: allTemplates } = useCreativeTemplates(subaccountId);

  // Agency media storage client id — used by the Elemente Publice (LibraryPanel)
  // tab to look up the shared Public Elements folder and list its categories.
  const [agencyStorageClientId, setAgencyStorageClientId] = useState<number | null>(null);
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const payload = await apiRequest<{ logo_storage_client_id?: number | null }>(
          "/company/settings",
          { requireAuth: true },
        );
        if (cancelled) return;
        const id = Number(payload.logo_storage_client_id);
        if (Number.isFinite(id) && id > 0) setAgencyStorageClientId(id);
        else setAgencyStorageClientId(null);
      } catch {
        if (!cancelled) setAgencyStorageClientId(null);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  // Feed data for Source Feed panel
  const { sources } = useFeedSources(subaccountId);
  const firstSourceId = sources.length > 0 ? sources[0].id : null;
  const { channels } = useChannels(firstSourceId);
  const firstChannelId = (channels?.length ?? 0) > 0 ? channels![0].id : null;
  const { products, columns, total: totalProducts, isLoading: productsLoading } = useChannelProducts(firstChannelId, 1, 50);

  // Shuffle pool: products that already have a background-removed cutout and
  // that match this template's treatment filters. The pool is refreshed every
  // 5s while the background-removal worker is still priming cutouts, so the
  // ready-count chip in the top bar grows live.
  const shufflePool = useShufflePool(templateId, { limit: 50, feedSourceId: firstSourceId });
  const primeMutation = usePrimeCutouts();

  // Kick off priming the first time the editor opens a template. The backend
  // is idempotent (image_cutouts is unique on (client_id, source_hash)) so
  // double-opens don't re-run the ML step.
  const primedTemplateRef = useRef<string | null>(null);
  useEffect(() => {
    if (!templateId || primedTemplateRef.current === templateId) return;
    primedTemplateRef.current = templateId;
    primeMutation.mutate({ templateId, limit: 200, feedSourceId: firstSourceId ?? undefined });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [templateId]);

  const hasFormatGroup = (siblings?.length ?? 0) > 1;
  const [saving, setSaving] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [saveToast, setSaveToast] = useState<string | null>(null);
  const [styleSyncEnabled, setStyleSyncEnabled] = useState(true);
  const [adapting, setAdapting] = useState(false);
  const [showAdaptMenu, setShowAdaptMenu] = useState(false);
  const [canvasObjects, setCanvasObjects] = useState<FabricObject[]>([]);
  const [selectedObjectIndex, setSelectedObjectIndex] = useState<number | null>(null);

  // Sidebar state
  const [sidebarTab, setSidebarTab] = useState<SidebarTab>("source_feed");
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [currentProductIndex, setCurrentProductIndex] = useState(0);
  const [zoom, setZoom] = useState<number>(34);
  const canvasAreaRef = useRef<HTMLDivElement>(null);

  // Enriched Feed Filters — modal opens from the SKU chip in the top bar and
  // narrows the set of rows the shuffle / source-feed panel iterates over.
  // Filters are persisted per-template in localStorage so they survive a
  // page refresh; the user explicitly clears them via the modal's Clear All
  // / trash controls.
  const filtersStorageKey = templateId ? `enriched-feed-filters:${templateId}` : "";
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [feedFilters, setFeedFilters] = useState<FeedFilter[]>(() => {
    if (typeof window === "undefined" || !filtersStorageKey) return [];
    try {
      const raw = window.localStorage.getItem(filtersStorageKey);
      if (!raw) return [];
      const parsed = JSON.parse(raw);
      if (!Array.isArray(parsed)) return [];
      // Defensive validation: only accept items that look like a FeedFilter
      // so an unrelated localStorage entry can't crash the editor.
      return parsed.filter(
        (f): f is FeedFilter =>
          f != null &&
          typeof f === "object" &&
          typeof (f as FeedFilter).id === "string" &&
          typeof (f as FeedFilter).column === "string" &&
          typeof (f as FeedFilter).operator === "string" &&
          typeof (f as FeedFilter).value === "string",
      );
    } catch {
      return [];
    }
  });
  useEffect(() => {
    if (typeof window === "undefined" || !filtersStorageKey) return;
    try {
      if (feedFilters.length === 0) {
        window.localStorage.removeItem(filtersStorageKey);
      } else {
        window.localStorage.setItem(filtersStorageKey, JSON.stringify(feedFilters));
      }
    } catch {
      // Ignore quota / private-mode errors — the filter still works in-memory.
    }
  }, [feedFilters, filtersStorageKey]);
  const filteredProducts = useMemo(
    () => applyFeedFilters(products, feedFilters),
    [products, feedFilters],
  );
  const filteredProductCount = filteredProducts.length;
  const activeFilterCount = countCompleteFilters(feedFilters);
  // Reset the pointer whenever the filtered result shrinks below the current
  // index so we don't render a stale / out-of-bounds row.
  useEffect(() => {
    if (currentProductIndex >= filteredProductCount && filteredProductCount > 0) {
      setCurrentProductIndex(0);
    }
  }, [currentProductIndex, filteredProductCount]);

  const {
    canvasWidth, canvasHeight, backgroundColor,
    selectedObject, hasUnsavedChanges,
    setSelectedObject, updateCanvasSize, updateBackgroundColor,
    markDirty, markClean,
  } = useCanvasEditor(
    template?.canvas_width || 1080,
    template?.canvas_height || 1080,
    template?.background_color || "#FFFFFF",
  );

  useEffect(() => {
    if (template) {
      updateCanvasSize(template.canvas_width, template.canvas_height);
      updateBackgroundColor(template.background_color);
      setStyleSyncEnabled(template.style_sync_enabled !== false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [template?.id]);

  const refreshObjectList = useCallback(() => {
    const canvas = canvasRef.current?.getCanvas();
    if (canvas) setCanvasObjects([...canvas.getObjects()]);
  }, []);

  const handleSelectionChange = useCallback((obj: FabricObject | null) => {
    setSelectedObject(obj);
    const canvas = canvasRef.current?.getCanvas();
    if (canvas && obj) {
      const idx = canvas.getObjects().indexOf(obj);
      setSelectedObjectIndex(idx >= 0 ? idx : null);
    } else {
      setSelectedObjectIndex(null);
    }
    refreshObjectList();
  }, [setSelectedObject, refreshObjectList]);

  const handleModified = useCallback(() => {
    markDirty();
    refreshObjectList();
  }, [markDirty, refreshObjectList]);

  const handleSave = async () => {
    if (!canvasRef.current) return;
    setSaving(true);
    try {
      const elements = canvasRef.current.getElements();
      const payload: UpdateTemplatePayload = {
        canvas_width: canvasWidth,
        canvas_height: canvasHeight,
        background_color: backgroundColor,
        elements,
      };
      await apiRequest(`/creative/templates/${templateId}`, {
        method: "PUT",
        body: JSON.stringify(payload),
      });
      markClean();
      setSaveToast("Template saved successfully");
      setTimeout(() => setSaveToast(null), 3000);

      if (styleSyncEnabled && hasFormatGroup) {
        setSyncing(true);
        try {
          await apiRequest(`/creative/templates/${templateId}/sync-styles`, { method: "POST" });
        } catch (syncErr) {
          console.warn("Style sync failed:", syncErr);
        } finally {
          setSyncing(false);
        }
      }
    } catch (err) {
      console.error("Failed to save template:", err);
      alert("Failed to save template. Please try again.");
    } finally {
      setSaving(false);
    }
  };

  const handlePreview = () => {
    if (hasUnsavedChanges && !confirm("You have unsaved changes. Go to preview without saving?")) return;
    router.push(`/agency/enriched-catalog/templates/${templateId}/preview`);
  };

  const handleSwitchFormat = (targetId: string) => {
    if (targetId === templateId) return;
    if (hasUnsavedChanges && !confirm("You have unsaved changes. Switch format without saving?")) return;
    router.push(`/agency/enriched-catalog/templates/${targetId}/editor`);
  };

  const handleAdaptLayout = async (sourceTemplateId: string) => {
    setAdapting(true);
    setShowAdaptMenu(false);
    try {
      await apiRequest(`/creative/templates/${templateId}/adapt-layout`, {
        method: "POST",
        body: JSON.stringify({ source_template_id: sourceTemplateId, target_width: canvasWidth, target_height: canvasHeight }),
      });
      window.location.reload();
    } catch (err) {
      console.error("Adapt layout failed:", err);
      alert("Failed to adapt layout.");
    } finally {
      setAdapting(false);
    }
  };

  const handleApplyBrandColor = (color: string) => {
    const canvas = canvasRef.current?.getCanvas();
    if (!canvas) return;
    const active = canvas.getActiveObject();
    if (active) { active.set("fill", color); canvas.renderAll(); markDirty(); }
  };

  const handleApplyBrandFont = (font: string) => {
    const canvas = canvasRef.current?.getCanvas();
    if (!canvas) return;
    const active = canvas.getActiveObject();
    if (active && "fontFamily" in active) {
      (active as unknown as { fontFamily: string }).fontFamily = font;
      canvas.renderAll();
      markDirty();
    }
  };

  // Source Feed: click a field to add as dynamic element
  const handleSourceFieldClick = async (fieldKey: string, value: string) => {
    // Handle remove background request
    const isRemoveBg = fieldKey.endsWith("__nobg");
    const actualKey = isRemoveBg ? fieldKey.replace("__nobg", "") : fieldKey;
    const binding = `{{${actualKey}}}`;

    if (actualKey.includes("image")) {
      if (isRemoveBg && value && value.startsWith("http")) {
        try {
          const res = await apiRequest("/creative/remove-background", {
            method: "POST",
            body: JSON.stringify({ image_url: value }),
          });
          const data = res as { url?: string };
          canvasRef.current?.addImageFromURL(data.url || value, binding);
        } catch (err) {
          console.warn("Remove background failed, using original image:", err);
          canvasRef.current?.addImageFromURL(value, binding);
        }
      } else {
        canvasRef.current?.addImageFromURL(value, binding);
      }
    } else {
      canvasRef.current?.addDynamicField(binding);
    }
  };

  const handleLayerSelect = (index: number) => {
    const canvas = canvasRef.current?.getCanvas();
    if (!canvas) return;
    const objects = canvas.getObjects();
    if (objects[index]) {
      canvas.setActiveObject(objects[index]);
      canvas.renderAll();
      setSelectedObject(objects[index]);
      setSelectedObjectIndex(index);
    }
  };

  const handleLayerToggleVisibility = (index: number) => {
    const canvas = canvasRef.current?.getCanvas();
    if (!canvas) return;
    const objects = canvas.getObjects();
    if (objects[index]) {
      objects[index].visible = !objects[index].visible;
      canvas.renderAll();
      refreshObjectList();
    }
  };

  const handleLayerDelete = (index: number) => {
    const canvas = canvasRef.current?.getCanvas();
    if (!canvas) return;
    const objects = canvas.getObjects();
    if (objects[index]) {
      canvas.remove(objects[index]);
      canvas.renderAll();
      markDirty();
      refreshObjectList();
    }
  };

  if (templateLoading) {
    return <div className="flex h-screen items-center justify-center"><Loader2 className="h-8 w-8 animate-spin text-slate-400" /></div>;
  }

  if (!template) {
    return <div className="flex h-screen items-center justify-center"><p className="text-slate-500">Template not found.</p></div>;
  }

  // Render sidebar panel content based on active tab
  const renderSidebarContent = () => {
    switch (sidebarTab) {
      case "source_feed":
        return (
          <SourceFeedPanel
            products={filteredProducts}
            columns={columns}
            isLoading={productsLoading}
            currentProductIndex={currentProductIndex}
            onProductChange={setCurrentProductIndex}
            totalProducts={filteredProductCount}
            onFieldClick={handleSourceFieldClick}
            hasActiveFilter={activeFilterCount > 0}
          />
        );
      case "image_assets":
        return <ImageAssetsPanel />;
      case "graphic_assets":
        return <GraphicAssetsPanel />;
      case "library":
        return (
          <LibraryPanel
            clientId={agencyStorageClientId}
            onInsertImage={(url, name) => canvasRef.current?.addImageFromURL(url, name)}
          />
        );
      case "layers":
        return (
          <LayerPanel
            objects={canvasObjects}
            selectedIndex={selectedObjectIndex}
            onSelect={handleLayerSelect}
            onToggleVisibility={handleLayerToggleVisibility}
            onDelete={handleLayerDelete}
          />
        );
    }
  };

  return (
    <div className="flex h-screen flex-col bg-slate-100 dark:bg-slate-900">
      {/* Top bar */}
      <div className="flex items-center justify-between border-b border-slate-200 bg-white px-4 py-2 dark:border-slate-700 dark:bg-slate-800">
        <div className="flex items-center gap-3">
          <button
            onClick={() => router.push("/agency/enriched-catalog/templates")}
            className="rounded p-1.5 text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-700"
          >
            <ArrowLeft className="h-4 w-4" />
          </button>
          <span className="text-sm font-medium text-slate-900 dark:text-slate-100">{template.name}</span>
          {hasUnsavedChanges && <span className="text-xs text-amber-500">Unsaved changes</span>}
        </div>

        <div className="flex items-center gap-2">
          {/* SKU chip — opens the Enriched Feed Filters modal. Shuffle still
              lives inside the Source Feed panel on the left sidebar. */}
          <button
            onClick={() => setFiltersOpen(true)}
            className={`flex items-center gap-1.5 rounded-md px-2 py-1.5 text-xs transition ${
              activeFilterCount > 0
                ? "border border-indigo-300 bg-indigo-50 text-indigo-700 dark:border-indigo-600 dark:bg-indigo-900/20 dark:text-indigo-300"
                : "text-slate-500 hover:bg-slate-100 dark:text-slate-400 dark:hover:bg-slate-700"
            }`}
            title="Open Enriched Feed Filters"
          >
            <Filter className="h-3.5 w-3.5" />
            {filteredProductCount} SKUs
            {activeFilterCount > 0 && (
              <span className="ml-1 rounded-full bg-indigo-200 px-1.5 text-[10px] font-medium text-indigo-800 dark:bg-indigo-800 dark:text-indigo-100">
                {activeFilterCount}
              </span>
            )}
          </button>

          {/* Cutout readiness chip — how many products in this template's feed
              already have a background-removed cutout ready for compositing.
              Polls every 5s while the priming worker is still processing so
              the count grows live. Hidden when the API isn't reachable or the
              template isn't bound to an output feed. */}
          {shufflePool.data && shufflePool.data.output_feed_id && (
            <div
              className="flex items-center gap-1.5 rounded-md border border-slate-200 px-2 py-1.5 text-xs text-slate-500 dark:border-slate-600 dark:text-slate-400"
              title="Products with a ready transparent-background cutout. The editor's Shuffle button can pick from these instantly."
            >
              {shufflePool.data.pool_ready_count < 50 && shufflePool.data.pool_ready_count < shufflePool.data.total_products ? (
                <Loader2 className="h-3 w-3 animate-spin text-indigo-500" />
              ) : (
                <Wand2 className="h-3 w-3 text-emerald-500" />
              )}
              <span>
                Cutouts {shufflePool.data.pool_ready_count}/{shufflePool.data.total_products}
              </span>
            </div>
          )}

          <div className="h-5 w-px bg-slate-200 dark:bg-slate-600" />

          <div className="flex items-center gap-1 text-xs text-slate-500 dark:text-slate-400">
            <input type="number" value={canvasWidth} onChange={(e) => updateCanvasSize(Number(e.target.value), canvasHeight)} className="mcc-input w-16 rounded border px-1.5 py-1 text-xs" />
            <span>x</span>
            <input type="number" value={canvasHeight} onChange={(e) => updateCanvasSize(canvasWidth, Number(e.target.value))} className="mcc-input w-16 rounded border px-1.5 py-1 text-xs" />
          </div>

          <input type="color" value={backgroundColor} onChange={(e) => updateBackgroundColor(e.target.value)} className="h-7 w-8 cursor-pointer rounded border" title="Background Color" />

          {hasFormatGroup && (
            <label className={`flex cursor-pointer items-center gap-1.5 rounded-md border px-3 py-1.5 text-xs transition ${styleSyncEnabled ? "border-indigo-300 bg-indigo-50 text-indigo-700 dark:border-indigo-600 dark:bg-indigo-900/20 dark:text-indigo-400" : "border-slate-200 text-slate-500 dark:border-slate-600 dark:text-slate-400"}`}>
              <input type="checkbox" checked={styleSyncEnabled} onChange={(e) => setStyleSyncEnabled(e.target.checked)} className="accent-indigo-600" />
              <RefreshCw className={`h-3 w-3 ${syncing ? "animate-spin" : ""}`} />
              Sync
            </label>
          )}

          <button onClick={handlePreview} className="flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm text-slate-600 hover:bg-slate-100 dark:text-slate-400 dark:hover:bg-slate-700">
            <Eye className="h-4 w-4" /> Preview
          </button>

          <button onClick={handleSave} disabled={saving} className="wm-btn-primary flex items-center gap-1.5 rounded-md px-4 py-1.5 text-sm font-medium text-white disabled:opacity-50">
            {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
            {saving && syncing ? "Syncing..." : "Save"}
          </button>
        </div>
      </div>

      {/* Toolbar */}
      <div className="flex items-center justify-center gap-2 border-b border-slate-200 bg-slate-50 px-4 py-2 dark:border-slate-700 dark:bg-slate-850">
        <CanvasToolbar
          onAddText={() => canvasRef.current?.addText()}
          onAddDynamicField={(binding) => canvasRef.current?.addDynamicField(binding)}
          onAddShape={(type) => canvasRef.current?.addShape(type)}
          onAddImage={(binding) => canvasRef.current?.addImagePlaceholder(binding)}
          onDelete={() => canvasRef.current?.deleteSelected()}
          onBringForward={() => canvasRef.current?.bringForward()}
          onSendBackward={() => canvasRef.current?.sendBackward()}
          onUndo={() => canvasRef.current?.undo()}
          onRedo={() => canvasRef.current?.redo()}
          hasSelection={selectedObject !== null}
        />
        {brandPresets.length > 0 && (
          <>
            <div className="h-6 w-px bg-slate-200 dark:bg-slate-600" />
            <BrandPicker presets={brandPresets} onApplyColor={handleApplyBrandColor} onApplyFont={handleApplyBrandFont} onApplyBackground={updateBackgroundColor} />
          </>
        )}
      </div>

      {/* Main area: Sidebar + Canvas + Properties */}
      <div className="flex flex-1 overflow-hidden">
        {/* Left: Marpipe-style sidebar */}
        <EditorSidebar
          activeTab={sidebarTab}
          onTabChange={setSidebarTab}
          collapsed={sidebarCollapsed}
          onToggleCollapse={() => setSidebarCollapsed(!sidebarCollapsed)}
        >
          {renderSidebarContent()}
        </EditorSidebar>

        {/* Center: Canvas + Format switcher + Status bar */}
        <div className="flex flex-1 flex-col overflow-hidden">
          <div
            ref={canvasAreaRef}
            className="relative flex flex-1 items-center justify-center overflow-auto bg-slate-300/70 dark:bg-slate-900"
            style={{ backgroundImage: "radial-gradient(circle, rgba(0,0,0,0.06) 1px, transparent 1px)", backgroundSize: "16px 16px" }}
            onDragOver={(e) => {
              const types = e.dataTransfer.types;
              if (
                types.includes("application/x-feed-field") ||
                types.includes("application/x-media-image")
              ) {
                e.preventDefault();
                e.dataTransfer.dropEffect = "copy";
              }
            }}
            onDrop={(e) => {
              e.preventDefault();
              // Drop a feed field → add a dynamic binding placeholder
              const feedRaw = e.dataTransfer.getData("application/x-feed-field");
              if (feedRaw) {
                try {
                  const { key, value } = JSON.parse(feedRaw) as { key: string; value: string };
                  handleSourceFieldClick(key, value);
                } catch { /* ignore invalid data */ }
                return;
              }
              // Drop a Public Elements image → add it at the drop position
              const mediaRaw = e.dataTransfer.getData("application/x-media-image");
              if (mediaRaw) {
                try {
                  const { url, name } = JSON.parse(mediaRaw) as { url: string; name: string };
                  canvasRef.current?.addImageFromURL(url, name, {
                    clientX: e.clientX,
                    clientY: e.clientY,
                  });
                } catch { /* ignore invalid data */ }
              }
            }}
          >
            {/* Scaled canvas wrapper for CSS-based zoom */}
            <div
              className="flex items-center justify-center"
              style={{
                minWidth: "100%",
                minHeight: "100%",
                padding: "48px",
              }}
            >
              <div
                style={{
                  transform: `scale(${zoom / 100})`,
                  transformOrigin: "center center",
                  transition: "transform 0.15s ease-out",
                }}
              >
                <CanvasEditor
                  ref={canvasRef}
                  editorRef={canvasRef}
                  width={canvasWidth}
                  height={canvasHeight}
                  backgroundColor={backgroundColor}
                  elements={template.elements}
                  onSelectionChange={handleSelectionChange}
                  onModified={handleModified}
                />
              </div>
            </div>
          </div>

          {/* Bottom status bar */}
          <div className="flex items-center justify-between border-t border-slate-200 bg-white px-4 py-1.5 dark:border-slate-700 dark:bg-slate-800">
            <div className="flex items-center gap-3 text-xs text-slate-500 dark:text-slate-400">
              <span>{canvasObjects.length} layer{canvasObjects.length !== 1 ? "s" : ""}</span>
            </div>
            <div className="flex items-center gap-1">
              <button
                onClick={() => setZoom((prev) => Math.max(10, Math.round(prev / 1.2)))}
                className="rounded p-1 text-slate-400 hover:text-slate-600 dark:hover:text-slate-300"
                title="Zoom Out"
              >
                <ZoomOut className="h-3.5 w-3.5" />
              </button>
              <span className="w-10 text-center text-xs text-slate-500 dark:text-slate-400">{zoom ?? 100}%</span>
              <button
                onClick={() => setZoom((prev) => Math.min(300, Math.round(prev * 1.2)))}
                className="rounded p-1 text-slate-400 hover:text-slate-600 dark:hover:text-slate-300"
                title="Zoom In"
              >
                <ZoomIn className="h-3.5 w-3.5" />
              </button>
              <button
                onClick={() => setZoom(100)}
                className="rounded p-1 text-slate-400 hover:text-slate-600 dark:hover:text-slate-300"
                title="Reset Zoom"
              >
                <Maximize2 className="h-3.5 w-3.5" />
              </button>
            </div>
          </div>

          {/* Format switcher bar */}
          {hasFormatGroup && (
            <div className="flex items-center justify-center gap-2 border-t border-slate-200 bg-white px-4 py-2 dark:border-slate-700 dark:bg-slate-800">
              <span className="mr-2 text-xs font-medium text-slate-500 dark:text-slate-400">Formats:</span>
              {(siblings ?? []).map((sibling) => {
                const isActive = sibling.id === templateId;
                const label = formatDimLabel(sibling.canvas_width, sibling.canvas_height, sibling.format_label);
                return (
                  <button key={sibling.id} onClick={() => handleSwitchFormat(sibling.id)} className={`flex flex-col items-center rounded-lg border px-4 py-2 text-xs transition ${isActive ? "border-indigo-500 bg-indigo-50 text-indigo-700 dark:border-indigo-400 dark:bg-indigo-900/20 dark:text-indigo-400" : "border-slate-200 text-slate-600 hover:border-slate-300 hover:bg-slate-50 dark:border-slate-600 dark:text-slate-400 dark:hover:bg-slate-700"}`}>
                    <span className="font-medium">{label}</span>
                    <span className="text-[10px] text-slate-400">{sibling.canvas_width}x{sibling.canvas_height}</span>
                  </button>
                );
              })}

              <div className="relative ml-2">
                <button onClick={() => setShowAdaptMenu(!showAdaptMenu)} disabled={adapting} className="flex items-center gap-1.5 rounded-lg border border-amber-300 bg-amber-50 px-3 py-2 text-xs font-medium text-amber-700 hover:bg-amber-100 disabled:opacity-50 dark:border-amber-600 dark:bg-amber-900/20 dark:text-amber-400">
                  {adapting ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Wand2 className="h-3.5 w-3.5" />}
                  Adapt From...
                </button>
                {showAdaptMenu && (
                  <>
                    <div className="fixed inset-0 z-10" onClick={() => setShowAdaptMenu(false)} />
                    <div className="absolute bottom-full left-0 z-20 mb-1 w-48 rounded-md border border-slate-200 bg-white py-1 shadow-lg dark:border-slate-600 dark:bg-slate-700">
                      <p className="px-3 py-1 text-xs text-slate-400">Copy layout from:</p>
                      {(siblings ?? []).filter((s) => s.id !== templateId).map((sibling) => (
                        <button key={sibling.id} onClick={() => handleAdaptLayout(sibling.id)} className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-slate-700 hover:bg-slate-50 dark:text-slate-300 dark:hover:bg-slate-600">
                          <Wand2 className="h-3 w-3 text-amber-500" />
                          {formatDimLabel(sibling.canvas_width, sibling.canvas_height, sibling.format_label)}
                        </button>
                      ))}
                    </div>
                  </>
                )}
              </div>
            </div>
          )}
        </div>

        {/* Right: Properties */}
        <div className="w-64 overflow-y-auto border-l border-slate-200 bg-white p-3 dark:border-slate-700 dark:bg-slate-800">
          <PropertyPanel selectedObject={selectedObject} onUpdate={() => { markDirty(); refreshObjectList(); }} />
        </div>
      </div>

      {/* Save toast notification */}
      {saveToast && (
        <div className="fixed bottom-6 left-1/2 z-50 -translate-x-1/2 animate-in fade-in slide-in-from-bottom-4">
          <div className="flex items-center gap-2 rounded-lg bg-emerald-600 px-4 py-2.5 text-sm font-medium text-white shadow-lg">
            <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}><path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" /></svg>
            {saveToast}
          </div>
        </div>
      )}

      <EnrichedFeedFiltersModal
        open={filtersOpen}
        onClose={() => setFiltersOpen(false)}
        columns={columns}
        productRowsCount={filteredProductCount}
        initialFilters={feedFilters}
        onApply={(next) => {
          setFeedFilters(next);
          setCurrentProductIndex(0);
        }}
      />
    </div>
  );
}
