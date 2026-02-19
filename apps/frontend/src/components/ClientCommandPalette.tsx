"use client";

import { Check, ChevronsUpDown, Search } from "lucide-react";
import * as React from "react";
import { Command } from "cmdk";

type ClientItem = {
  id: number;
  name: string;
  owner_email: string;
};

export function ClientCommandPalette({
  clients,
  selectedClientId,
  onSelect
}: {
  clients: ClientItem[];
  selectedClientId: number;
  onSelect: (id: number) => void;
}) {
  const [open, setOpen] = React.useState(false);

  const selected = clients.find((item) => item.id === selectedClientId);

  return (
    <div className="relative w-full max-w-sm">
      <button
        type="button"
        onClick={() => setOpen((prev) => !prev)}
        className="wm-input flex items-center justify-between"
        aria-expanded={open}
      >
        <span className="truncate text-left">{selected ? `${selected.name} (#${selected.id})` : "Selectează client"}</span>
        <ChevronsUpDown className="ml-2 h-4 w-4 shrink-0 text-slate-500" />
      </button>

      {open ? (
        <div className="absolute z-20 mt-2 w-full rounded-xl border border-slate-200 bg-white p-2 shadow-lg">
          <Command>
            <div className="mb-2 flex items-center rounded-lg border border-slate-200 px-2">
              <Search className="h-4 w-4 text-slate-500" />
              <Command.Input className="w-full bg-transparent px-2 py-2 text-sm outline-none" placeholder="Caută client..." />
            </div>

            <Command.List className="max-h-56 overflow-auto">
              <Command.Empty className="px-2 py-2 text-sm text-slate-500">Niciun client găsit.</Command.Empty>
              <Command.Group>
                {clients.map((item) => (
                  <Command.Item
                    key={item.id}
                    value={`${item.name} ${item.id} ${item.owner_email}`}
                    onSelect={() => {
                      onSelect(item.id);
                      setOpen(false);
                    }}
                    className="flex cursor-pointer items-center justify-between rounded-lg px-2 py-2 text-sm aria-selected:bg-purple-50"
                  >
                    <div className="min-w-0">
                      <p className="truncate font-medium text-slate-800">{item.name}</p>
                      <p className="truncate text-xs text-slate-500">{item.owner_email}</p>
                    </div>
                    <Check className={`ml-2 h-4 w-4 ${item.id === selectedClientId ? "opacity-100" : "opacity-0"}`} />
                  </Command.Item>
                ))}
              </Command.Group>
            </Command.List>
          </Command>
        </div>
      ) : null}
    </div>
  );
}
