"use client";

import { useRef, useState, useEffect, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import { ArrowLeft, Save, Loader2, Eye, RefreshCw, Wand2, ZoomIn, ZoomOut, Maximize2 } from "lucide-react";
import dynamic from "next/dynamic";
import { useCreativeTemplate, useFormatSiblings, useCreativeTemplates } from "@/lib/hooks/useCreativeTemplates";
import { useCanvasEditor } from "@/lib/hooks/useCanvasEditor";
import { useBrandPresets } from "@/lib/hooks/useBrandPresets";
import { useFeedManagement } from "@/lib/contexts/FeedManagementContext";
import { useFeedSources } from "@/lib/hooks/useFeedSources";
import { useChannelProducts } from "@/lib/hooks/useChannelProducts";
import { useChannels } from "@/lib/hooks/useMasterFields";
import { apiRequest } from "@/lib/api";
import type { CanvasEditorHandle } from "@/components/enriched-catalog/CanvasEditor";
import type { UpdateTemplatePayload } from "@/lib/hooks/useCreativeTemplates";
import type { FabricObject } from "fabric";

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

  // Feed data for Source Feed panel
  const { sources } = useFeedSources(subaccountId);
  const firstSourceId = sources.length > 0 ? sources[0].id : null;
  const { channels } = useChannels(firstSourceId);
  const firstChannelId = (channels?.length ?? 0) > 0 ? channels![0].id : null;
  const { products, columns, total: totalProducts, isLoading: productsLoading } = useChannelProducts(firstChannelId, 1, 50);

  const hasFormatGroup = (siblings?.length ?? 0) > 1;
  const [saving, setSaving] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [styleSyncEnabled, setStyleSyncEnabled] = useState(true);
  const [adapting, setAdapting] = useState(false);
  const [showAdaptMenu, setShowAdaptMenu] = useState(false);
  const [canvasObjects, setCanvasObjects] = useState<FabricObject[]>([]);
  const [selectedObjectIndex, setSelectedObjectIndex] = useState<number | null>(null);

  // Sidebar state
  const [sidebarTab, setSidebarTab] = useState<SidebarTab>("source_feed");
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [currentProductIndex, setCurrentProductIndex] = useState(0);
  const [zoom, setZoom] = useState<number | null>(null);
  const canvasAreaRef = useRef<HTMLDivElement>(null);

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

  // Auto-fit canvas to available viewport on load and when dimensions change
  useEffect(() => {
    const container = canvasAreaRef.current;
    if (!container || !canvasWidth || !canvasHeight) return;
    const padding = 96; // 48px each side
    const availW = container.clientWidth - padding;
    const availH = container.clientHeight - padding;
    if (availW <= 0 || availH <= 0) return;
    const fitZoom = Math.min(availW / canvasWidth, availH / canvasHeight);
    const fitPercent = Math.max(10, Math.min(300, Math.round(fitZoom * 100)));
    setZoom(fitPercent);
  }, [canvasWidth, canvasHeight]);

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

  const handlePreview = async () => {
    const product = products[currentProductIndex] ?? {};
    try {
      await apiRequest(`/creative/templates/${templateId}/preview`, {
        method: "POST",
        body: JSON.stringify(product),
      });
      alert("Preview generated with current product data.");
    } catch (err) {
      console.error("Preview failed:", err);
    }
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
  const handleSourceFieldClick = (fieldKey: string, value: string) => {
    const binding = `{{${fieldKey}}}`;
    if (fieldKey.includes("image")) {
      canvasRef.current?.addImageFromURL(value, binding);
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
            products={products}
            columns={columns}
            isLoading={productsLoading}
            currentProductIndex={currentProductIndex}
            onProductChange={setCurrentProductIndex}
            totalProducts={totalProducts}
            onFieldClick={handleSourceFieldClick}
          />
        );
      case "image_assets":
        return <ImageAssetsPanel />;
      case "graphic_assets":
        return <GraphicAssetsPanel />;
      case "library":
        return (
          <LibraryPanel
            templates={allTemplates.map((t) => ({ id: t.id, name: t.name, canvas_width: t.canvas_width, canvas_height: t.canvas_height }))}
            onSelect={(id) => router.push(`/agency/enriched-catalog/templates/${id}/editor`)}
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

          <button onClick={handleSave} disabled={saving || !hasUnsavedChanges} className="wm-btn-primary flex items-center gap-1.5 rounded-md px-4 py-1.5 text-sm font-medium text-white disabled:opacity-50">
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
          <div ref={canvasAreaRef} className="relative flex flex-1 items-center justify-center overflow-auto bg-slate-300/70 dark:bg-slate-900" style={{ backgroundImage: "radial-gradient(circle, rgba(0,0,0,0.06) 1px, transparent 1px)", backgroundSize: "16px 16px" }}>
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
                  transform: `scale(${(zoom ?? 100) / 100})`,
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

                {/* Empty state hint */}
                {canvasObjects.length === 0 && (
                  <div className="pointer-events-none absolute inset-0 flex items-center justify-center">
                    <div className="rounded-lg bg-white/90 px-6 py-4 text-center shadow dark:bg-slate-800/90">
                      <p className="text-sm font-medium text-slate-600 dark:text-slate-300">Add Layers</p>
                      <p className="text-xs text-slate-400 dark:text-slate-500">
                        Drag elements from your library or click the toolbar to add them to the canvas
                      </p>
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Bottom status bar */}
          <div className="flex items-center justify-between border-t border-slate-200 bg-white px-4 py-1.5 dark:border-slate-700 dark:bg-slate-800">
            <div className="flex items-center gap-3 text-xs text-slate-500 dark:text-slate-400">
              <span>{totalProducts} SKUs</span>
              <span>{canvasObjects.length} layer{canvasObjects.length !== 1 ? "s" : ""}</span>
            </div>
            <div className="flex items-center gap-1">
              <button
                onClick={() => setZoom((prev) => Math.max(10, Math.round((prev ?? 100) / 1.2)))}
                className="rounded p-1 text-slate-400 hover:text-slate-600 dark:hover:text-slate-300"
                title="Zoom Out"
              >
                <ZoomOut className="h-3.5 w-3.5" />
              </button>
              <span className="w-10 text-center text-xs text-slate-500 dark:text-slate-400">{zoom ?? 100}%</span>
              <button
                onClick={() => setZoom((prev) => Math.min(300, Math.round((prev ?? 100) * 1.2)))}
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
    </div>
  );
}
