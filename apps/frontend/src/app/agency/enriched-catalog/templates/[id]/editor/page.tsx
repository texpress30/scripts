"use client";

import { useRef, useState, useEffect, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import { ArrowLeft, Save, Loader2, Eye } from "lucide-react";
import dynamic from "next/dynamic";
import { useCreativeTemplate } from "@/lib/hooks/useCreativeTemplates";
import { useCanvasEditor } from "@/lib/hooks/useCanvasEditor";
import { apiRequest } from "@/lib/api";
import type { CanvasEditorHandle } from "@/components/enriched-catalog/CanvasEditor";
import type { UpdateTemplatePayload } from "@/lib/hooks/useCreativeTemplates";
import type { FabricObject } from "fabric";

// Dynamic import to avoid SSR issues with fabric.js
const CanvasEditor = dynamic(
  () => import("@/components/enriched-catalog/CanvasEditor").then((m) => ({ default: m.CanvasEditor })),
  { ssr: false, loading: () => <div className="flex h-96 items-center justify-center"><Loader2 className="h-6 w-6 animate-spin text-slate-400" /></div> },
);

// These don't use fabric directly, safe to import normally
import { CanvasToolbar } from "@/components/enriched-catalog/CanvasToolbar";
import { LayerPanel } from "@/components/enriched-catalog/LayerPanel";
import { PropertyPanel } from "@/components/enriched-catalog/PropertyPanel";

export default function TemplateEditorPage() {
  const params = useParams();
  const router = useRouter();
  const templateId = params.id as string;
  const canvasRef = useRef<CanvasEditorHandle>(null);

  const { data: template, isLoading: templateLoading } = useCreativeTemplate(templateId);
  const [saving, setSaving] = useState(false);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [canvasObjects, setCanvasObjects] = useState<FabricObject[]>([]);
  const [selectedObjectIndex, setSelectedObjectIndex] = useState<number | null>(null);

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

  // Sync canvas size from loaded template
  useEffect(() => {
    if (template) {
      updateCanvasSize(template.canvas_width, template.canvas_height);
      updateBackgroundColor(template.background_color);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [template?.id]);

  const refreshObjectList = useCallback(() => {
    const canvas = canvasRef.current?.getCanvas();
    if (canvas) {
      setCanvasObjects([...canvas.getObjects()]);
    }
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
    } catch (err) {
      console.error("Failed to save template:", err);
      alert("Failed to save template. Please try again.");
    } finally {
      setSaving(false);
    }
  };

  const handlePreview = async () => {
    setPreviewLoading(true);
    try {
      const result = await apiRequest<{ template_id: string; rendered_elements: unknown[] }>(
        `/creative/templates/${templateId}/preview`,
        {
          method: "POST",
          body: JSON.stringify({
            title: "Sample Product",
            price: "$29.99",
            sale_price: "$19.99",
            brand: "Brand Name",
            description: "This is a sample product description",
            image_link: "https://via.placeholder.com/400",
            category: "Clothing",
            availability: "in stock",
          }),
        },
      );
      alert(`Preview generated! ${(result.rendered_elements || []).length} elements rendered.`);
    } catch (err) {
      console.error("Preview failed:", err);
    } finally {
      setPreviewLoading(false);
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
    return (
      <div className="flex h-screen items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-slate-400" />
      </div>
    );
  }

  if (!template) {
    return (
      <div className="flex h-screen items-center justify-center">
        <p className="text-slate-500">Template not found.</p>
      </div>
    );
  }

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
          {hasUnsavedChanges && (
            <span className="text-xs text-amber-500">Unsaved changes</span>
          )}
        </div>

        <div className="flex items-center gap-2">
          {/* Canvas size controls */}
          <div className="flex items-center gap-1 text-xs text-slate-500 dark:text-slate-400">
            <input
              type="number"
              value={canvasWidth}
              onChange={(e) => updateCanvasSize(Number(e.target.value), canvasHeight)}
              className="mcc-input w-16 rounded border px-1.5 py-1 text-xs"
            />
            <span>x</span>
            <input
              type="number"
              value={canvasHeight}
              onChange={(e) => updateCanvasSize(canvasWidth, Number(e.target.value))}
              className="mcc-input w-16 rounded border px-1.5 py-1 text-xs"
            />
          </div>

          {/* Background color */}
          <input
            type="color"
            value={backgroundColor}
            onChange={(e) => updateBackgroundColor(e.target.value)}
            className="h-7 w-8 cursor-pointer rounded border"
            title="Background Color"
          />

          {/* Preview */}
          <button
            onClick={handlePreview}
            disabled={previewLoading}
            className="flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm text-slate-600 hover:bg-slate-100 dark:text-slate-400 dark:hover:bg-slate-700"
          >
            {previewLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Eye className="h-4 w-4" />}
            Preview
          </button>

          {/* Save */}
          <button
            onClick={handleSave}
            disabled={saving || !hasUnsavedChanges}
            className="wm-btn-primary flex items-center gap-1.5 rounded-md px-4 py-1.5 text-sm font-medium text-white disabled:opacity-50"
          >
            {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
            Save
          </button>
        </div>
      </div>

      {/* Toolbar */}
      <div className="flex justify-center border-b border-slate-200 bg-slate-50 px-4 py-2 dark:border-slate-700 dark:bg-slate-850">
        <CanvasToolbar
          onAddText={() => canvasRef.current?.addText()}
          onAddDynamicField={(binding) => canvasRef.current?.addDynamicField(binding)}
          onAddShape={(type) => canvasRef.current?.addShape(type)}
          onAddImage={(binding) => canvasRef.current?.addImagePlaceholder(binding)}
          onDelete={() => canvasRef.current?.deleteSelected()}
          onBringForward={() => canvasRef.current?.bringForward()}
          onSendBackward={() => canvasRef.current?.sendBackward()}
          hasSelection={selectedObject !== null}
        />
      </div>

      {/* Main area */}
      <div className="flex flex-1 overflow-hidden">
        {/* Left panel: Layers */}
        <div className="w-60 overflow-y-auto border-r border-slate-200 bg-white p-3 dark:border-slate-700 dark:bg-slate-800">
          <LayerPanel
            objects={canvasObjects}
            selectedIndex={selectedObjectIndex}
            onSelect={handleLayerSelect}
            onToggleVisibility={handleLayerToggleVisibility}
            onDelete={handleLayerDelete}
          />
        </div>

        {/* Canvas area */}
        <div className="flex flex-1 items-center justify-center overflow-auto bg-slate-200 p-8 dark:bg-slate-900">
          <CanvasEditor
            ref={canvasRef}
            width={canvasWidth}
            height={canvasHeight}
            backgroundColor={backgroundColor}
            elements={template.elements}
            onSelectionChange={handleSelectionChange}
            onModified={handleModified}
          />
        </div>

        {/* Right panel: Properties */}
        <div className="w-68 overflow-y-auto border-l border-slate-200 bg-white p-3 dark:border-slate-700 dark:bg-slate-800">
          <PropertyPanel
            selectedObject={selectedObject}
            onUpdate={() => {
              markDirty();
              refreshObjectList();
            }}
          />
        </div>
      </div>
    </div>
  );
}
