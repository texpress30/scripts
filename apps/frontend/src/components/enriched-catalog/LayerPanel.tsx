"use client";

import { Type, Image, Square, Circle, Sparkles, Eye, EyeOff, Trash2 } from "lucide-react";
import type { FabricObject } from "fabric";

interface LayerPanelProps {
  objects: FabricObject[];
  selectedIndex: number | null;
  onSelect: (index: number) => void;
  onToggleVisibility: (index: number) => void;
  onDelete: (index: number) => void;
}

function getLayerIcon(obj: FabricObject) {
  const elementType = (obj as unknown as { data?: { elementType?: string } }).data?.elementType || "";
  switch (elementType) {
    case "text":
      return <Type className="h-3.5 w-3.5" />;
    case "dynamic_field":
      return <Sparkles className="h-3.5 w-3.5 text-indigo-500" />;
    case "image":
      return <Image className="h-3.5 w-3.5" />;
    case "shape": {
      const shapeType = (obj as unknown as { data?: { shapeType?: string } }).data?.shapeType;
      return shapeType === "ellipse"
        ? <Circle className="h-3.5 w-3.5" />
        : <Square className="h-3.5 w-3.5" />;
    }
    default:
      return <Square className="h-3.5 w-3.5" />;
  }
}

function getLayerLabel(obj: FabricObject): string {
  const data = (obj as unknown as { data?: { elementType?: string; dynamicBinding?: string } }).data;
  const elementType = data?.elementType || "";
  switch (elementType) {
    case "text":
      return (obj as unknown as { text?: string }).text?.slice(0, 20) || "Text";
    case "dynamic_field":
      return data?.dynamicBinding || "Dynamic Field";
    case "image":
      return data?.dynamicBinding || "Image";
    case "shape":
      return (obj as unknown as { data?: { shapeType?: string } }).data?.shapeType || "Shape";
    default:
      return "Layer";
  }
}

export function LayerPanel({ objects, selectedIndex, onSelect, onToggleVisibility, onDelete }: LayerPanelProps) {
  // Show layers in reverse order (top layer first)
  const reversedObjects = [...objects].reverse();

  return (
    <div className="w-56 rounded-lg border border-slate-200 bg-white dark:border-slate-700 dark:bg-slate-800">
      <div className="border-b border-slate-200 px-3 py-2 dark:border-slate-600">
        <p className="text-xs font-semibold text-slate-600 dark:text-slate-400">Layers</p>
      </div>
      <div className="max-h-64 overflow-y-auto">
        {reversedObjects.length === 0 ? (
          <p className="px-3 py-4 text-center text-xs text-slate-400">No layers yet</p>
        ) : (
          reversedObjects.map((obj, reverseIdx) => {
            const actualIndex = objects.length - 1 - reverseIdx;
            const isSelected = selectedIndex === actualIndex;
            const isVisible = obj.visible !== false;

            return (
              <div
                key={reverseIdx}
                onClick={() => onSelect(actualIndex)}
                className={`flex cursor-pointer items-center gap-2 border-b border-slate-100 px-3 py-2 text-sm last:border-0 dark:border-slate-700 ${
                  isSelected
                    ? "bg-indigo-50 text-indigo-700 dark:bg-indigo-900/20 dark:text-indigo-400"
                    : "text-slate-700 hover:bg-slate-50 dark:text-slate-300 dark:hover:bg-slate-700/50"
                }`}
              >
                <span className={isVisible ? "" : "opacity-40"}>{getLayerIcon(obj)}</span>
                <span className={`flex-1 truncate text-xs ${isVisible ? "" : "opacity-40"}`}>
                  {getLayerLabel(obj)}
                </span>
                <button
                  onClick={(e) => { e.stopPropagation(); onToggleVisibility(actualIndex); }}
                  className="rounded p-0.5 text-slate-400 hover:text-slate-600 dark:hover:text-slate-300"
                >
                  {isVisible ? <Eye className="h-3 w-3" /> : <EyeOff className="h-3 w-3" />}
                </button>
                <button
                  onClick={(e) => { e.stopPropagation(); onDelete(actualIndex); }}
                  className="rounded p-0.5 text-slate-400 hover:text-red-500"
                >
                  <Trash2 className="h-3 w-3" />
                </button>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
