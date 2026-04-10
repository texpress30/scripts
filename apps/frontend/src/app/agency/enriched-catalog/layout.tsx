"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { AppShell } from "@/components/AppShell";
import { ProtectedPage } from "@/components/ProtectedPage";
import { FeedManagementProvider, useFeedManagement } from "@/lib/contexts/FeedManagementContext";
import { SubaccountSelector } from "@/components/feed-management/SubaccountSelector";
import { cn } from "@/lib/utils";

const TABS = [
  { href: "/agency/enriched-catalog/templates", label: "Templates" },
  { href: "/agency/enriched-catalog/output-feeds", label: "Output Feeds" },
  { href: "/agency/enriched-catalog/library", label: "Library" },
] as const;

function EnrichedCatalogInner({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { clients, selectedId, select, isLoading } = useFeedManagement();

  const isEditorPage = pathname.includes("/editor");

  if (isEditorPage) {
    return <>{children}</>;
  }

  return (
    <main className="p-6">
      <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <h1 className="text-xl font-semibold text-slate-900 dark:text-slate-100">Enriched Catalog</h1>
        <SubaccountSelector
          clients={clients}
          selectedId={selectedId}
          onSelect={select}
          isLoading={isLoading}
        />
      </div>

      <nav className="mb-6 flex gap-1 border-b border-slate-200 dark:border-slate-700">
        {TABS.map((tab) => {
          const isActive = pathname.startsWith(tab.href);
          return (
            <Link
              key={tab.href}
              href={tab.href}
              className={cn(
                "px-4 py-2.5 text-sm font-medium transition",
                isActive
                  ? "border-b-2 border-indigo-600 text-indigo-700 dark:border-indigo-400 dark:text-indigo-400"
                  : "text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-300",
              )}
            >
              {tab.label}
            </Link>
          );
        })}
      </nav>

      {children}
    </main>
  );
}

export default function EnrichedCatalogLayout({ children }: { children: React.ReactNode }) {
  return (
    <ProtectedPage>
      <AppShell title="Enriched Catalog">
        <FeedManagementProvider>
          <EnrichedCatalogInner>{children}</EnrichedCatalogInner>
        </FeedManagementProvider>
      </AppShell>
    </ProtectedPage>
  );
}
