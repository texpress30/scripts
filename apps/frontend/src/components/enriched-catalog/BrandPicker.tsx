"use client";

import { useState } from "react";
import { Palette, Star } from "lucide-react";
import type { BrandPreset } from "@/lib/hooks/useBrandPresets";

interface BrandPickerProps {
  presets: BrandPreset[];
  onApplyColor: (color: string) => void;
  onApplyFont: (font: string) => void;
  onApplyBackground: (color: string) => void;
}

export function BrandPicker({ presets, onApplyColor, onApplyFont, onApplyBackground }: BrandPickerProps) {
  const [open, setOpen] = useState(false);

  if (presets.length === 0) return null;

  return (
    <div className="relative">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-1.5 rounded px-3 py-2 text-sm text-slate-700 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-700"
        title="Brand Presets"
      >
        <Palette className="h-4 w-4" /> Brand
      </button>

      {open && (
        <>
          <div className="fixed inset-0 z-10" onClick={() => setOpen(false)} />
          <div className="absolute left-0 top-full z-20 mt-1 w-72 rounded-md border border-slate-200 bg-white shadow-lg dark:border-slate-600 dark:bg-slate-700">
            <div className="border-b border-slate-200 px-3 py-2 dark:border-slate-600">
              <p className="text-xs font-medium text-slate-500 dark:text-slate-400">Apply brand preset</p>
            </div>
            <div className="max-h-80 overflow-y-auto p-2">
              {presets.map((preset) => (
                <div key={preset.id} className="mb-3 last:mb-0">
                  <div className="mb-1.5 flex items-center gap-1.5">
                    <span className="text-xs font-medium text-slate-700 dark:text-slate-300">{preset.name}</span>
                    {preset.is_default && <Star className="h-3 w-3 fill-amber-400 text-amber-400" />}
                  </div>

                  {/* Colors — click to apply */}
                  <div className="mb-1.5 flex flex-wrap gap-1">
                    {preset.colors.map((color, idx) => (
                      <div key={idx} className="group relative">
                        <button
                          onClick={() => { onApplyColor(color); }}
                          className="h-6 w-6 rounded border border-slate-200 transition hover:scale-110 hover:ring-2 hover:ring-indigo-300 dark:border-slate-500"
                          style={{ backgroundColor: color }}
                          title={`Apply ${color} to selected element`}
                        />
                        <button
                          onClick={() => { onApplyBackground(color); setOpen(false); }}
                          className="absolute -right-1 -top-1 hidden rounded-full bg-slate-600 p-0.5 text-white group-hover:block"
                          title="Set as background"
                        >
                          <span className="block h-2 w-2 text-[6px] leading-none">BG</span>
                        </button>
                      </div>
                    ))}
                  </div>

                  {/* Fonts — click to apply */}
                  {preset.fonts.length > 0 && (
                    <div className="flex flex-wrap gap-1">
                      {preset.fonts.map((font, idx) => (
                        <button
                          key={idx}
                          onClick={() => { onApplyFont(font); setOpen(false); }}
                          className="rounded bg-slate-100 px-1.5 py-0.5 text-xs text-slate-600 hover:bg-indigo-100 hover:text-indigo-700 dark:bg-slate-600 dark:text-slate-400 dark:hover:bg-indigo-900/30 dark:hover:text-indigo-400"
                        >
                          {font}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
