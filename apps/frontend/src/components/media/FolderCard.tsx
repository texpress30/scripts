"use client";

import { Folder, Lock, MoreVertical } from "lucide-react";
import { useState } from "react";

import { type StorageFolder } from "@/lib/storage-client";
import { cn } from "@/lib/utils";

type FolderCardProps = {
  folder: StorageFolder;
  onOpen: (folder: StorageFolder) => void;
  onRename?: (folder: StorageFolder) => void;
  onDelete?: (folder: StorageFolder) => void;
};

export function FolderCard({ folder, onOpen, onRename, onDelete }: FolderCardProps) {
  const [menuOpen, setMenuOpen] = useState(false);
  const isSystem = folder.system;

  return (
    <div
      role="button"
      tabIndex={0}
      onClick={() => onOpen(folder)}
      onKeyDown={(event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          onOpen(folder);
        }
      }}
      className={cn(
        "group relative flex w-full cursor-pointer items-center justify-between rounded-lg border border-slate-200 bg-slate-50 px-3 py-2.5 text-left transition-colors hover:border-slate-300 hover:bg-slate-100",
        "dark:border-slate-700 dark:bg-slate-800/60 dark:hover:border-slate-600",
      )}
      title={folder.name}
    >
      <div className="flex min-w-0 items-center gap-2">
        <Folder className="h-4 w-4 shrink-0 text-slate-500 dark:text-slate-400" />
        <span className="truncate text-xs font-medium text-slate-700 dark:text-slate-200">{folder.name}</span>
        {isSystem && (
          <Lock className="h-3 w-3 shrink-0 text-slate-400" aria-label="System folder" />
        )}
      </div>
      {!isSystem && (onRename || onDelete) && (
        <div className="relative shrink-0">
          <button
            type="button"
            onClick={(event) => {
              event.stopPropagation();
              setMenuOpen((prev) => !prev);
            }}
            className="rounded p-1 text-slate-400 hover:bg-slate-200 hover:text-slate-600 dark:hover:bg-slate-700 dark:hover:text-slate-200"
            aria-label="Acțiuni folder"
          >
            <MoreVertical className="h-4 w-4" />
          </button>
          {menuOpen && (
            <div
              className="absolute right-0 top-full z-20 mt-1 w-36 overflow-hidden rounded-md border border-slate-200 bg-white shadow-lg dark:border-slate-700 dark:bg-slate-900"
              onClick={(event) => event.stopPropagation()}
            >
              {onRename && (
                <button
                  type="button"
                  onClick={() => {
                    setMenuOpen(false);
                    onRename(folder);
                  }}
                  className="block w-full px-3 py-2 text-left text-xs text-slate-700 hover:bg-slate-50 dark:text-slate-200 dark:hover:bg-slate-800"
                >
                  Redenumește
                </button>
              )}
              {onDelete && (
                <button
                  type="button"
                  onClick={() => {
                    setMenuOpen(false);
                    onDelete(folder);
                  }}
                  className="block w-full px-3 py-2 text-left text-xs text-rose-600 hover:bg-rose-50 dark:hover:bg-rose-900/30"
                >
                  Șterge
                </button>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
