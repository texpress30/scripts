"use client";

import type { FabricObject } from "fabric";

interface PropertyPanelProps {
  selectedObject: FabricObject | null;
  onUpdate: () => void;
}

export function PropertyPanel({ selectedObject, onUpdate }: PropertyPanelProps) {
  if (!selectedObject) {
    return (
      <div className="w-64 rounded-lg border border-slate-200 bg-white p-4 dark:border-slate-700 dark:bg-slate-800">
        <p className="text-center text-xs text-slate-400 dark:text-slate-500">
          Select an element to edit its properties
        </p>
      </div>
    );
  }

  const data = (selectedObject as unknown as { data?: { elementType?: string; dynamicBinding?: string; shapeType?: string } }).data;
  const elementType = data?.elementType || "unknown";

  const updateProp = (key: string, value: unknown) => {
    selectedObject.set(key as keyof FabricObject, value as never);
    selectedObject.setCoords();
    selectedObject.canvas?.renderAll();
    onUpdate();
  };

  return (
    <div className="w-64 rounded-lg border border-slate-200 bg-white dark:border-slate-700 dark:bg-slate-800">
      <div className="border-b border-slate-200 px-3 py-2 dark:border-slate-600">
        <p className="text-xs font-semibold text-slate-600 dark:text-slate-400">
          Properties — {elementType.replace("_", " ")}
        </p>
      </div>
      <div className="space-y-3 p-3">
        {/* Position */}
        <fieldset>
          <legend className="mb-1 text-xs font-medium text-slate-500 dark:text-slate-400">Position</legend>
          <div className="grid grid-cols-2 gap-2">
            <label className="text-xs text-slate-500 dark:text-slate-400">
              X
              <input
                type="number"
                value={Math.round(selectedObject.left || 0)}
                onChange={(e) => updateProp("left", Number(e.target.value))}
                className="mcc-input mt-0.5 w-full rounded border px-2 py-1 text-xs"
              />
            </label>
            <label className="text-xs text-slate-500 dark:text-slate-400">
              Y
              <input
                type="number"
                value={Math.round(selectedObject.top || 0)}
                onChange={(e) => updateProp("top", Number(e.target.value))}
                className="mcc-input mt-0.5 w-full rounded border px-2 py-1 text-xs"
              />
            </label>
          </div>
        </fieldset>

        {/* Size */}
        <fieldset>
          <legend className="mb-1 text-xs font-medium text-slate-500 dark:text-slate-400">Size</legend>
          <div className="grid grid-cols-2 gap-2">
            <label className="text-xs text-slate-500 dark:text-slate-400">
              W
              <input
                type="number"
                value={Math.round((selectedObject.width || 0) * (selectedObject.scaleX || 1))}
                onChange={(e) => {
                  const newW = Number(e.target.value);
                  updateProp("scaleX", newW / (selectedObject.width || 1));
                }}
                className="mcc-input mt-0.5 w-full rounded border px-2 py-1 text-xs"
              />
            </label>
            <label className="text-xs text-slate-500 dark:text-slate-400">
              H
              <input
                type="number"
                value={Math.round((selectedObject.height || 0) * (selectedObject.scaleY || 1))}
                onChange={(e) => {
                  const newH = Number(e.target.value);
                  updateProp("scaleY", newH / (selectedObject.height || 1));
                }}
                className="mcc-input mt-0.5 w-full rounded border px-2 py-1 text-xs"
              />
            </label>
          </div>
        </fieldset>

        {/* Color / Fill */}
        {(elementType === "text" || elementType === "dynamic_field") && (
          <fieldset>
            <legend className="mb-1 text-xs font-medium text-slate-500 dark:text-slate-400">Text</legend>
            <div className="space-y-2">
              <label className="flex items-center gap-2 text-xs text-slate-500 dark:text-slate-400">
                Color
                <input
                  type="color"
                  value={(selectedObject.fill as string) || "#000000"}
                  onChange={(e) => updateProp("fill", e.target.value)}
                  className="h-6 w-8 cursor-pointer rounded border"
                />
              </label>
              <label className="text-xs text-slate-500 dark:text-slate-400">
                Font Size
                <input
                  type="number"
                  value={(selectedObject as unknown as { fontSize?: number }).fontSize || 16}
                  onChange={(e) => updateProp("fontSize", Number(e.target.value))}
                  className="mcc-input mt-0.5 w-full rounded border px-2 py-1 text-xs"
                  min={8}
                  max={200}
                />
              </label>
            </div>
          </fieldset>
        )}

        {elementType === "shape" && (
          <fieldset>
            <legend className="mb-1 text-xs font-medium text-slate-500 dark:text-slate-400">Fill</legend>
            <label className="flex items-center gap-2 text-xs text-slate-500 dark:text-slate-400">
              Color
              <input
                type="color"
                value={(selectedObject.fill as string) || "#CCCCCC"}
                onChange={(e) => updateProp("fill", e.target.value)}
                className="h-6 w-8 cursor-pointer rounded border"
              />
            </label>
          </fieldset>
        )}

        {/* Dynamic binding info */}
        {elementType === "dynamic_field" && data?.dynamicBinding && (
          <fieldset>
            <legend className="mb-1 text-xs font-medium text-slate-500 dark:text-slate-400">Binding</legend>
            <code className="block rounded bg-indigo-50 px-2 py-1 text-xs text-indigo-600 dark:bg-indigo-900/20 dark:text-indigo-400">
              {data.dynamicBinding}
            </code>
          </fieldset>
        )}

        {elementType === "image" && data?.dynamicBinding && (
          <fieldset>
            <legend className="mb-1 text-xs font-medium text-slate-500 dark:text-slate-400">Image Source</legend>
            <code className="block rounded bg-indigo-50 px-2 py-1 text-xs text-indigo-600 dark:bg-indigo-900/20 dark:text-indigo-400">
              {data.dynamicBinding}
            </code>
          </fieldset>
        )}

        {/* Opacity */}
        <fieldset>
          <legend className="mb-1 text-xs font-medium text-slate-500 dark:text-slate-400">Opacity</legend>
          <input
            type="range"
            min={0}
            max={1}
            step={0.05}
            value={selectedObject.opacity ?? 1}
            onChange={(e) => updateProp("opacity", Number(e.target.value))}
            className="w-full"
          />
        </fieldset>
      </div>
    </div>
  );
}
