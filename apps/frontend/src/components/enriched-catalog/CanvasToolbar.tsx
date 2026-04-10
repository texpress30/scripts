"use client";

import { useState } from "react";
import { Type, Image, Square, Circle, Sparkles, Trash2, ArrowUp, ArrowDown } from "lucide-react";
import { DynamicFieldPicker } from "./DynamicFieldPicker";

interface CanvasToolbarProps {
  onAddText: () => void;
  onAddDynamicField: (binding: string) => void;
  onAddShape: (type: "rectangle" | "ellipse") => void;
  onAddImage: (binding?: string) => void;
  onDelete: () => void;
  onBringForward: () => void;
  onSendBackward: () => void;
  hasSelection: boolean;
}

export function CanvasToolbar({
  onAddText,
  onAddDynamicField,
  onAddShape,
  onAddImage,
  onDelete,
  onBringForward,
  onSendBackward,
  hasSelection,
}: CanvasToolbarProps) {
  const [showFieldPicker, setShowFieldPicker] = useState(false);
  const [showShapeMenu, setShowShapeMenu] = useState(false);

  return (
    <div className="flex items-center gap-1 rounded-lg border border-slate-200 bg-white p-1 shadow-sm dark:border-slate-600 dark:bg-slate-800">
      {/* Add Text */}
      <button
        onClick={onAddText}
        className="flex items-center gap-1.5 rounded px-3 py-2 text-sm text-slate-700 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-700"
        title="Add Text"
      >
        <Type className="h-4 w-4" /> Text
      </button>

      {/* Add Dynamic Field */}
      <div className="relative">
        <button
          onClick={() => setShowFieldPicker(!showFieldPicker)}
          className="flex items-center gap-1.5 rounded px-3 py-2 text-sm text-indigo-600 hover:bg-indigo-50 dark:text-indigo-400 dark:hover:bg-indigo-900/20"
          title="Add Dynamic Field"
        >
          <Sparkles className="h-4 w-4" /> Dynamic
        </button>
        {showFieldPicker && (
          <>
            <div className="fixed inset-0 z-10" onClick={() => setShowFieldPicker(false)} />
            <div className="absolute left-0 top-full z-20 mt-1">
              <DynamicFieldPicker
                onSelect={(binding) => {
                  onAddDynamicField(binding);
                  setShowFieldPicker(false);
                }}
              />
            </div>
          </>
        )}
      </div>

      {/* Add Image */}
      <button
        onClick={() => onAddImage("{{image_link}}")}
        className="flex items-center gap-1.5 rounded px-3 py-2 text-sm text-slate-700 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-700"
        title="Add Image Zone"
      >
        <Image className="h-4 w-4" /> Image
      </button>

      {/* Add Shape */}
      <div className="relative">
        <button
          onClick={() => setShowShapeMenu(!showShapeMenu)}
          className="flex items-center gap-1.5 rounded px-3 py-2 text-sm text-slate-700 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-700"
          title="Add Shape"
        >
          <Square className="h-4 w-4" /> Shape
        </button>
        {showShapeMenu && (
          <>
            <div className="fixed inset-0 z-10" onClick={() => setShowShapeMenu(false)} />
            <div className="absolute left-0 top-full z-20 mt-1 w-36 rounded-md border border-slate-200 bg-white py-1 shadow-lg dark:border-slate-600 dark:bg-slate-700">
              <button
                onClick={() => { onAddShape("rectangle"); setShowShapeMenu(false); }}
                className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-slate-700 hover:bg-slate-50 dark:text-slate-300 dark:hover:bg-slate-600"
              >
                <Square className="h-3.5 w-3.5" /> Rectangle
              </button>
              <button
                onClick={() => { onAddShape("ellipse"); setShowShapeMenu(false); }}
                className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-slate-700 hover:bg-slate-50 dark:text-slate-300 dark:hover:bg-slate-600"
              >
                <Circle className="h-3.5 w-3.5" /> Ellipse
              </button>
            </div>
          </>
        )}
      </div>

      {/* Separator */}
      <div className="mx-1 h-6 w-px bg-slate-200 dark:bg-slate-600" />

      {/* Layer controls */}
      <button
        onClick={onBringForward}
        disabled={!hasSelection}
        className="rounded p-2 text-slate-700 hover:bg-slate-100 disabled:opacity-30 dark:text-slate-300 dark:hover:bg-slate-700"
        title="Bring Forward"
      >
        <ArrowUp className="h-4 w-4" />
      </button>
      <button
        onClick={onSendBackward}
        disabled={!hasSelection}
        className="rounded p-2 text-slate-700 hover:bg-slate-100 disabled:opacity-30 dark:text-slate-300 dark:hover:bg-slate-700"
        title="Send Backward"
      >
        <ArrowDown className="h-4 w-4" />
      </button>

      {/* Delete */}
      <button
        onClick={onDelete}
        disabled={!hasSelection}
        className="rounded p-2 text-red-500 hover:bg-red-50 disabled:opacity-30 dark:hover:bg-red-900/20"
        title="Delete Selected"
      >
        <Trash2 className="h-4 w-4" />
      </button>
    </div>
  );
}
