"use client";

import { useEffect, useRef, useCallback, forwardRef, useImperativeHandle } from "react";
import { Canvas, Rect, Ellipse, Textbox, FabricImage, type FabricObject } from "fabric";
import { canvasElementsToFabricObjects, fabricToCanvasElements } from "@/lib/canvas-schema-bridge";
import type { CanvasElement } from "@/lib/hooks/useCreativeTemplates";

export interface CanvasEditorHandle {
  getElements: () => CanvasElement[];
  getCanvas: () => Canvas | null;
  addText: (text?: string) => void;
  addDynamicField: (binding: string) => void;
  addShape: (shapeType: "rectangle" | "ellipse") => void;
  addImagePlaceholder: (binding?: string) => void;
  deleteSelected: () => void;
  bringForward: () => void;
  sendBackward: () => void;
}

interface CanvasEditorProps {
  width: number;
  height: number;
  backgroundColor: string;
  elements: CanvasElement[];
  onSelectionChange?: (obj: FabricObject | null) => void;
  onModified?: () => void;
}

export const CanvasEditor = forwardRef<CanvasEditorHandle, CanvasEditorProps>(
  function CanvasEditor({ width, height, backgroundColor, elements, onSelectionChange, onModified }, ref) {
    const canvasElRef = useRef<HTMLCanvasElement>(null);
    const fabricRef = useRef<Canvas | null>(null);
    const initializedRef = useRef(false);

    // Initialize canvas
    useEffect(() => {
      if (!canvasElRef.current || initializedRef.current) return;
      initializedRef.current = true;

      const canvas = new Canvas(canvasElRef.current, {
        width,
        height,
        backgroundColor,
        selection: true,
      });

      canvas.on("selection:created", (e) => {
        onSelectionChange?.(e.selected?.[0] ?? null);
      });
      canvas.on("selection:updated", (e) => {
        onSelectionChange?.(e.selected?.[0] ?? null);
      });
      canvas.on("selection:cleared", () => {
        onSelectionChange?.(null);
      });
      canvas.on("object:modified", () => {
        onModified?.();
      });

      fabricRef.current = canvas;

      // Load initial elements
      if (elements.length > 0) {
        loadElements(canvas, elements);
      }

      return () => {
        canvas.dispose();
        fabricRef.current = null;
        initializedRef.current = false;
      };
      // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    // Update canvas size
    useEffect(() => {
      const canvas = fabricRef.current;
      if (!canvas) return;
      canvas.setDimensions({ width, height });
      canvas.backgroundColor = backgroundColor;
      canvas.renderAll();
    }, [width, height, backgroundColor]);

    const loadElements = useCallback(async (canvas: Canvas, els: CanvasElement[]) => {
      const fabricObjects = canvasElementsToFabricObjects(els);
      for (const objData of fabricObjects) {
        try {
          const obj = await createFabricObject(objData);
          if (obj) {
            canvas.add(obj);
          }
        } catch (err) {
          console.warn("Failed to load element:", err);
        }
      }
      canvas.renderAll();
    }, []);

    useImperativeHandle(ref, () => ({
      getElements: () => {
        const canvas = fabricRef.current;
        if (!canvas) return [];
        const json = (canvas as unknown as { toJSON: (props: string[]) => { version: string; objects: unknown[] } }).toJSON(["data"]);
        return fabricToCanvasElements(json as Parameters<typeof fabricToCanvasElements>[0]);
      },
      getCanvas: () => fabricRef.current,
      addText: (text = "Text") => {
        const canvas = fabricRef.current;
        if (!canvas) return;
        const textbox = new Textbox(text, {
          left: 50,
          top: 50,
          width: 200,
          fontSize: 24,
          fill: "#000000",
          fontFamily: "Arial",
          data: { elementType: "text" },
        });
        canvas.add(textbox);
        canvas.setActiveObject(textbox);
        canvas.renderAll();
        onModified?.();
      },
      addDynamicField: (binding: string) => {
        const canvas = fabricRef.current;
        if (!canvas) return;
        const textbox = new Textbox(binding, {
          left: 50,
          top: 50,
          width: 200,
          fontSize: 20,
          fill: "#6366f1",
          fontFamily: "Arial",
          data: { elementType: "dynamic_field", dynamicBinding: binding },
        });
        canvas.add(textbox);
        canvas.setActiveObject(textbox);
        canvas.renderAll();
        onModified?.();
      },
      addShape: (shapeType: "rectangle" | "ellipse") => {
        const canvas = fabricRef.current;
        if (!canvas) return;
        let obj: FabricObject;
        if (shapeType === "ellipse") {
          obj = new Ellipse({
            left: 50,
            top: 50,
            rx: 75,
            ry: 50,
            fill: "#e2e8f0",
            data: { elementType: "shape", shapeType: "ellipse" },
          });
        } else {
          obj = new Rect({
            left: 50,
            top: 50,
            width: 200,
            height: 100,
            fill: "#e2e8f0",
            data: { elementType: "shape", shapeType: "rectangle" },
          });
        }
        canvas.add(obj);
        canvas.setActiveObject(obj);
        canvas.renderAll();
        onModified?.();
      },
      addImagePlaceholder: (binding?: string) => {
        const canvas = fabricRef.current;
        if (!canvas) return;
        // Add a placeholder rectangle representing the image zone
        const placeholder = new Rect({
          left: 50,
          top: 50,
          width: 200,
          height: 200,
          fill: "#cbd5e1",
          stroke: "#94a3b8",
          strokeWidth: 2,
          strokeDashArray: [8, 4],
          data: {
            elementType: "image",
            dynamicBinding: binding || "{{image_link}}",
          },
        });
        canvas.add(placeholder);
        canvas.setActiveObject(placeholder);
        canvas.renderAll();
        onModified?.();
      },
      deleteSelected: () => {
        const canvas = fabricRef.current;
        if (!canvas) return;
        const active = canvas.getActiveObjects();
        active.forEach((obj) => canvas.remove(obj));
        canvas.discardActiveObject();
        canvas.renderAll();
        onModified?.();
      },
      bringForward: () => {
        const canvas = fabricRef.current;
        if (!canvas) return;
        const active = canvas.getActiveObject();
        if (active) {
          canvas.bringObjectForward(active);
          canvas.renderAll();
          onModified?.();
        }
      },
      sendBackward: () => {
        const canvas = fabricRef.current;
        if (!canvas) return;
        const active = canvas.getActiveObject();
        if (active) {
          canvas.sendObjectBackwards(active);
          canvas.renderAll();
          onModified?.();
        }
      },
    }));

    return (
      <div className="inline-block rounded border border-slate-300 shadow-sm dark:border-slate-600">
        <canvas ref={canvasElRef} />
      </div>
    );
  },
);

async function createFabricObject(data: Record<string, unknown>): Promise<FabricObject | null> {
  const type = data.type as string;
  switch (type) {
    case "textbox":
    case "i-text":
    case "text":
      return new Textbox(String(data.text || "Text"), {
        left: data.left as number,
        top: data.top as number,
        width: data.width as number,
        fontSize: (data.fontSize as number) || 16,
        fill: (data.fill as string) || "#000000",
        fontFamily: (data.fontFamily as string) || "Arial",
        data: data.data,
      });
    case "rect":
      return new Rect({
        left: data.left as number,
        top: data.top as number,
        width: data.width as number,
        height: data.height as number,
        fill: (data.fill as string) || "#CCCCCC",
        stroke: data.stroke as string | undefined,
        strokeWidth: data.strokeWidth as number | undefined,
        strokeDashArray: data.strokeDashArray as number[] | undefined,
        data: data.data,
      });
    case "ellipse":
    case "circle":
      return new Ellipse({
        left: data.left as number,
        top: data.top as number,
        rx: (data.rx as number) || 50,
        ry: (data.ry as number) || 50,
        fill: (data.fill as string) || "#CCCCCC",
        data: data.data,
      });
    case "image":
      try {
        const img = await FabricImage.fromURL(data.src as string);
        img.set({
          left: data.left as number,
          top: data.top as number,
          data: data.data,
        });
        if (data.width && data.height) {
          img.scaleToWidth(data.width as number);
          img.scaleToHeight(data.height as number);
        }
        return img;
      } catch {
        // Fallback: placeholder rect for failed image loads
        return new Rect({
          left: data.left as number,
          top: data.top as number,
          width: (data.width as number) || 200,
          height: (data.height as number) || 200,
          fill: "#cbd5e1",
          stroke: "#94a3b8",
          strokeWidth: 2,
          strokeDashArray: [8, 4],
          data: data.data,
        });
      }
    default:
      return null;
  }
}
