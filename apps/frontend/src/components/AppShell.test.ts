import { describe, expect, it } from "vitest";

import {
  AGENCY_SETTINGS_ITEMS,
  buildScopedClients,
  formatSubaccountBrandingLocation,
  filterAgencyNavItems,
  filterAgencySettingsItems,
  filterSubaccountNavItems,
  getNavItems,
  resolveAgencyRouteRedirect,
  resolveSubaccountModuleRedirect,
  resolveSubaccountSettingsRedirect,
  resolveSubaccountRouteGuardDecision,
} from "./AppShell";
import type { SessionAccessContext } from "@/lib/session";

function context(overrides: Partial<SessionAccessContext>): SessionAccessContext {
  return {
    email: "user@example.com",
    role: "subaccount_user",
    access_scope: "subaccount",
    allowed_subaccount_ids: [11, 15],
    allowed_subaccounts: [
      { id: 11, name: "Client 11" },
      { id: 15, name: "Client 15" },
    ],
    primary_subaccount_id: 15,
    ...overrides,
  };
}

describe("AppShell sub-account access helpers", () => {
  it("formats subaccount sidebar location from business profile city/country", () => {
    expect(formatSubaccountBrandingLocation("Onești", "România")).toBe("Locație: Onești, România");
    expect(formatSubaccountBrandingLocation("Onești", "")).toBe("Locație: Onești");
    expect(formatSubaccountBrandingLocation("", "")).toBe("Locație: -");
  });

  it("keeps settings pages out of agency main nav and in settings nav", () => {
    const navItems = getNavItems("/agency/dashboard");
    expect(navItems.some((item) => item.href === "/agency/email-templates")).toBe(false);
    expect(navItems.some((item) => item.href === "/agency/notifications")).toBe(false);
    expect(AGENCY_SETTINGS_ITEMS.some((item) => item.href === "/agency/email-templates" && item.label === "Email Templates")).toBe(true);
    expect(AGENCY_SETTINGS_ITEMS.some((item) => item.href === "/agency/notifications" && item.label === "Notificări")).toBe(true);
  });

  it("filters visible clients to allowed ids and preserves allowed order", () => {
    const result = buildScopedClients(
      [
        { id: 15, name: "Fifteen", owner_email: "fifteen@example.com" },
        { id: 44, name: "Other", owner_email: "other@example.com" },
        { id: 11, name: "Eleven", owner_email: "eleven@example.com" },
      ],
      context({ allowed_subaccount_ids: [11, 15] })
    );

    expect(result.visibleClients.map((item) => item.id)).toEqual([11, 15]);
    expect(result.allowedSubaccountIds).toEqual([11, 15]);
  });

  it("injects missing allowed client from token metadata", () => {
    const result = buildScopedClients([], context({ allowed_subaccount_ids: [11], allowed_subaccounts: [{ id: 11, name: "Token Name" }] }));
    expect(result.visibleClients).toEqual([{ id: 11, name: "Token Name", owner_email: "" }]);
  });

  it("redirects scoped users away from forbidden sub-account urls", () => {
    const accessContext = context({ allowed_subaccount_ids: [11, 15], primary_subaccount_id: 15 });

    const redirect = resolveSubaccountRouteGuardDecision({
      role: "subaccount_user",
      accessContext,
      allowedSubaccountIds: [11, 15],
      currentSubId: 99,
      subSettingsId: null,
      pathname: "/sub/99/dashboard",
    });

    expect(redirect).toBe("/sub/15/dashboard");
  });

  it("redirects to only allowed sub-account when scope has one option", () => {
    const accessContext = context({
      allowed_subaccount_ids: [7],
      allowed_subaccounts: [{ id: 7, name: "Only" }],
      primary_subaccount_id: 7,
    });

    const redirect = resolveSubaccountRouteGuardDecision({
      role: "subaccount_user",
      accessContext,
      allowedSubaccountIds: [7],
      currentSubId: null,
      subSettingsId: null,
      pathname: "/agency/dashboard",
    });

    expect(redirect).toBe("/sub/7/dashboard");
  });

  it("keeps agency role unguarded", () => {
    const accessContext = context({ role: "agency_admin", access_scope: "agency", allowed_subaccount_ids: [] });

    const redirect = resolveSubaccountRouteGuardDecision({
      role: "agency_admin",
      accessContext,
      allowedSubaccountIds: [],
      currentSubId: 200,
      subSettingsId: null,
      pathname: "/sub/200/dashboard",
    });

    expect(redirect).toBeNull();
  });

  it("filters sub-account nav items by module_keys", () => {
    const navItems = [
      { href: "/sub/15/dashboard", label: "Dashboard", icon: {} as never, moduleKey: "dashboard" as const },
      { href: "/sub/15/campaigns", label: "Campaigns", icon: {} as never, moduleKey: "campaigns" as const },
      { href: "/sub/15/rules", label: "Rules", icon: {} as never, moduleKey: "rules" as const },
    ];

    const visible = filterSubaccountNavItems({
      navItems,
      currentSubId: 15,
      moduleKeys: ["dashboard", "rules"],
      loading: false,
    });

    expect(visible.map((item) => item.label)).toEqual(["Dashboard", "Rules"]);
  });

  it("filters sub-account nav items by module_keys regardless of role label", () => {
    const navItems = [
      { href: "/sub/15/dashboard", label: "Dashboard", icon: {} as never, moduleKey: "dashboard" as const },
      { href: "/sub/15/campaigns", label: "Campaigns", icon: {} as never, moduleKey: "campaigns" as const },
    ];

    const visible = filterSubaccountNavItems({
      navItems,
      currentSubId: 15,
      moduleKeys: ["dashboard"],
      loading: false,
    });

    expect(visible.map((item) => item.label)).toEqual(["Dashboard"]);
  });

  it("keeps sidebar stable while access context is loading", () => {
    const navItems = [
      { href: "/sub/15/dashboard", label: "Dashboard", icon: {} as never, moduleKey: "dashboard" as const },
      { href: "/sub/15/campaigns", label: "Campaigns", icon: {} as never, moduleKey: "campaigns" as const },
    ];

    const visible = filterSubaccountNavItems({
      navItems,
      currentSubId: 15,
      moduleKeys: null,
      loading: true,
    });

    expect(visible).toEqual(navItems);
  });

  it("redirects manual access to first allowed module", () => {
    const redirect = resolveSubaccountModuleRedirect({
      pathname: "/sub/15/campaigns",
      currentSubId: 15,
      moduleKeys: ["dashboard", "rules"],
      loading: false,
    });

    expect(redirect).toBe("/sub/15/dashboard");
  });

  it("redirects to safe settings route when no module is allowed", () => {
    const redirect = resolveSubaccountModuleRedirect({
      pathname: "/sub/15/rules",
      currentSubId: 15,
      moduleKeys: [],
      loading: false,
    });

    expect(redirect).toBe("/agency/dashboard");
  });

  it("filters agency main nav by agency module keys", () => {
    const navItems = getNavItems("/agency/dashboard");
    const visible = filterAgencyNavItems({
      navItems,
      role: "agency_member",
      moduleKeys: ["agency_clients", "creative", "settings"],
      loading: false,
    });
    expect(visible.map((item) => item.href)).toEqual(["/agency/clients", "/creative"]);
  });

  it("filters agency settings nav by settings parent + child keys", () => {
    const visible = filterAgencySettingsItems({
      settingsItems: AGENCY_SETTINGS_ITEMS,
      role: "agency_member",
      moduleKeys: ["settings", "settings_profile", "settings_my_team"],
      loading: false,
    });
    expect(visible.map((item) => item.href)).toEqual(["/settings/profile", "/settings/team"]);
  });

  it("hides agency settings nav when settings parent is OFF", () => {
    const visible = filterAgencySettingsItems({
      settingsItems: AGENCY_SETTINGS_ITEMS,
      role: "agency_member",
      moduleKeys: ["agency_dashboard", "settings_profile"],
      loading: false,
    });
    expect(visible).toEqual([]);
  });

  it("redirects forbidden agency route to first allowed agency module", () => {
    const redirect = resolveAgencyRouteRedirect({
      pathname: "/agency/dashboard",
      role: "agency_member",
      moduleKeys: ["agency_clients", "settings", "settings_profile"],
      loading: false,
      settingsItems: AGENCY_SETTINGS_ITEMS,
    });
    expect(redirect).toBe("/agency/clients");
  });

  it("redirects forbidden agency settings route to first allowed settings child", () => {
    const redirect = resolveAgencyRouteRedirect({
      pathname: "/settings/company",
      role: "agency_member",
      moduleKeys: ["settings", "settings_profile"],
      loading: false,
      settingsItems: AGENCY_SETTINGS_ITEMS,
    });
    expect(redirect).toBe("/settings/profile");
  });

  it("redirects subaccount settings route when settings module is OFF", () => {
    const redirect = resolveSubaccountSettingsRedirect({
      pathname: "/subaccount/15/settings/profile",
      subSettingsId: 15,
      moduleKeys: ["campaigns"],
      loading: false,
    });
    expect(redirect).toBe("/sub/15/campaigns");
  });

  it("does not apply agency module filtering over sub-account navigation items", () => {
    const navItems = getNavItems("/sub/15/dashboard");
    const visible = filterAgencyNavItems({
      navItems,
      role: "agency_member",
      moduleKeys: ["creative"],
      loading: false,
    });
    expect(visible.map((item) => item.href)).toEqual(navItems.map((item) => item.href));
  });
});
