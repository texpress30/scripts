"use client";

import { useState } from "react";
import { MoreHorizontal, Copy, Trash2, Pencil } from "lucide-react";
import type { CreativeTemplate } from "@/lib/hooks/useCreativeTemplates";

interface TemplateGroupCardProps {
  groupName: string;
  templates: CreativeTemplate[];
  onEdit: (id: string) => void;
  onDuplicate: (id: string, name: string) => void;
  onDelete: (id: string) => void;
}

function formatDimensions(w: number, h: number): string {
  if (w === 1080 && h === 1080) return "Square";
  if (w === 1200 && h === 628) return "Landscape";
  if (w === 1080 && h === 1920) return "Stories";
  return `${w}x${h}`;
}

export function TemplateGroupCard({ groupName, templates, onEdit, onDuplicate, onDelete }: TemplateGroupCardProps) {
  const [menuOpen, setMenuOpen] = useState(false);
  const isGroup = templates.length > 1;
  const primaryTemplate = templates[0];

  return (
    <div className="mcc-card group relative flex flex-col overflow-hidden rounded-lg border border-slate-200 bg-white shadow-sm transition hover:shadow-md dark:border-slate-700 dark:bg-slate-800">
      {/* Preview area */}
      <div
        className="relative flex h-40 items-center justify-center overflow-hidden"
        style={{ backgroundColor: primaryTemplate.background_color || "#f1f5f9" }}
        onClick={() => onEdit(primaryTemplate.id)}
        role="button"
      >
        <div className="text-center text-xs text-slate-500 dark:text-slate-400">
          {isGroup ? (
            <div className="flex items-end justify-center gap-2">
              {templates.map((t) => {
                const aspectRatio = t.canvas_width / t.canvas_height;
                const maxH = 80;
                const h = maxH;
                const w = Math.round(h * aspectRatio);
                return (
                  <div
                    key={t.id}
                    className="rounded border border-slate-300 bg-white/80 dark:border-slate-500 dark:bg-slate-700/80"
                    style={{ width: Math.min(w, 80), height: Math.min(h, 80) }}
                    title={`${t.canvas_width}x${t.canvas_height}`}
                  />
                );
              })}
            </div>
          ) : (
            <>
              <div className="mb-1 text-2xl font-light text-slate-400 dark:text-slate-500">
                {primaryTemplate.canvas_width} x {primaryTemplate.canvas_height}
              </div>
              <div>
                {primaryTemplate.elements.length} element{primaryTemplate.elements.length !== 1 ? "s" : ""}
              </div>
            </>
          )}
        </div>
      </div>

      {/* Info */}
      <div className="flex flex-1 flex-col gap-2 p-4">
        <div className="flex items-start justify-between">
          <h3 className="text-sm font-medium text-slate-900 dark:text-slate-100 line-clamp-1">
            {groupName}
          </h3>
          <div className="relative">
            <button
              onClick={() => setMenuOpen(!menuOpen)}
              className="rounded p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-600 dark:hover:bg-slate-700 dark:hover:text-slate-300"
            >
              <MoreHorizontal className="h-4 w-4" />
            </button>
            {menuOpen && (
              <>
                <div className="fixed inset-0 z-10" onClick={() => setMenuOpen(false)} />
                <div className="absolute right-0 top-8 z-20 w-40 rounded-md border border-slate-200 bg-white py-1 shadow-lg dark:border-slate-600 dark:bg-slate-700">
                  <button
                    onClick={() => { onEdit(primaryTemplate.id); setMenuOpen(false); }}
                    className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-slate-700 hover:bg-slate-50 dark:text-slate-300 dark:hover:bg-slate-600"
                  >
                    <Pencil className="h-3.5 w-3.5" /> Edit
                  </button>
                  <button
                    onClick={() => { onDuplicate(primaryTemplate.id, `${groupName} (copy)`); setMenuOpen(false); }}
                    className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-slate-700 hover:bg-slate-50 dark:text-slate-300 dark:hover:bg-slate-600"
                  >
                    <Copy className="h-3.5 w-3.5" /> Duplicate
                  </button>
                  {templates.map((t) => (
                    <button
                      key={t.id}
                      onClick={() => { onDelete(t.id); setMenuOpen(false); }}
                      className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-red-600 hover:bg-red-50 dark:text-red-400 dark:hover:bg-red-900/20"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                      {isGroup ? `Delete ${t.format_label || formatDimensions(t.canvas_width, t.canvas_height)}` : "Delete"}
                    </button>
                  ))}
                </div>
              </>
            )}
          </div>
        </div>

        {/* Format badges */}
        <div className="flex flex-wrap gap-1">
          {templates.map((t) => (
            <button
              key={t.id}
              onClick={() => onEdit(t.id)}
              className="rounded bg-indigo-50 px-1.5 py-0.5 text-xs font-medium text-indigo-600 hover:bg-indigo-100 dark:bg-indigo-900/20 dark:text-indigo-400 dark:hover:bg-indigo-900/30"
            >
              {t.format_label || formatDimensions(t.canvas_width, t.canvas_height)}
            </button>
          ))}
        </div>

        <p className="mt-auto text-xs text-slate-400 dark:text-slate-500">
          Updated {new Date(primaryTemplate.updated_at).toLocaleDateString()}
        </p>
      </div>
    </div>
  );
}
