"use client";

import { useState } from "react";
import Link from "next/link";
import { MoreVertical, Pencil, Copy, Trash2, Layers } from "lucide-react";
import type { CreativeTemplate } from "@/lib/types/creative-studio";

function formatDate(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleDateString();
}

export function TemplateCard({
  template,
  onDuplicate,
  onDelete,
}: {
  template: CreativeTemplate;
  onDuplicate: (id: string) => void;
  onDelete: (id: string) => void;
}) {
  const [menuOpen, setMenuOpen] = useState(false);
  const aspectRatio = template.canvas_width / template.canvas_height;
  const dynamicBindings = template.elements.filter((el) => el.dynamic_binding).length;

  return (
    <div className="group wm-card overflow-hidden transition hover:shadow-md">
      {/* Canvas preview thumbnail */}
      <Link href={`/agency/creative-studio/templates/${template.id}`} className="block">
        <div
          className="relative flex items-center justify-center overflow-hidden border-b border-slate-200 dark:border-slate-700"
          style={{ aspectRatio: String(aspectRatio), maxHeight: 200, backgroundColor: template.background_color }}
        >
          <div className="text-center">
            <p className="text-xs font-medium" style={{ color: isLightColor(template.background_color) ? "#64748b" : "#cbd5e1" }}>
              {template.canvas_width} × {template.canvas_height}
            </p>
            <p className="mt-1 text-xs" style={{ color: isLightColor(template.background_color) ? "#94a3b8" : "#94a3b8" }}>
              {template.elements.length} element{template.elements.length !== 1 ? "s" : ""}
            </p>
          </div>
        </div>
      </Link>

      {/* Info */}
      <div className="flex items-start justify-between p-4">
        <div className="min-w-0 flex-1">
          <Link href={`/agency/creative-studio/templates/${template.id}`} className="block truncate text-sm font-medium text-slate-900 hover:text-indigo-700 dark:text-slate-100 dark:hover:text-indigo-400">
            {template.name}
          </Link>
          <div className="mt-1 flex items-center gap-3 text-xs text-slate-500 dark:text-slate-400">
            <span>{template.canvas_width}×{template.canvas_height}</span>
            {dynamicBindings > 0 ? (
              <span className="flex items-center gap-0.5">
                <Layers className="h-3 w-3" />
                {dynamicBindings} binding{dynamicBindings !== 1 ? "s" : ""}
              </span>
            ) : null}
          </div>
          <p className="mt-0.5 text-xs text-slate-400 dark:text-slate-500">{formatDate(template.created_at)}</p>
        </div>

        {/* Actions menu */}
        <div className="relative ml-2">
          <button type="button" onClick={() => setMenuOpen((p) => !p)} className="rounded p-1 text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-800" aria-label="Acțiuni">
            <MoreVertical className="h-4 w-4" />
          </button>
          {menuOpen ? (
            <>
              <div className="fixed inset-0 z-10" onClick={() => setMenuOpen(false)} />
              <div className="absolute right-0 z-20 mt-1 w-40 rounded-lg border border-slate-200 bg-white py-1 shadow-lg dark:border-slate-700 dark:bg-slate-900">
                <Link href={`/agency/creative-studio/templates/${template.id}`} className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-slate-700 hover:bg-slate-50 dark:text-slate-300 dark:hover:bg-slate-800" onClick={() => setMenuOpen(false)}>
                  <Pencil className="h-4 w-4" /> Edit
                </Link>
                <button type="button" onClick={() => { setMenuOpen(false); onDuplicate(template.id); }} className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-slate-700 hover:bg-slate-50 dark:text-slate-300 dark:hover:bg-slate-800">
                  <Copy className="h-4 w-4" /> Duplicate
                </button>
                <button type="button" onClick={() => { setMenuOpen(false); onDelete(template.id); }} className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-red-600 hover:bg-red-50 dark:text-red-400 dark:hover:bg-red-900/20">
                  <Trash2 className="h-4 w-4" /> Delete
                </button>
              </div>
            </>
          ) : null}
        </div>
      </div>
    </div>
  );
}

function isLightColor(hex: string): boolean {
  const c = hex.replace("#", "");
  if (c.length < 6) return true;
  const r = parseInt(c.substring(0, 2), 16);
  const g = parseInt(c.substring(2, 4), 16);
  const b = parseInt(c.substring(4, 6), 16);
  return (r * 299 + g * 587 + b * 114) / 1000 > 128;
}
