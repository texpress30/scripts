"use client";

import { FormEvent, useEffect, useState } from "react";
import { X } from "lucide-react";

type CreateFolderModalProps = {
  open: boolean;
  title: string;
  initialName?: string;
  submitLabel?: string;
  submitting?: boolean;
  error?: string;
  onClose: () => void;
  onSubmit: (name: string) => void;
};

export function CreateFolderModal({
  open,
  title,
  initialName = "",
  submitLabel = "Salvează",
  submitting = false,
  error = "",
  onClose,
  onSubmit,
}: CreateFolderModalProps) {
  const [name, setName] = useState(initialName);

  useEffect(() => {
    if (open) setName(initialName);
  }, [open, initialName]);

  if (!open) return null;

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmed = name.trim();
    if (trimmed === "") return;
    onSubmit(trimmed);
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 px-4"
      onClick={onClose}
    >
      <form
        onSubmit={handleSubmit}
        onClick={(event) => event.stopPropagation()}
        className="wm-card w-full max-w-md p-5"
      >
        <div className="mb-3 flex items-center justify-between">
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
        <label className="block text-sm text-slate-700 dark:text-slate-300">
          Nume folder
          <input
            className="wm-input mt-1"
            value={name}
            onChange={(event) => setName(event.target.value)}
            autoFocus
            maxLength={120}
            disabled={submitting}
          />
        </label>
        {error ? <p className="mt-2 text-xs text-red-600">{error}</p> : null}
        <div className="mt-4 flex justify-end gap-2">
          <button
            type="button"
            onClick={onClose}
            className="wm-btn-secondary text-sm"
            disabled={submitting}
          >
            Anulează
          </button>
          <button type="submit" className="wm-btn-primary text-sm" disabled={submitting || name.trim() === ""}>
            {submitting ? "Se salvează..." : submitLabel}
          </button>
        </div>
      </form>
    </div>
  );
}
