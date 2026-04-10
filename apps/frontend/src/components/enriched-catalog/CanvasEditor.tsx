"use client";

import { useEffect, useRef, useCallback, forwardRef, useMemo } from "react";
import { Canvas, Rect, Ellipse, Textbox, FabricImage, Line, Point, FabricObject } from "fabric";
import { canvasElementsToFabricObjects, fabricToCanvasElements } from "@/lib/canvas-schema-bridge";
import type { CanvasElement } from "@/lib/hooks/useCreativeTemplates";

export interface CanvasEditorHandle {
  getElements: () => CanvasElement[];
  getCanvas: () => Canvas | null;
  addText: (text?: string) => void;
  addDynamicField: (binding: string) => void;
  addShape: (shapeType: "rectangle" | "ellipse") => void;
  addImagePlaceholder: (binding?: string) => void;
  addImageFromURL: (url: string, binding: string) => void;
  deleteSelected: () => void;
  bringForward: () => void;
  sendBackward: () => void;
  undo: () => void;
  redo: () => void;
  zoomIn: () => void;
  zoomOut: () => void;
  zoomReset: () => void;
  getZoom: () => number;
}

interface CanvasEditorProps {
  width: number;
  height: number;
  backgroundColor: string;
  elements: CanvasElement[];
  editorRef?: React.MutableRefObject<CanvasEditorHandle | null>;
  onSelectionChange?: (obj: FabricObject | null) => void;
  onModified?: () => void;
}

