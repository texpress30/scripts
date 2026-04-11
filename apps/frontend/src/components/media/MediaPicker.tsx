"use client";

import { useState } from "react";
import { X } from "lucide-react";

import { MediaLibraryView } from "@/components/media/MediaLibraryView";
import type { StorageKind, StorageMediaListItem } from "@/lib/storage-client";

type MediaPickerProps = {
  open: boolean;
  clientId: number;
  title?: string;
  kind?: StorageKind;
  onClose: () => void;
  onSelect: (file: StorageMediaListItem) => void;
};

/**
 * Modal that embeds the Media Library browser in "picker" mode. Clicking a
 * file calls `onSelect` with the chosen record and closes the modal.
 */
export function MediaPicker({
  open,
  clientId,
  title = "Alege un fișier din Media Storage",
  kind,
  onClose,
  onSelect,
}: MediaPickerProps) {
  const [selected, setSelected] = useState<StorageMediaListItem | null>(null);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-black/50 px-4 py-6"
      onClick={onClose}
    >
      <div
        onClick={(event) => event.stopPropagation()}
        className="wm-card flex max-h-[90vh] w-full max-w-5xl flex-col overflow-hidden"
      >
        <div className="flex items-center justify-between border-b border-slate-200 p-4 dark:border-slate-700">
          <h3 className="text-base font-semibold text-slate-900 dark:text-slate-100">{title}</h3>
          <button
            type="button"
            onClick={onClose}
            className="rounded p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-600 dark:hover:bg-slate-800"
            aria-label="Închide"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
        <div className="flex-1 overflow-y-auto p-4">
          <MediaLibraryView
            clientId={clientId}
            embed
            kindFilter={kind}
            onFileSelect={(file) => {
              setSelected(file);
              onSelect(file);
            }}
          />
        </div>
        {selected ? (
          <div className="flex items-center justify-between border-t border-slate-200 bg-slate-50 px-4 py-2 text-xs text-slate-600 dark:border-slate-700 dark:bg-slate-800/40 dark:text-slate-300">
            <span>Selectat: {selected.display_name || selected.original_filename}</span>
          </div>
        ) : null}
      </div>
    </div>
  );
}
