"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, Loader2 } from "lucide-react";
import { useCreativeTemplates } from "@/lib/hooks/useCreativeTemplates";

const PRESET_SIZES = [
  { label: "Square (1080×1080)", w: 1080, h: 1080 },
  { label: "Landscape (1200×628)", w: 1200, h: 628 },
  { label: "Story (1080×1920)", w: 1080, h: 1920 },
  { label: "Custom", w: 0, h: 0 },
] as const;

export default function NewTemplatePage() {
  const router = useRouter();
  const { createTemplate, isCreating } = useCreativeTemplates();
  const [name, setName] = useState("");
  const [canvasWidth, setCanvasWidth] = useState(1080);
  const [canvasHeight, setCanvasHeight] = useState(1080);
  const [bgColor, setBgColor] = useState("#FFFFFF");
  const [preset, setPreset] = useState("Square (1080×1080)");
  const [error, setError] = useState("");
  const [nameError, setNameError] = useState("");

  function handlePresetChange(label: string) {
    setPreset(label);
    const found = PRESET_SIZES.find((p) => p.label === label);
    if (found && found.w > 0) {
      setCanvasWidth(found.w);
      setCanvasHeight(found.h);
    }
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setNameError("");
    setError("");
    if (!name.trim()) { setNameError("Numele template-ului este obligatoriu."); return; }
    if (canvasWidth < 50 || canvasHeight < 50) { setError("Dimensiunile canvas-ului trebuie să fie minim 50px."); return; }
    try {
      const created = await createTemplate({
        name: name.trim(),
        canvas_width: canvasWidth,
        canvas_height: canvasHeight,
        background_color: bgColor,
      });
      router.push(`/agency/creative-studio/templates/${created.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Eroare la crearea template-ului.");
    }
  }

  return (
    <>
      <div className="mb-6">
        <Link href="/agency/creative-studio/templates" className="mb-4 inline-flex items-center gap-1 text-sm text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-300">
          <ArrowLeft className="h-4 w-4" />
          Înapoi la templates
        </Link>
        <h1 className="text-xl font-semibold text-slate-900 dark:text-slate-100">Create Template</h1>
        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">Configurează metadata pentru noul template.</p>
      </div>

      {error ? <p className="mb-4 text-sm text-red-600">{error}</p> : null}

      <div className="flex flex-col gap-6 lg:flex-row">
        <form onSubmit={(e) => void handleSubmit(e)} className="wm-card max-w-xl flex-1 space-y-5 p-6">
          <div>
            <label htmlFor="tpl-name" className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">Template Name</label>
            <input id="tpl-name" value={name} onChange={(e) => setName(e.target.value)} placeholder="Ex: Summer Sale Banner" className="wm-input" />
            {nameError ? <p className="mt-1 text-xs text-red-600">{nameError}</p> : null}
          </div>

          <div>
            <label htmlFor="tpl-preset" className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">Canvas Size</label>
            <select id="tpl-preset" value={preset} onChange={(e) => handlePresetChange(e.target.value)} className="wm-input">
              {PRESET_SIZES.map((p) => (<option key={p.label} value={p.label}>{p.label}</option>))}
            </select>
          </div>

          <div className="flex gap-4">
            <div className="flex-1">
              <label htmlFor="tpl-w" className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">Width (px)</label>
              <input id="tpl-w" type="number" min={50} max={4096} value={canvasWidth} onChange={(e) => { setCanvasWidth(Number(e.target.value)); setPreset("Custom"); }} className="wm-input" />
            </div>
            <div className="flex-1">
              <label htmlFor="tpl-h" className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">Height (px)</label>
              <input id="tpl-h" type="number" min={50} max={4096} value={canvasHeight} onChange={(e) => { setCanvasHeight(Number(e.target.value)); setPreset("Custom"); }} className="wm-input" />
            </div>
          </div>

          <div>
            <label htmlFor="tpl-bg" className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">Background Color</label>
            <div className="flex items-center gap-3">
              <input id="tpl-bg" type="color" value={bgColor} onChange={(e) => setBgColor(e.target.value)} className="h-10 w-10 cursor-pointer rounded border border-slate-200 dark:border-slate-700" />
              <input type="text" value={bgColor} onChange={(e) => setBgColor(e.target.value)} className="wm-input max-w-[120px]" />
            </div>
          </div>

          <div className="flex items-center gap-3 pt-2">
            <button type="submit" className="wm-btn-primary" disabled={isCreating}>
              {isCreating ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
              {isCreating ? "Se creează..." : "Create & Open Editor"}
            </button>
            <Link href="/agency/creative-studio/templates" className="wm-btn-secondary">Anulează</Link>
          </div>
        </form>

        {/* Live canvas preview */}
        <div className="flex-shrink-0">
          <p className="mb-2 text-sm font-medium text-slate-500 dark:text-slate-400">Preview</p>
          <div
            className="rounded-lg border border-slate-200 dark:border-slate-700"
            style={{
              width: Math.min(canvasWidth, 280),
              height: Math.min(canvasHeight, 280) * (canvasHeight / canvasWidth),
              backgroundColor: bgColor,
              aspectRatio: `${canvasWidth}/${canvasHeight}`,
              maxWidth: 280,
              maxHeight: 400,
            }}
          />
          <p className="mt-1 text-xs text-slate-400">{canvasWidth} × {canvasHeight}px</p>
        </div>
      </div>
    </>
  );
}
