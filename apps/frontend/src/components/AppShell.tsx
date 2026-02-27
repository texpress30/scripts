"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useTheme } from "next-themes";
import { useEffect, useMemo, useState } from "react";
import {
  Bell,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  LayoutDashboard,
  LogOut,
  Menu,
  Moon,
  Palette,
  Sparkles,
  Sun,
  Users,
  X,
} from "lucide-react";

import { apiRequest } from "@/lib/api";
import { isPinterestIntegrationEnabled, isSnapchatIntegrationEnabled, isTikTokIntegrationEnabled } from "@/lib/featureFlags";
import { cn } from "@/lib/utils";

type ClientItem = { id: number; name: string; owner_email: string };
function getNavItems(pathname: string) {
  const subMatch = pathname.match(/^\/sub\/(\d+)/);
  if (subMatch) {
    const id = subMatch[1];
    return [
      { href: `/sub/${id}/dashboard`, label: "Dashboard", icon: LayoutDashboard },
      { href: `/sub/${id}/campaigns`, label: "Campaigns", icon: Bell },
      { href: `/sub/${id}/rules`, label: "Rules", icon: Sparkles },
      { href: `/sub/${id}/creative`, label: "Creative", icon: Palette },
      { href: `/sub/${id}/recommendations`, label: "Recommendations", icon: Users },
    ];
  }

  const agencyItems = [
    { href: "/agency/dashboard", label: "Agency Dashboard", icon: LayoutDashboard },
    { href: "/agency/clients", label: "Agency Clients", icon: Users },
    { href: "/agency-accounts", label: "Agency Accounts", icon: Bell },
    { href: "/agency/audit", label: "Agency Audit", icon: Sparkles },
    { href: "/notifications", label: "Notificari", icon: Bell },
    { href: "/creative", label: "Creative", icon: Palette },
  ];

  if (isTikTokIntegrationEnabled() || isPinterestIntegrationEnabled() || isSnapchatIntegrationEnabled()) {
    agencyItems.splice(3, 0, { href: "/agency/integrations", label: "Integrations (beta)", icon: Sparkles });
  }

  return agencyItems;
}