export const CanvasEditor = forwardRef<CanvasEditorHandle, CanvasEditorProps>(
  function CanvasEditor({ width, height, backgroundColor, elements, editorRef, onSelectionChange, onModified }, ref) {
    const canvasElRef = useRef<HTMLCanvasElement>(null);
    const fabricRef = useRef<Canvas | null>(null);
    const initializedRef = useRef(false);
    const undoStackRef = useRef<string[]>([]);
    const redoStackRef = useRef<string[]>([]);
    const isUndoRedoRef = useRef(false);

    const saveUndoState = useCallback(() => {
      const canvas = fabricRef.current;
      if (!canvas || isUndoRedoRef.current) return;
      const json = JSON.stringify((canvas as unknown as { toJSON: (p: string[]) => unknown }).toJSON(["data"]));
      undoStackRef.current.push(json);
      if (undoStackRef.current.length > 50) undoStackRef.current.shift();
      redoStackRef.current = [];
    }, []);

    // Initialize canvas
    useEffect(() => {
      if (!canvasElRef.current || initializedRef.current) return;
      initializedRef.current = true;

      const canvas = new Canvas(canvasElRef.current, {
        width,
        height,
        backgroundColor,
        selection: true,
        selectionBorderColor: "#6366f1",
        selectionLineWidth: 2,
        selectionColor: "rgba(99, 102, 241, 0.1)",
      });

      // Make selection controls more visible for all objects
      FabricObject.prototype.set({
        borderColor: "#6366f1",
        cornerColor: "#6366f1",
        cornerStrokeColor: "#ffffff",
        cornerSize: 10,
        cornerStyle: "circle",
        borderScaleFactor: 2,
        transparentCorners: false,
        padding: 4,
      } as Partial<FabricObject>);

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
        saveUndoState();
        onModified?.();
      });

      // Snapping guide lines
      const SNAP_THRESHOLD = 5;
      const guideLines: Line[] = [];

      const clearGuides = () => {
        guideLines.forEach((line) => canvas.remove(line));
        guideLines.length = 0;
      };

      const addGuideLine = (x1: number, y1: number, x2: number, y2: number) => {
        const line = new Line([x1, y1, x2, y2], {
          stroke: "#ef4444",
          strokeWidth: 2,
          selectable: false,
          evented: false,
          excludeFromExport: true,
          data: { isGuideLine: true },
        });
        canvas.add(line);
        guideLines.push(line);
      };

      canvas.on("object:moving", (e) => {
        const obj = e.target;
        if (!obj) return;
        clearGuides();

        const bound = obj.getBoundingRect();
        const objCenterX = bound.left + bound.width / 2;
        const objCenterY = bound.top + bound.height / 2;
        const canvasCenterX = width / 2;
        const canvasCenterY = height / 2;

        // Snap to canvas center X
        if (Math.abs(objCenterX - canvasCenterX) < SNAP_THRESHOLD) {
          obj.set("left", (obj.left ?? 0) + (canvasCenterX - objCenterX));
          addGuideLine(canvasCenterX, 0, canvasCenterX, height);
        }
        // Snap to canvas center Y
        if (Math.abs(objCenterY - canvasCenterY) < SNAP_THRESHOLD) {
          obj.set("top", (obj.top ?? 0) + (canvasCenterY - objCenterY));
          addGuideLine(0, canvasCenterY, width, canvasCenterY);
        }
        // Snap to left/right edges
        if (Math.abs(bound.left) < SNAP_THRESHOLD) {
          obj.set("left", (obj.left ?? 0) - bound.left);
          addGuideLine(0, 0, 0, height);
        } else if (Math.abs(bound.left + bound.width - width) < SNAP_THRESHOLD) {
          obj.set("left", (obj.left ?? 0) + (width - bound.left - bound.width));
          addGuideLine(width, 0, width, height);
        }
        // Snap to top/bottom edges
        if (Math.abs(bound.top) < SNAP_THRESHOLD) {
          obj.set("top", (obj.top ?? 0) - bound.top);
          addGuideLine(0, 0, width, 0);
        } else if (Math.abs(bound.top + bound.height - height) < SNAP_THRESHOLD) {
          obj.set("top", (obj.top ?? 0) + (height - bound.top - bound.height));
          addGuideLine(0, height, width, height);
        }

        obj.setCoords();
        canvas.renderAll();
      });

      canvas.on("object:modified", () => clearGuides());
      canvas.on("mouse:up", () => { clearGuides(); canvas.renderAll(); });

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

    // Build imperative handle and assign to both ref and editorRef prop
    // NOTE: We use useMemo instead of useImperativeHandle because next/dynamic
    // does not forward refs, so ref is always null and useImperativeHandle
    // never executes its factory. We assign directly to editorRef instead.
    const handle = useMemo<CanvasEditorHandle>(() => ({
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
          data: { elementId: crypto.randomUUID(), elementType: "text" },
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
          data: { elementId: crypto.randomUUID(), elementType: "dynamic_field", dynamicBinding: binding },
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
            data: { elementId: crypto.randomUUID(), elementType: "shape", shapeType: "ellipse" },
          });
        } else {
          obj = new Rect({
            left: 50,
            top: 50,
            width: 200,
            height: 100,
            fill: "#e2e8f0",
            data: { elementId: crypto.randomUUID(), elementType: "shape", shapeType: "rectangle" },
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
            elementId: crypto.randomUUID(),
            elementType: "image",
            dynamicBinding: binding || "{{image_link}}",
          },
        });
        canvas.add(placeholder);
        canvas.setActiveObject(placeholder);
        canvas.renderAll();
        onModified?.();
      },
      addImageFromURL: (url: string, binding: string) => {
        const canvas = fabricRef.current;
        if (!canvas) return;
        if (!url || !url.startsWith("http")) {
          // Fallback to placeholder if no valid URL
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
              elementId: crypto.randomUUID(),
              elementType: "image",
              dynamicBinding: binding,
            },
          });
          canvas.add(placeholder);
          canvas.setActiveObject(placeholder);
          canvas.renderAll();
          onModified?.();
          return;
        }
        FabricImage.fromURL(url, { crossOrigin: "anonymous" }).then((fabricImg) => {
          const maxDim = 300;
          let w = fabricImg.width ?? 200;
          let h = fabricImg.height ?? 200;
          if (w > maxDim || h > maxDim) {
            const ratio = Math.min(maxDim / w, maxDim / h);
            w = Math.round(w * ratio);
            h = Math.round(h * ratio);
          }
          fabricImg.set({
            left: 50,
            top: 50,
            data: {
              elementId: crypto.randomUUID(),
              elementType: "image",
              dynamicBinding: binding,
              imageSrc: url,
            },
          });
          fabricImg.scaleToWidth(w);
          canvas.add(fabricImg);
          canvas.setActiveObject(fabricImg);
          canvas.renderAll();
          onModified?.();
        }).catch(() => {
          // Try again without CORS (allows display but not pixel access)
          const imgEl = document.createElement("img");
          imgEl.onload = () => {
            const fabricImg = new FabricImage(imgEl, {
              left: 50,
              top: 50,
              data: {
                elementId: crypto.randomUUID(),
                elementType: "image",
                dynamicBinding: binding,
                imageSrc: url,
              },
            });
            fabricImg.scaleToWidth(Math.min(300, imgEl.naturalWidth));
            canvas.add(fabricImg);
            canvas.setActiveObject(fabricImg);
            canvas.renderAll();
            onModified?.();
          };
          imgEl.onerror = () => {
            // Final fallback: placeholder
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
                elementId: crypto.randomUUID(),
                elementType: "image",
                dynamicBinding: binding,
              },
            });
            canvas.add(placeholder);
            canvas.setActiveObject(placeholder);
            canvas.renderAll();
            onModified?.();
          };
          imgEl.src = url;
        });
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
      undo: () => {
        const canvas = fabricRef.current;
        if (!canvas || undoStackRef.current.length === 0) return;
        const currentState = JSON.stringify((canvas as unknown as { toJSON: (p: string[]) => unknown }).toJSON(["data"]));
        redoStackRef.current.push(currentState);
        const prevState = undoStackRef.current.pop()!;
        isUndoRedoRef.current = true;
        canvas.loadFromJSON(JSON.parse(prevState)).then(() => {
          canvas.renderAll();
          isUndoRedoRef.current = false;
          onModified?.();
        });
      },
      redo: () => {
        const canvas = fabricRef.current;
        if (!canvas || redoStackRef.current.length === 0) return;
        const currentState = JSON.stringify((canvas as unknown as { toJSON: (p: string[]) => unknown }).toJSON(["data"]));
        undoStackRef.current.push(currentState);
        const nextState = redoStackRef.current.pop()!;
        isUndoRedoRef.current = true;
        canvas.loadFromJSON(JSON.parse(nextState)).then(() => {
          canvas.renderAll();
          isUndoRedoRef.current = false;
          onModified?.();
        });
      },
      zoomIn: () => {
        const canvas = fabricRef.current;
        if (!canvas) return;
        const newZoom = Math.min(3, canvas.getZoom() * 1.2);
        canvas.zoomToPoint(new Point(canvas.getWidth() / 2, canvas.getHeight() / 2), newZoom);
        canvas.renderAll();
      },
      zoomOut: () => {
        const canvas = fabricRef.current;
        if (!canvas) return;
        const newZoom = Math.max(0.1, canvas.getZoom() / 1.2);
        canvas.zoomToPoint(new Point(canvas.getWidth() / 2, canvas.getHeight() / 2), newZoom);
        canvas.renderAll();
      },
      zoomReset: () => {
        const canvas = fabricRef.current;
        if (!canvas) return;
        canvas.setViewportTransform([1, 0, 0, 1, 0, 0]);
        canvas.renderAll();
      },
      getZoom: () => fabricRef.current?.getZoom() ?? 1,
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }), []);

    // Assign handle synchronously to editorRef (bypasses next/dynamic ref issue)
    if (editorRef) editorRef.current = handle;
    if (typeof ref === "function") ref(handle);
    else if (ref) (ref as React.MutableRefObject<CanvasEditorHandle | null>).current = handle;

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
