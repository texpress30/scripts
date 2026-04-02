"use client";

import { useState, useEffect, useCallback } from "react";
import { apiRequest } from "@/lib/api";
import { getSessionAccessContext } from "@/lib/session";

const STORAGE_KEY = "feed_management_subaccount_id";

export type SubaccountOption = {
  id: number;
  name: string;
};

/**
 * Hook that manages the selected subaccount for Feed Management.
 *
 * Selection is persisted in localStorage so it survives page refreshes.
 * Falls back to the user's primary subaccount from the JWT token.
 */
export function useFeedSubaccount() {
  const [clients, setClients] = useState<SubaccountOption[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  // Boot: load clients + restore persisted selection
  useEffect(() => {
    let ignore = false;

    async function load() {
      // 1. Fetch client list
      let items: SubaccountOption[] = [];
      try {
        const resp = await apiRequest<{ items: { id: number; name: string }[] }>("/clients", { cache: "no-store" });
        items = (resp.items ?? []).map((c) => ({ id: c.id, name: c.name }));
      } catch {
        // Fallback to session's allowed subaccounts
        const ctx = getSessionAccessContext();
        items = ctx.allowed_subaccounts.map((s) => ({ id: s.id, name: s.name }));
      }
      if (ignore) return;
      setClients(items);

      // 2. Restore persisted selection or pick default
      const stored = localStorage.getItem(STORAGE_KEY);
      const storedId = stored ? Number(stored) : null;
      const ctx = getSessionAccessContext();

      if (storedId && items.some((c) => c.id === storedId)) {
        setSelectedId(storedId);
      } else if (ctx.primary_subaccount_id && items.some((c) => c.id === ctx.primary_subaccount_id)) {
        setSelectedId(ctx.primary_subaccount_id);
      } else if (items.length === 1) {
        setSelectedId(items[0].id);
      }

      setIsLoading(false);
    }

    void load();
    return () => { ignore = true; };
  }, []);

  const select = useCallback((id: number) => {
    setSelectedId(id);
    localStorage.setItem(STORAGE_KEY, String(id));
  }, []);

  const selectedClient = clients.find((c) => c.id === selectedId) ?? null;

  return {
    clients,
    selectedId,
    selectedClient,
    select,
    isLoading,
  };
}
