"use client";

import { useState } from "react";
import { MoreHorizontal, Copy, Trash2, Pencil } from "lucide-react";
import type { CreativeTemplate } from "@/lib/hooks/useCreativeTemplates";

interface TemplateCardProps {
  template: CreativeTemplate;
  onEdit: (id: string) => void;
  onDuplicate: (id: string, name: string) => void;
  onDelete: (id: string) => void;
}

export function TemplateCard({ template, onEdit, onDuplicate, onDelete }: TemplateCardProps) {
  const [menuOpen, setMenuOpen] = useState(false);

  const elementCounts = template.elements.reduce(
    (acc, el) => {
      acc[el.type] = (acc[el.type] || 0) + 1;
      return acc;
    },
    {} as Record<string, number>,
  );

  return (
    <div className="mcc-card group relative flex flex-col overflow-hidden rounded-lg border border-slate-200 bg-white shadow-sm transition hover:shadow-md dark:border-slate-700 dark:bg-slate-800">
      {/* Preview area */}
      <div
        className="relative flex h-40 items-center justify-center overflow-hidden"
        style={{ backgroundColor: template.background_color || "#f1f5f9" }}
      >
        <div className="text-center text-xs text-slate-500 dark:text-slate-400">
          <div className="mb-1 text-2xl font-light text-slate-400 dark:text-slate-500">
            {template.canvas_width} x {template.canvas_height}
          </div>
          <div>
            {template.elements.length} element{template.elements.length !== 1 ? "s" : ""}
          </div>
        </div>
      </div>

      {/* Info */}
      <div className="flex flex-1 flex-col gap-2 p-4">
        <div className="flex items-start justify-between">
          <h3 className="text-sm font-medium text-slate-900 dark:text-slate-100 line-clamp-1">
            {template.name}
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
                    onClick={() => { onEdit(template.id); setMenuOpen(false); }}
                    className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-slate-700 hover:bg-slate-50 dark:text-slate-300 dark:hover:bg-slate-600"
                  >
                    <Pencil className="h-3.5 w-3.5" /> Edit
                  </button>
                  <button
                    onClick={() => { onDuplicate(template.id, `${template.name} (copy)`); setMenuOpen(false); }}
                    className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-slate-700 hover:bg-slate-50 dark:text-slate-300 dark:hover:bg-slate-600"
                  >
                    <Copy className="h-3.5 w-3.5" /> Duplicate
                  </button>
                  <button
                    onClick={() => { onDelete(template.id); setMenuOpen(false); }}
                    className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-red-600 hover:bg-red-50 dark:text-red-400 dark:hover:bg-red-900/20"
                  >
                    <Trash2 className="h-3.5 w-3.5" /> Delete
                  </button>
                </div>
              </>
            )}
          </div>
        </div>

        {/* Element type badges */}
        <div className="flex flex-wrap gap-1">
          {Object.entries(elementCounts).map(([type, count]) => (
            <span
              key={type}
              className="rounded bg-slate-100 px-1.5 py-0.5 text-xs text-slate-600 dark:bg-slate-700 dark:text-slate-400"
            >
              {count} {type.replace("_", " ")}
            </span>
          ))}
        </div>

        <p className="mt-auto text-xs text-slate-400 dark:text-slate-500">
          Updated {new Date(template.updated_at).toLocaleDateString()}
        </p>
      </div>
    </div>
  );
}