export function AppShell({
  title,
  headerPrefix,
  children,
}: {
  title: React.ReactNode;
  headerPrefix?: React.ReactNode;
  children: React.ReactNode;
}) {
  const pathname = usePathname();
  const router = useRouter();
  const navItems = getNavItems(pathname);
  const { theme, setTheme } = useTheme();

  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [mounted, setMounted] = useState(false);

  const [switcherOpen, setSwitcherOpen] = useState(false);
  const [search, setSearch] = useState("");
  const [clients, setClients] = useState<ClientItem[]>([]);

  const subMatch = pathname.match(/^\/sub\/(\d+)/);
  const currentSubId = subMatch ? Number(subMatch[1]) : null;

  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    let ignore = false;
    async function loadClients() {
      try {
        const result = await apiRequest<{ items: ClientItem[] }>("/clients");
        if (!ignore) setClients(result.items);
      } catch {
        if (!ignore) setClients([]);
      }
    }
    void loadClients();
    return () => {
      ignore = true;
    };
  }, []);

  const filteredClients = useMemo(() => {
    const query = search.trim().toLowerCase();
    if (!query) return clients;
    return clients.filter((c) => c.name.toLowerCase().includes(query) || String(c.id).includes(query));
  }, [clients, search]);

  const currentTitle = useMemo(() => {
    if (!currentSubId) return "Agency MCC";
    return clients.find((c) => c.id === currentSubId)?.name ?? `Sub-account #${currentSubId}`;
  }, [clients, currentSubId]);

  const toggleTheme = () => setTheme(theme === "dark" ? "light" : "dark");

  const sidebarContent = (
    <div className="flex h-full flex-col">
      <div className="border-b border-slate-200 px-3 py-3 dark:border-slate-700">
        <button
          onClick={() => setSwitcherOpen((v) => !v)}
          className="flex w-full items-center justify-between rounded-lg border border-slate-200 bg-white px-3 py-2 text-left text-sm font-medium text-slate-700 hover:bg-slate-50 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200"
        >
          <span className="truncate">{currentTitle}</span>
          <ChevronDown className="h-4 w-4 shrink-0" />
        </button>

        {switcherOpen ? (
          <div className="mt-2 rounded-lg border border-slate-200 bg-white p-2 shadow-lg dark:border-slate-700 dark:bg-slate-900">
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search sub-account..."
              className="mb-2 h-9 w-full rounded-md border border-slate-200 px-2 text-sm outline-none dark:border-slate-700 dark:bg-slate-800"
            />

            {currentSubId ? (
              <button
                onClick={() => {
                  setSwitcherOpen(false);
                  router.push("/agency/dashboard");
                }}
                className="mb-2 w-full rounded-md bg-indigo-50 px-2 py-2 text-left text-sm font-medium text-indigo-700 hover:bg-indigo-100"
              >
                ← Back to Agency
              </button>
            ) : null}

            <div className="max-h-56 overflow-auto">
              {filteredClients.map((client) => (
                <button
                  key={client.id}
                  onClick={() => {
                    setSwitcherOpen(false);
                    router.push(`/sub/${client.id}/dashboard`);
                  }}
                  className="block w-full rounded-md px-2 py-2 text-left text-sm text-slate-700 hover:bg-slate-100 dark:text-slate-200 dark:hover:bg-slate-800"
                >
                  {client.name}
                  <span className="ml-1 text-xs text-slate-400">#{client.id}</span>
                </button>
              ))}
              {filteredClients.length === 0 ? (
                <p className="px-2 py-2 text-xs text-slate-500">No sub-accounts found.</p>
              ) : null}
            </div>
          </div>
        ) : null}
      </div>

      <nav className="flex-1 space-y-1 px-3 py-4">
        {navItems.map((item) => {
          const active = pathname === item.href || pathname.startsWith(`${item.href}/`);
          const Icon = item.icon;
          return (
            <Link
              key={item.href}
              href={item.href}
              onClick={() => setMobileOpen(false)}
              className={cn(
                "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
                active
                  ? "bg-indigo-50 text-indigo-700 dark:bg-indigo-950/50 dark:text-indigo-300"
                  : "text-slate-600 hover:bg-slate-100 hover:text-slate-900 dark:text-slate-400 dark:hover:bg-slate-800 dark:hover:text-slate-200"
              )}
              title={collapsed ? item.label : undefined}
            >
              <Icon className="h-4 w-4 shrink-0" />
              {!collapsed && <span className="truncate">{item.label}</span>}
            </Link>
          );
        })}




      </nav>

      <div className="space-y-1 border-t border-slate-200 px-3 py-4 dark:border-slate-700">
        <button
          onClick={toggleTheme}
          className="flex w-full items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium text-slate-600 transition-colors hover:bg-slate-100 hover:text-slate-900 dark:text-slate-400 dark:hover:bg-slate-800 dark:hover:text-slate-200"
          title={collapsed ? "Schimba tema" : undefined}
        >
          {mounted && theme === "dark" ? <Sun className="h-4 w-4 shrink-0" /> : <Moon className="h-4 w-4 shrink-0" />}
          {!collapsed && <span>Schimba tema</span>}
        </button>

        <Link
          href="/login"
          onClick={() => setMobileOpen(false)}
          className="flex w-full items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium text-slate-600 transition-colors hover:bg-red-50 hover:text-red-600 dark:text-slate-400 dark:hover:bg-red-950/30 dark:hover:text-red-400"
          title={collapsed ? "Logout" : undefined}
        >
          <LogOut className="h-4 w-4 shrink-0" />
          {!collapsed && <span>Logout</span>}
        </Link>
      </div>

      <div className="hidden border-t border-slate-200 px-3 py-3 dark:border-slate-700 md:block">
        <button
          onClick={() => setCollapsed(!collapsed)}
          className="flex w-full items-center justify-center rounded-lg p-2 text-slate-400 transition-colors hover:bg-slate-100 hover:text-slate-600 dark:hover:bg-slate-800 dark:hover:text-slate-300"
        >
          {collapsed ? <ChevronRight className="h-4 w-4" /> : <ChevronLeft className="h-4 w-4" />}
        </button>
      </div>
    </div>
  );

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-950">
      {mobileOpen && <div className="fixed inset-0 z-40 bg-black/40 md:hidden" onClick={() => setMobileOpen(false)} />}

      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-50 w-72 transform border-r border-slate-200 bg-white transition-transform duration-200 ease-in-out dark:border-slate-700 dark:bg-slate-900 md:hidden",
          mobileOpen ? "translate-x-0" : "-translate-x-full"
        )}
      >
        <div className="absolute right-2 top-3">
          <button onClick={() => setMobileOpen(false)} className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800">
            <X className="h-5 w-5" />
          </button>
        </div>
        {sidebarContent}
      </aside>

      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-30 hidden border-r border-slate-200 bg-white transition-all duration-200 dark:border-slate-700 dark:bg-slate-900 md:block",
          collapsed ? "w-16" : "w-72"
        )}
      >
        {sidebarContent}
      </aside>

      <div className={cn("transition-all duration-200", collapsed ? "md:pl-16" : "md:pl-72")}>
        <header className="sticky top-0 z-20 flex h-14 items-center gap-4 border-b border-slate-200 bg-white/80 px-4 backdrop-blur dark:border-slate-700 dark:bg-slate-900/80 md:px-6">
          <button onClick={() => setMobileOpen(true)} className="rounded-lg p-1.5 text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-800 md:hidden">
            <Menu className="h-5 w-5" />
          </button>
          <div className="flex items-center gap-2">
            {headerPrefix}
            <h1 className="text-lg font-semibold text-slate-900 dark:text-slate-100">{title}</h1>
          </div>
        </header>

        <main className="p-4 md:p-6">{children}</main>
      </div>
    </div>
  );
}
