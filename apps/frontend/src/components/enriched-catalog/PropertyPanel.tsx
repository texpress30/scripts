"use client";

import { FlipHorizontal, FlipVertical, Bold, Italic, Underline, Strikethrough, AlignLeft, AlignCenter, AlignRight, AlignJustify, CaseSensitive } from "lucide-react";
import type { FabricObject } from "fabric";
import { cn } from "@/lib/utils";

const FONT_LIST = [
  "Arial", "Helvetica", "Poppins", "Inter", "Roboto", "Open Sans", "Montserrat",
  "Lato", "Oswald", "Raleway", "Playfair Display", "Merriweather",
  "Georgia", "Verdana", "Times New Roman", "Courier New",
  "Bebas Neue", "Dancing Script", "Pacifico", "Lobster",
  "Impact", "Comic Sans MS", "Trebuchet MS", "Tahoma",
];

interface PropertyPanelProps {
  selectedObject: FabricObject | null;
  onUpdate: () => void;
}

export function PropertyPanel({ selectedObject, onUpdate }: PropertyPanelProps) {
  if (!selectedObject) {
    return (
      <div className="w-full">
        <h3 className="mb-1 text-xs font-semibold text-slate-600 dark:text-slate-400">Select a layer</h3>
        <p className="text-[10px] text-slate-400 dark:text-slate-500">
          Click a layer in the left panel or on the canvas to edit its properties
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

  const currentX = Math.round(selectedObject.left || 0);
  const currentY = Math.round(selectedObject.top || 0);
  const currentW = Math.round((selectedObject.width || 0) * (selectedObject.scaleX || 1));
  const currentH = Math.round((selectedObject.height || 0) * (selectedObject.scaleY || 1));
  const currentR = Math.round(selectedObject.angle || 0);

  return (
    <div className="w-full">
      <h3 className="mb-3 text-xs font-semibold text-slate-600 dark:text-slate-400">
        {elementType.replace("_", " ").toUpperCase()}
      </h3>

      {/* TRANSFORM section */}
      <div className="mb-4">
        <p className="mb-2 text-[10px] font-semibold uppercase tracking-wider text-indigo-500">Transform</p>
        <div className="grid grid-cols-2 gap-x-3 gap-y-1.5">
          <label className="flex items-center gap-1 text-[10px] text-slate-500 dark:text-slate-400">
            <span className="w-3 font-medium">X</span>
            <input
              type="number"
              value={currentX}
              onChange={(e) => updateProp("left", Number(e.target.value))}
              className="mcc-input w-full rounded border px-1.5 py-1 text-[11px]"
            />
            <span className="text-slate-400">px</span>
          </label>
          <label className="flex items-center gap-1 text-[10px] text-slate-500 dark:text-slate-400">
            <span className="w-3 font-medium">Y</span>
            <input
              type="number"
              value={currentY}
              onChange={(e) => updateProp("top", Number(e.target.value))}
              className="mcc-input w-full rounded border px-1.5 py-1 text-[11px]"
            />
            <span className="text-slate-400">px</span>
          </label>
          <label className="flex items-center gap-1 text-[10px] text-slate-500 dark:text-slate-400">
            <span className="w-3 font-medium">W</span>
            <input
              type="number"
              value={currentW}
              onChange={(e) => updateProp("scaleX", Number(e.target.value) / (selectedObject.width || 1))}
              className="mcc-input w-full rounded border px-1.5 py-1 text-[11px]"
            />
            <span className="text-slate-400">px</span>
          </label>
          <label className="flex items-center gap-1 text-[10px] text-slate-500 dark:text-slate-400">
            <span className="w-3 font-medium">H</span>
            <input
              type="number"
              value={currentH}
              onChange={(e) => updateProp("scaleY", Number(e.target.value) / (selectedObject.height || 1))}
              className="mcc-input w-full rounded border px-1.5 py-1 text-[11px]"
            />
            <span className="text-slate-400">px</span>
          </label>
        </div>

        {/* Rotation + Flip */}
        <div className="mt-2 flex items-center gap-2">
          <label className="flex items-center gap-1 text-[10px] text-slate-500 dark:text-slate-400">
            <span className="w-3 font-medium">R</span>
            <input
              type="number"
              value={currentR}
              onChange={(e) => updateProp("angle", Number(e.target.value))}
              className="mcc-input w-16 rounded border px-1.5 py-1 text-[11px]"
            />
            <span className="text-slate-400">deg</span>
          </label>
          <div className="ml-auto flex gap-1">
            <button
              onClick={() => { updateProp("flipX", !selectedObject.flipX); }}
              className={`rounded border p-1 text-slate-400 hover:text-slate-600 ${selectedObject.flipX ? "border-indigo-300 bg-indigo-50 text-indigo-600" : "border-slate-200 dark:border-slate-600"}`}
              title="Flip Horizontal"
            >
              <FlipHorizontal className="h-3.5 w-3.5" />
            </button>
            <button
              onClick={() => { updateProp("flipY", !selectedObject.flipY); }}
              className={`rounded border p-1 text-slate-400 hover:text-slate-600 ${selectedObject.flipY ? "border-indigo-300 bg-indigo-50 text-indigo-600" : "border-slate-200 dark:border-slate-600"}`}
              title="Flip Vertical"
            >
              <FlipVertical className="h-3.5 w-3.5" />
            </button>
          </div>
        </div>
      </div>

      {/* TEXT STYLE section */}
      {(elementType === "text" || elementType === "dynamic_field") && (() => {
        const textObj = selectedObject as unknown as {
          fontFamily?: string; fontSize?: number; fontWeight?: string | number;
          fontStyle?: string; underline?: boolean; linethrough?: boolean;
          textAlign?: string; charSpacing?: number; lineHeight?: number;
          fill?: string;
        };
        const isBold = textObj.fontWeight === "bold" || textObj.fontWeight === 700;
        const isItalic = textObj.fontStyle === "italic";
        const isUnderline = textObj.underline === true;
        const isStrikethrough = textObj.linethrough === true;
        const textAlign = textObj.textAlign || "left";
        const toggleBtn = "rounded border p-1.5 transition";
        const activeBtn = "border-indigo-400 bg-indigo-50 text-indigo-600 dark:border-indigo-500 dark:bg-indigo-900/30 dark:text-indigo-400";
        const inactiveBtn = "border-slate-200 text-slate-400 hover:text-slate-600 dark:border-slate-600 dark:hover:text-slate-300";

        return (
          <div className="mb-4">
            <p className="mb-2 text-[10px] font-semibold uppercase tracking-wider text-indigo-500">Text</p>
            <div className="space-y-3">
              {/* Font Family */}
              <select
                value={textObj.fontFamily || "Arial"}
                onChange={(e) => updateProp("fontFamily", e.target.value)}
                className="mcc-input w-full rounded border px-2 py-1.5 text-[11px]"
              >
                {FONT_LIST.map((f) => (
                  <option key={f} value={f} style={{ fontFamily: f }}>{f}</option>
                ))}
              </select>

              {/* Font Size + Color */}
              <div className="flex items-center gap-2">
                <div className="flex items-center gap-1 rounded border border-slate-200 dark:border-slate-600">
                  <button onClick={() => updateProp("fontSize", Math.max(8, (textObj.fontSize || 16) - 1))} className="px-1.5 py-1 text-xs text-slate-400 hover:text-slate-600">-</button>
                  <input
                    type="number"
                    value={textObj.fontSize || 16}
                    onChange={(e) => updateProp("fontSize", Number(e.target.value))}
                    className="mcc-input w-10 border-0 px-0 py-1 text-center text-[11px]"
                    min={8}
                    max={400}
                  />
                  <button onClick={() => updateProp("fontSize", Math.min(400, (textObj.fontSize || 16) + 1))} className="px-1.5 py-1 text-xs text-slate-400 hover:text-slate-600">+</button>
                </div>
                <input
                  type="color"
                  value={(selectedObject.fill as string) || "#000000"}
                  onChange={(e) => updateProp("fill", e.target.value)}
                  className="h-8 w-8 cursor-pointer rounded border"
                  title="Text Color"
                />
              </div>

              {/* Bold / Italic / Underline / Strikethrough */}
              <div className="flex gap-1">
                <button onClick={() => updateProp("fontWeight", isBold ? "normal" : "bold")} className={cn(toggleBtn, isBold ? activeBtn : inactiveBtn)} title="Bold">
                  <Bold className="h-3.5 w-3.5" />
                </button>
                <button onClick={() => updateProp("fontStyle", isItalic ? "normal" : "italic")} className={cn(toggleBtn, isItalic ? activeBtn : inactiveBtn)} title="Italic">
                  <Italic className="h-3.5 w-3.5" />
                </button>
                <button onClick={() => updateProp("underline", !isUnderline)} className={cn(toggleBtn, isUnderline ? activeBtn : inactiveBtn)} title="Underline">
                  <Underline className="h-3.5 w-3.5" />
                </button>
                <button onClick={() => updateProp("linethrough", !isStrikethrough)} className={cn(toggleBtn, isStrikethrough ? activeBtn : inactiveBtn)} title="Strikethrough">
                  <Strikethrough className="h-3.5 w-3.5" />
                </button>
                <button
                  onClick={() => {
                    const text = textObj as unknown as { text?: string };
                    if (!text.text) return;
                    const current = text.text;
                    const upper = current.toUpperCase();
                    updateProp("text", current === upper ? current.toLowerCase() : upper);
                  }}
                  className={cn(toggleBtn, inactiveBtn)}
                  title="Toggle Case"
                >
                  <CaseSensitive className="h-3.5 w-3.5" />
                </button>
              </div>

              {/* Text Alignment */}
              <div className="flex gap-1">
                {([
                  ["left", AlignLeft],
                  ["center", AlignCenter],
                  ["right", AlignRight],
                  ["justify", AlignJustify],
                ] as const).map(([align, Icon]) => (
                  <button
                    key={align}
                    onClick={() => updateProp("textAlign", align)}
                    className={cn(toggleBtn, textAlign === align ? activeBtn : inactiveBtn)}
                    title={`Align ${align}`}
                  >
                    <Icon className="h-3.5 w-3.5" />
                  </button>
                ))}
              </div>

              {/* Letter Spacing */}
              <div>
                <p className="mb-1 text-[10px] text-slate-500 dark:text-slate-400">Letter Spacing</p>
                <div className="flex items-center gap-2">
                  <input
                    type="range"
                    min={-200}
                    max={1000}
                    step={10}
                    value={textObj.charSpacing || 0}
                    onChange={(e) => updateProp("charSpacing", Number(e.target.value))}
                    className="flex-1"
                  />
                  <input
                    type="number"
                    value={Math.round((textObj.charSpacing || 0) / 10)}
                    onChange={(e) => updateProp("charSpacing", Number(e.target.value) * 10)}
                    className="mcc-input w-12 rounded border px-1 py-0.5 text-center text-[10px]"
                  />
                </div>
              </div>

              {/* Line Height */}
              <div>
                <p className="mb-1 text-[10px] text-slate-500 dark:text-slate-400">Line Spacing</p>
                <div className="flex items-center gap-2">
                  <input
                    type="range"
                    min={0.5}
                    max={3}
                    step={0.1}
                    value={textObj.lineHeight || 1.16}
                    onChange={(e) => updateProp("lineHeight", Number(e.target.value))}
                    className="flex-1"
                  />
                  <input
                    type="number"
                    value={Number((textObj.lineHeight || 1.16).toFixed(1))}
                    onChange={(e) => updateProp("lineHeight", Number(e.target.value))}
                    className="mcc-input w-12 rounded border px-1 py-0.5 text-center text-[10px]"
                    step={0.1}
                  />
                </div>
              </div>
            </div>
          </div>
        );
      })()}

      {elementType === "shape" && (
        <div className="mb-4">
          <p className="mb-2 text-[10px] font-semibold uppercase tracking-wider text-indigo-500">Fill</p>
          <label className="flex items-center gap-2 text-[10px] text-slate-500 dark:text-slate-400">
            Color
            <input
              type="color"
              value={(selectedObject.fill as string) || "#CCCCCC"}
              onChange={(e) => updateProp("fill", e.target.value)}
              className="h-6 w-8 cursor-pointer rounded border"
            />
          </label>
        </div>
      )}

      {/* Binding info */}
      {elementType === "dynamic_field" && data?.dynamicBinding && (
        <div className="mb-4">
          <p className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-indigo-500">Binding</p>
          <code className="block rounded bg-indigo-50 px-2 py-1 text-[11px] text-indigo-600 dark:bg-indigo-900/20 dark:text-indigo-400">
            {data.dynamicBinding}
          </code>
        </div>
      )}

      {elementType === "image" && data?.dynamicBinding && (
        <div className="mb-4">
          <p className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-indigo-500">Image Source</p>
          <code className="block rounded bg-indigo-50 px-2 py-1 text-[11px] text-indigo-600 dark:bg-indigo-900/20 dark:text-indigo-400">
            {data.dynamicBinding}
          </code>
        </div>
      )}

      {/* Opacity */}
      <div className="mb-4">
        <p className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-indigo-500">Opacity</p>
        <div className="flex items-center gap-2">
          <input
            type="range"
            min={0}
            max={1}
            step={0.05}
            value={selectedObject.opacity ?? 1}
            onChange={(e) => updateProp("opacity", Number(e.target.value))}
            className="flex-1"
          />
          <span className="text-[10px] text-slate-400">{Math.round((selectedObject.opacity ?? 1) * 100)}%</span>
        </div>
      </div>
    </div>
  );
}
