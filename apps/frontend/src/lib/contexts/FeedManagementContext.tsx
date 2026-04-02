"use client";

import { createContext, useContext, type ReactNode } from "react";
import { useFeedSubaccount, type SubaccountOption } from "@/lib/hooks/useFeedSubaccount";

interface FeedManagementContextType {
  clients: SubaccountOption[];
  selectedId: number | null;
  selectedClient: SubaccountOption | null;
  select: (id: number) => void;
  isLoading: boolean;
}

const FeedManagementContext = createContext<FeedManagementContextType | null>(null);

export function FeedManagementProvider({ children }: { children: ReactNode }) {
  const value = useFeedSubaccount();
  return (
    <FeedManagementContext.Provider value={value}>
      {children}
    </FeedManagementContext.Provider>
  );
}

export function useFeedManagement(): FeedManagementContextType {
  const ctx = useContext(FeedManagementContext);
  if (!ctx) {
    throw new Error("useFeedManagement must be used within FeedManagementProvider");
  }
  return ctx;
}
