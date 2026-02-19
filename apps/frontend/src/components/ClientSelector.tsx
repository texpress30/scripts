"use client";

import { useEffect, useState, useCallback } from "react";
import { Command } from "cmdk";
import { Search, Building2, ChevronDown, X } from "lucide-react";
import { cn } from "@/lib/utils";

// Placeholder clients (will be replaced with FastAPI data)
const MOCK_CLIENTS = [
  { id: 1, name: "Acme Corp", category: "E-Commerce" },
  { id: 2, name: "TechStart SRL", category: "SaaS" },
  { id: 3, name: "FoodExpress", category: "Delivery" },
  { id: 4, name: "StyleBoutique", category: "Fashion" },
  { id: 5, name: "AutoParts Pro", category: "Automotive" },
  { id: 6, name: "HealthPlus", category: "Healthcare" },
];

type ClientSelectorProps = {
  selectedClientId: number;
  onClientChange: (clientId: number) => void;
};

export function ClientSelector({ selectedClientId, onClientChange }: ClientSelectorProps) {
  const [open, setOpen] = useState(false);
  const selectedClient = MOCK_CLIENTS.find((c) => c.id === selectedClientId) || MOCK_CLIENTS[0];

  // Listen for CMD+K
  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        setOpen((prev) => !prev);
      }
    }
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, []);

  const handleSelect = useCallback(
    (clientId: string) => {
      onClientChange(Number(clientId));
      setOpen(false);
    },
    [onClientChange]
  );

  return (
    <>
      {/* Trigger button */}
      <button
        onClick={() => setOpen(true)}
        className="flex items-center gap-2 rounded-lg border border-input bg-background px-3 py-1.5 text-sm transition-colors hover:bg-accent"
      >
        <Building2 className="h-3.5 w-3.5 text-muted-foreground" />
        <span className="font-medium text-foreground">{selectedClient.name}</span>
        <span className="text-xs text-muted-foreground">{selectedClient.category}</span>
        <ChevronDown className="ml-1 h-3 w-3 text-muted-foreground" />
        <kbd className="ml-2 hidden rounded border border-border bg-muted px-1.5 py-0.5 text-[10px] font-medium text-muted-foreground sm:inline-block">
          {"⌘K"}
        </kbd>
      </button>

      {/* Command palette overlay */}
      {open && (
        <div className="fixed inset-0 z-[100] flex items-start justify-center pt-[20vh]">
          {/* Backdrop */}
          <div
            className="absolute inset-0 bg-foreground/20 backdrop-blur-sm"
            onClick={() => setOpen(false)}
          />

          {/* Command palette */}
          <div className="relative w-full max-w-lg animate-fade-in">
            <Command
              className="overflow-hidden rounded-xl border border-border bg-card shadow-2xl"
              shouldFilter={true}
            >
              {/* Search input */}
              <div className="flex items-center border-b border-border px-4">
                <Search className="mr-2 h-4 w-4 shrink-0 text-muted-foreground" />
                <Command.Input
                  placeholder="Cauta client..."
                  className="flex h-12 w-full bg-transparent text-sm text-foreground outline-none placeholder:text-muted-foreground"
                  autoFocus
                />
                <button
                  onClick={() => setOpen(false)}
                  className="ml-2 rounded-md p-1 text-muted-foreground hover:text-foreground"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>

              {/* Results */}
              <Command.List className="max-h-72 overflow-y-auto p-2">
                <Command.Empty className="py-6 text-center text-sm text-muted-foreground">
                  Niciun client gasit.
                </Command.Empty>

                <Command.Group
                  heading={
                    <span className="px-2 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                      Clienti
                    </span>
                  }
                >
                  {MOCK_CLIENTS.map((client) => (
                    <Command.Item
                      key={client.id}
                      value={`${client.name} ${client.category}`}
                      onSelect={() => handleSelect(String(client.id))}
                      className={cn(
                        "flex cursor-pointer items-center gap-3 rounded-lg px-3 py-2.5 text-sm transition-colors",
                        "data-[selected=true]:bg-accent",
                        selectedClientId === client.id && "bg-primary/5"
                      )}
                    >
                      <div className="flex h-8 w-8 items-center justify-center rounded-md bg-muted">
                        <Building2 className="h-4 w-4 text-muted-foreground" />
                      </div>
                      <div className="flex-1">
                        <p className="font-medium text-foreground">{client.name}</p>
                        <p className="text-xs text-muted-foreground">{client.category}</p>
                      </div>
                      {selectedClientId === client.id && (
                        <span className="text-xs font-medium text-primary">Activ</span>
                      )}
                    </Command.Item>
                  ))}
                </Command.Group>
              </Command.List>

              {/* Footer */}
              <div className="flex items-center justify-between border-t border-border px-4 py-2">
                <div className="flex items-center gap-2 text-xs text-muted-foreground">
                  <kbd className="rounded border border-border bg-muted px-1 py-0.5 text-[10px]">
                    {"↑↓"}
                  </kbd>
                  <span>navigate</span>
                  <kbd className="rounded border border-border bg-muted px-1 py-0.5 text-[10px]">
                    {"↵"}
                  </kbd>
                  <span>select</span>
                  <kbd className="rounded border border-border bg-muted px-1 py-0.5 text-[10px]">
                    esc
                  </kbd>
                  <span>close</span>
                </div>
              </div>
            </Command>
          </div>
        </div>
      )}
    </>
  );
}
