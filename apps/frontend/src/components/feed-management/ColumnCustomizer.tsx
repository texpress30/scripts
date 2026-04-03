"use client";

import { useState, useRef, useEffect } from "react";
import { SlidersHorizontal } from "lucide-react";
import type { ColumnDef } from "@/lib/hooks/useChannelProducts";

type Props = {
  columns: ColumnDef[];
  visible: Set<string>;
  onChange: (visible: Set<string>) => void;
};

export function ColumnCustomizer({ columns, visible, onChange }: Props) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    if (open) document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [open]);

  const allOn = columns.length === visible.size;

  function toggleAll() {
    onChange(allOn ? new Set<string>() : new Set(columns.map((c) => c.key)));
  }

  function toggle(key: string) {
    const next = new Set(visible);
    if (next.has(key)) next.delete(key);
    else next.add(key);
    onChange(next);
  }

  return (
    <div className="relative" ref={ref}>
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="wm-btn-secondary inline-flex items-center gap-1.5 text-xs"
      >
        <SlidersHorizontal className="h-3.5 w-3.5" />
        Customize Columns
      </button>

      {open && (
        <div className="absolute right-0 top-full z-20 mt-1 w-56 rounded-lg border border-slate-200 bg-white shadow-lg dark:border-slate-700 dark:bg-slate-900">
          <div className="border-b border-slate-200 px-3 py-2 dark:border-slate-700">
            <label className="flex items-center gap-2 text-xs font-medium text-slate-700 dark:text-slate-300">
              <input
                type="checkbox"
                checked={allOn}
                onChange={toggleAll}
                className="rounded border-slate-300"
              />
              {allOn ? "Deselect All" : "Select All"}
            </label>
          </div>
          <div className="max-h-60 overflow-y-auto py-1">
            {columns.map((col) => (
              <label
                key={col.key}
                className="flex items-center gap-2 px-3 py-1.5 text-xs text-slate-700 hover:bg-slate-50 dark:text-slate-300 dark:hover:bg-slate-800"
              >
                <input
                  type="checkbox"
                  checked={visible.has(col.key)}
                  onChange={() => toggle(col.key)}
                  className="rounded border-slate-300"
                />
                {col.label}
              </label>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
