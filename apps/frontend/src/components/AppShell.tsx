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
  Menu,
  Maximize2,
  Minimize2,
  Moon,
  Palette,
  Search,
  Settings,
  Sparkles,
  Sun,
  Users,
  X,
} from "lucide-react";

import { apiRequest } from "@/lib/api";
import { isPinterestIntegrationEnabled, isSnapchatIntegrationEnabled, isTikTokIntegrationEnabled } from "@/lib/featureFlags";
import { AppRole, getSessionInfo } from "@/lib/session";
import { cn } from "@/lib/utils";

type ClientItem = { id: number; name: string; owner_email: string; client_logo_url?: string | null };
type CompanySettings = { logo_url: string; city: string; country: string; company_name: string };
type TeamMemberItem = { id: number; first_name: string; last_name: string; email: string; user_role: string };
type TeamMembersResponse = { items: TeamMemberItem[]; total: number };

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

function initials(name: string): string {
  const words = name.trim().split(/\s+/).filter(Boolean);
  if (words.length === 0) return "U";
  if (words.length === 1) return words[0].slice(0, 2).toUpperCase();
  return `${words[0][0] || ""}${words[1][0] || ""}`.toUpperCase();
}

function roleForImpersonation(value: string): AppRole {
  const role = value.trim().toLowerCase();
  if (role === "admin") return "agency_admin";
  if (role === "viewer") return "subaccount_viewer";
  if (role === "member") return "subaccount_user";
  if (
    [
      "super_admin",
      "agency_owner",
      "agency_admin",
      "agency_member",
      "agency_viewer",
      "subaccount_admin",
      "subaccount_user",
      "subaccount_viewer",
      "account_manager",
      "client_viewer",
    ].includes(role)
  ) {
    return role as AppRole;
  }
  return "subaccount_user";
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
  const [companySettings, setCompanySettings] = useState<CompanySettings | null>(null);

  const [profileOpen, setProfileOpen] = useState(false);
  const [loginAsOpen, setLoginAsOpen] = useState(false);
  const [userSearch, setUserSearch] = useState("");
  const [teamUsers, setTeamUsers] = useState<TeamMemberItem[]>([]);
  const [fullscreen, setFullscreen] = useState(false);
  const [impersonatingAs, setImpersonatingAs] = useState<{ email: string; role: string } | null>(null);

  const subMatch = pathname.match(/^\/sub\/(\d+)/);
  const currentSubId = subMatch ? Number(subMatch[1]) : null;

  const subSettingsMatch = pathname.match(/^\/subaccount\/(\d+)\/settings\//);
  const subSettingsId = subSettingsMatch ? Number(subSettingsMatch[1]) : null;
  const contextClientId = currentSubId ?? subSettingsId;

  const isAgencySettingsMode = pathname.startsWith("/settings/");
  const isSubSettingsMode = pathname.startsWith("/subaccount/") && pathname.includes("/settings/");
  const isSettingsMode = isAgencySettingsMode || isSubSettingsMode;

  const settingsHeaderLabel = isSubSettingsMode ? "SUB-ACCOUNT SETTINGS" : "AGENCY SETTINGS";
  const goBackHref = isSubSettingsMode && subSettingsId ? `/sub/${subSettingsId}/dashboard` : "/agency/dashboard";

  const agencySettingsItems = [
    { href: "/settings/profile", label: "Profile" },
    { href: "/settings/company", label: "Company" },
    { href: "/settings/team", label: "My Team" },
    { href: "/settings/tags", label: "Tags" },
    { href: "/settings/audit-logs", label: "Audit Logs" },
    { href: "/settings/ai-agents", label: "Ai Agents" },
    { href: "/settings/storage", label: "Media Storage Usage" },
  ] as const;

  const subSettingsItems = useMemo(
    () =>
      subSettingsId
        ? [
            { href: `/subaccount/${subSettingsId}/settings/profile`, label: "Profil Business" },
            { href: `/subaccount/${subSettingsId}/settings/team`, label: "Echipa Mea" },
            { href: `/subaccount/${subSettingsId}/settings/integrations`, label: "Integrări" },
            { href: `/subaccount/${subSettingsId}/settings/accounts`, label: "Conturi" },
            { href: `/subaccount/${subSettingsId}/settings/tags`, label: "Tag-uri" },
            { href: `/subaccount/${subSettingsId}/settings/audit-logs`, label: "Audit Logs" },
            { href: `/subaccount/${subSettingsId}/settings/ai-agents`, label: "Agenți AI" },
          ]
        : [],
    [subSettingsId]
  );

  const settingsItems = isSubSettingsMode ? subSettingsItems : agencySettingsItems;

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

  useEffect(() => {
    let ignore = false;
    async function loadCompanySettings() {
      try {
        const result = await apiRequest<CompanySettings>("/company/settings");
        if (!ignore) setCompanySettings(result);
      } catch {
        if (!ignore) setCompanySettings(null);
      }
    }
    void loadCompanySettings();
    return () => {
      ignore = true;
    };
  }, []);

  useEffect(() => {
    let ignore = false;
    async function loadTeamUsers() {
      try {
        const result = await apiRequest<TeamMembersResponse>("/team/members?page=1&page_size=500");
        if (!ignore) setTeamUsers(result.items);
      } catch {
        if (!ignore) setTeamUsers([]);
      }
    }
    void loadTeamUsers();
    return () => {
      ignore = true;
    };
  }, []);

  useEffect(() => {
    const onFullscreen = () => setFullscreen(Boolean(document.fullscreenElement));
    document.addEventListener("fullscreenchange", onFullscreen);
    return () => document.removeEventListener("fullscreenchange", onFullscreen);
  }, []);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const value = localStorage.getItem("mcc_impersonating");
    if (!value) {
      setImpersonatingAs(null);
      return;
    }
    try {
      const parsed = JSON.parse(value) as { email: string; role: string };
      setImpersonatingAs(parsed);
    } catch {
      setImpersonatingAs(null);
    }
  }, []);

  const filteredClients = useMemo(() => {
    const query = search.trim().toLowerCase();
    if (!query) return clients;
    return clients.filter((c) => c.name.toLowerCase().includes(query) || String(c.id).includes(query));
  }, [clients, search]);

  const filteredTeamUsers = useMemo(() => {
    const q = userSearch.trim().toLowerCase();
    if (!q) return teamUsers;
    return teamUsers.filter((u) => {
      const fullName = `${u.first_name} ${u.last_name}`.toLowerCase();
      return fullName.includes(q) || u.email.toLowerCase().includes(q);
    });
  }, [teamUsers, userSearch]);

  const currentTitle = useMemo(() => {
    if (isSettingsMode) return "Settings";
    if (!currentSubId) return "Agency MCC";
    return clients.find((c) => c.id === currentSubId)?.name ?? `Sub-account #${currentSubId}`;
  }, [clients, currentSubId, isSettingsMode]);

  const currentClient = useMemo(() => clients.find((c) => c.id === contextClientId) ?? null, [clients, contextClientId]);
  const isSubContext = contextClientId !== null || isSubSettingsMode;
  const brandingTitle = isSubContext ? (currentClient?.name ?? "Sub-cont") : (companySettings?.company_name || "Agency MCC");
  const brandingSubtitle = `Locație: ${companySettings?.city || "-"}, ${companySettings?.country || "-"}`;
  const agencyLogoUrl = companySettings?.logo_url?.trim() || "";
  const subLogoUrl = currentClient?.client_logo_url?.trim() || "";
  const brandingLogoUrl = isSubContext ? subLogoUrl : agencyLogoUrl;
  const brandingInitials = useMemo(() => initials(brandingTitle), [brandingTitle]);

  const sessionInfo = getSessionInfo();
  const profileName = useMemo(() => {
    const email = sessionInfo.email || "admin@omarosa.ro";
    const local = email.split("@")[0] || "User";
    return local
      .split(/[._-]+/)
      .map((part) => (part ? `${part[0].toUpperCase()}${part.slice(1)}` : ""))
      .join(" ") || "Utilizator";
  }, [sessionInfo.email]);

  const toggleTheme = () => setTheme(theme === "dark" ? "light" : "dark");

  async function toggleFullscreen() {
    if (!document.fullscreenElement) {
      await document.documentElement.requestFullscreen();
    } else {
      await document.exitFullscreen();
    }
  }

  async function loginAs(user: TeamMemberItem) {
    try {
      const currentToken = localStorage.getItem("mcc_token");
      if (!currentToken) return;
      if (!localStorage.getItem("mcc_admin_token")) {
        localStorage.setItem("mcc_admin_token", currentToken);
      }

      const targetRole = roleForImpersonation(user.user_role);
      const result = await apiRequest<{ access_token: string }>("/auth/impersonate", {
        method: "POST",
        body: JSON.stringify({ email: user.email, role: targetRole }),
      });

      localStorage.setItem("mcc_token", result.access_token);
      localStorage.setItem("mcc_impersonating", JSON.stringify({ email: user.email, role: targetRole }));
      setImpersonatingAs({ email: user.email, role: targetRole });
      setProfileOpen(false);
      setLoginAsOpen(false);
      router.refresh();
    } catch {
      // noop for now
    }
  }

  function stopImpersonation() {
    const adminToken = localStorage.getItem("mcc_admin_token");
    if (adminToken) {
      localStorage.setItem("mcc_token", adminToken);
    }
    localStorage.removeItem("mcc_admin_token");
    localStorage.removeItem("mcc_impersonating");
    setImpersonatingAs(null);
    router.refresh();
  }

  function signout() {
    localStorage.removeItem("mcc_token");
    localStorage.removeItem("mcc_admin_token");
    localStorage.removeItem("mcc_impersonating");
    router.push("/login");
  }

  const settingsEntryHref = contextClientId ? `/subaccount/${contextClientId}/settings/profile` : "/settings/profile";

  const profileTargetHref = isSubContext ? "/settings/team" : ["super_admin", "agency_owner", "agency_admin"].includes(sessionInfo.role) ? "/settings/profile" : "/settings/team";

  const sidebarContent = (
    <div className="flex h-full flex-col">
      <div className="border-b border-slate-200 px-3 py-3 dark:border-slate-700">
        <div className="mb-3 rounded-xl border border-slate-200 bg-slate-50 p-3 text-center dark:border-slate-700 dark:bg-slate-800/50">
          <div className="mx-auto mb-2 flex h-16 w-16 items-center justify-center overflow-hidden rounded-full border border-slate-200 bg-white dark:border-slate-600 dark:bg-slate-900">
            {brandingLogoUrl ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={brandingLogoUrl} alt="Logo context" className="h-full w-full object-cover" />
            ) : (
              <span className="text-sm font-semibold text-indigo-600 dark:text-indigo-300">{brandingInitials}</span>
            )}
          </div>
          <p className="truncate text-sm font-semibold text-slate-900 dark:text-slate-100">{brandingTitle}</p>
          <p className="truncate text-xs text-slate-500 dark:text-slate-400">{brandingSubtitle}</p>
        </div>

        {isSettingsMode ? (
          <div className="space-y-2">
            <p className="text-xs font-semibold tracking-wide text-slate-500 dark:text-slate-400">{settingsHeaderLabel}</p>
            <Link
              href={goBackHref}
              onClick={() => setMobileOpen(false)}
              className="block rounded-md bg-indigo-50 px-2 py-2 text-sm font-medium text-indigo-700 hover:bg-indigo-100"
            >
              ← Go Back
            </Link>
          </div>
        ) : (
          <>
            <button
              onClick={() => setSwitcherOpen((prev) => !prev)}
              className="flex w-full items-center justify-between rounded-lg border border-slate-200 px-3 py-2 text-left text-sm font-medium text-slate-700 hover:bg-slate-50 dark:border-slate-700 dark:text-slate-200 dark:hover:bg-slate-800"
            >
              <span className="truncate">{currentTitle}</span>
              <ChevronDown className={cn("h-4 w-4 shrink-0 transition-transform", switcherOpen && "rotate-180")} />
            </button>

            {switcherOpen ? (
              <div className="mt-2 rounded-lg border border-slate-200 bg-white p-2 shadow-sm dark:border-slate-700 dark:bg-slate-900">
                <input
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  placeholder="Search sub-account..."
                  className="wm-input mb-2 h-9"
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
                  {filteredClients.length === 0 ? <p className="px-2 py-2 text-xs text-slate-500">No sub-accounts found.</p> : null}
                </div>
              </div>
            ) : null}
          </>
        )}
      </div>

      <nav className="flex-1 space-y-1 px-3 py-4">
        {isSettingsMode
          ? settingsItems.map((item) => {
              const active = pathname === item.href || pathname.startsWith(`${item.href}/`);
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  onClick={() => setMobileOpen(false)}
                  className={cn(
                    "block rounded-lg px-3 py-2 text-sm font-medium transition-colors",
                    active
                      ? "bg-indigo-50 text-indigo-700 dark:bg-indigo-950/50 dark:text-indigo-300"
                      : "text-slate-600 hover:bg-slate-100 hover:text-slate-900 dark:text-slate-400 dark:hover:bg-slate-800 dark:hover:text-slate-200"
                  )}
                >
                  {item.label}
                </Link>
              );
            })
          : navItems.map((item) => {
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
        {!isSettingsMode ? (
          <Link
            href={settingsEntryHref}
            onClick={() => setMobileOpen(false)}
            className="flex w-full items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium text-slate-600 transition-colors hover:bg-slate-100 hover:text-slate-900 dark:text-slate-400 dark:hover:bg-slate-800 dark:hover:text-slate-200"
            title={collapsed ? "Settings" : undefined}
          >
            <Settings className="h-4 w-4 shrink-0" />
            {!collapsed && <span>Settings</span>}
          </Link>
        ) : null}
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
        <header className="sticky top-0 z-20 flex h-14 items-center justify-between gap-4 border-b border-slate-200 bg-white px-4 md:px-6">
          <div className="flex items-center gap-2">
            <button onClick={() => setMobileOpen(true)} className="rounded-lg p-1.5 text-slate-500 hover:bg-slate-100 md:hidden">
              <Menu className="h-5 w-5" />
            </button>
            {headerPrefix}
            <h1 className="text-lg font-semibold text-slate-900">{title}</h1>
          </div>

          <div className="relative flex items-center gap-2">
            <button className="relative rounded-lg p-2 text-slate-500 hover:bg-slate-100" title="Notificări">
              <Bell className="h-5 w-5" />
              <span className="absolute right-1 top-1 h-2 w-2 rounded-full bg-red-500" />
            </button>

            <button onClick={toggleTheme} className="rounded-lg p-2 text-slate-500 hover:bg-slate-100" title="Schimbă tema">
              {mounted && theme === "dark" ? <Sun className="h-5 w-5" /> : <Moon className="h-5 w-5" />}
            </button>

            <button onClick={toggleFullscreen} className="rounded-lg p-2 text-slate-500 hover:bg-slate-100" title="Fullscreen">
              {fullscreen ? <Minimize2 className="h-5 w-5" /> : <Maximize2 className="h-5 w-5" />}
            </button>

            <button
              onClick={() => {
                setProfileOpen((prev) => !prev);
                setLoginAsOpen(false);
              }}
              className="flex items-center gap-2 rounded-lg border border-slate-200 px-2 py-1.5 hover:bg-slate-50"
            >
              <div className="flex h-8 w-8 items-center justify-center rounded-full bg-indigo-100 text-xs font-semibold text-indigo-700">
                {initials(profileName)}
              </div>
              <div className="hidden text-left md:block">
                <p className="text-xs font-semibold text-slate-800">{profileName}</p>
                <p className="text-[11px] text-slate-500">{sessionInfo.email || "admin@omarosa.ro"}</p>
              </div>
              <ChevronDown className="h-4 w-4 text-slate-400" />
            </button>

            {profileOpen ? (
              <div className="absolute right-0 top-12 z-50 w-80 rounded-xl border border-slate-200 bg-white p-2 shadow-lg">
                <div className="rounded-lg border border-slate-100 bg-slate-50 p-2">
                  <div className="flex items-center gap-2">
                    <div className="flex h-9 w-9 items-center justify-center rounded-full bg-indigo-100 text-xs font-semibold text-indigo-700">{initials(profileName)}</div>
                    <div>
                      <p className="text-sm font-semibold text-slate-800">{profileName}</p>
                      <p className="text-xs text-slate-500">{sessionInfo.email || "admin@omarosa.ro"}</p>
                    </div>
                  </div>
                </div>

                <div className="relative mt-2">
                  <button
                    onClick={() => setLoginAsOpen((prev) => !prev)}
                    className="flex w-full items-center justify-between rounded-md px-3 py-2 text-left text-sm text-slate-700 hover:bg-slate-100"
                  >
                    <span>Login As</span>
                    <ChevronLeft className="h-4 w-4" />
                  </button>

                  {loginAsOpen ? (
                    <div className="absolute right-full top-0 z-50 mr-2 w-80 rounded-xl border border-slate-200 bg-white p-2 shadow-lg">
                      <div className="mb-2 flex items-center gap-2 rounded-md border border-slate-200 px-2 py-1.5">
                        <Search className="h-4 w-4 text-slate-400" />
                        <input
                          className="w-full bg-transparent text-sm outline-none"
                          placeholder="Search users"
                          value={userSearch}
                          onChange={(e) => setUserSearch(e.target.value)}
                        />
                      </div>
                      <div className="max-h-64 space-y-1 overflow-y-auto">
                        {filteredTeamUsers.map((u) => (
                          <button
                            key={u.id}
                            onClick={() => void loginAs(u)}
                            className="flex w-full items-center gap-2 rounded-md px-2 py-2 text-left hover:bg-slate-100"
                          >
                            <div className="flex h-8 w-8 items-center justify-center rounded-full bg-slate-200 text-xs font-semibold text-slate-700">
                              {initials(`${u.first_name} ${u.last_name}`)}
                            </div>
                            <div className="min-w-0">
                              <p className="truncate text-sm font-medium text-slate-800">{u.first_name} {u.last_name}</p>
                              <p className="truncate text-xs text-slate-500">{u.email}</p>
                            </div>
                          </button>
                        ))}
                      </div>
                    </div>
                  ) : null}
                </div>

                <Link href={profileTargetHref} className="mt-1 block rounded-md px-3 py-2 text-sm text-slate-700 hover:bg-slate-100" onClick={() => setProfileOpen(false)}>
                  Profil
                </Link>
                <button className="mt-1 w-full rounded-md px-3 py-2 text-left text-sm text-red-600 hover:bg-red-50" onClick={signout}>
                  Signout
                </button>
              </div>
            ) : null}
          </div>
        </header>

        {impersonatingAs ? (
          <div className="border-b border-amber-200 bg-amber-50 px-4 py-2 text-sm text-amber-800 md:px-6">
            <div className="flex items-center justify-between gap-2">
              <span>Impersonating: <strong>{impersonatingAs.email}</strong> ({impersonatingAs.role})</span>
              <button className="rounded-md border border-amber-300 bg-white px-2 py-1 text-xs font-medium hover:bg-amber-100" onClick={stopImpersonation}>
                Switch back to Admin
              </button>
            </div>
          </div>
        ) : null}

        <main className="p-4 md:p-6">{children}</main>
      </div>
    </div>
  );
}
