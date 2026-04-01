"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { AppShell } from "@/components/AppShell";
import { ProtectedPage } from "@/components/ProtectedPage";
import { cn } from "@/lib/utils";

const TABS = [
  { href: "/agency/feed-management/sources", label: "Sources" },
  { href: "/agency/feed-management/imports", label: "Imports" },
  { href: "/agency/feed-management/field-mapping", label: "Field Mapping" },
] as const;

export default function FeedManagementLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();

  return (
    <ProtectedPage>
      <AppShell title="Feed Management">
        <main className="p-6">
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
      </AppShell>
    </ProtectedPage>
  );
}
