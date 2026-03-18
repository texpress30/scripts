import { describe, expect, it } from "vitest";

import {
  AGENCY_SETTINGS_ITEMS,
  buildScopedClients,
  filterSubaccountNavItems,
  getNavItems,
  resolveSubaccountModuleRedirect,
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

  it("keeps Email Templates out of agency main nav and in settings nav", () => {
    const navItems = getNavItems("/agency/dashboard");
    expect(navItems.some((item) => item.href === "/agency/email-templates")).toBe(false);
    expect(AGENCY_SETTINGS_ITEMS.some((item) => item.href === "/agency/email-templates" && item.label === "Email Templates")).toBe(true);
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
    const accessContext = context({ role: "agency_admin", allowed_subaccount_ids: [] });

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
      role: "subaccount_user",
      currentSubId: 15,
      moduleKeys: ["dashboard", "rules"],
      loading: false,
    });

    expect(visible.map((item) => item.label)).toEqual(["Dashboard", "Rules"]);
  });

  it("does not filter nav items for agency roles", () => {
    const navItems = [
      { href: "/sub/15/dashboard", label: "Dashboard", icon: {} as never, moduleKey: "dashboard" as const },
      { href: "/sub/15/campaigns", label: "Campaigns", icon: {} as never, moduleKey: "campaigns" as const },
    ];

    const visible = filterSubaccountNavItems({
      navItems,
      role: "agency_admin",
      currentSubId: 15,
      moduleKeys: ["dashboard"],
      loading: false,
    });

    expect(visible).toEqual(navItems);
  });

  it("keeps sidebar stable while access context is loading", () => {
    const navItems = [
      { href: "/sub/15/dashboard", label: "Dashboard", icon: {} as never, moduleKey: "dashboard" as const },
      { href: "/sub/15/campaigns", label: "Campaigns", icon: {} as never, moduleKey: "campaigns" as const },
    ];

    const visible = filterSubaccountNavItems({
      navItems,
      role: "subaccount_user",
      currentSubId: 15,
      moduleKeys: null,
      loading: true,
    });

    expect(visible).toEqual(navItems);
  });

  it("redirects manual access to first allowed module", () => {
    const redirect = resolveSubaccountModuleRedirect({
      pathname: "/sub/15/campaigns",
      role: "subaccount_user",
      currentSubId: 15,
      moduleKeys: ["dashboard", "rules"],
      loading: false,
    });

    expect(redirect).toBe("/sub/15/dashboard");
  });

  it("redirects to safe settings route when no module is allowed", () => {
    const redirect = resolveSubaccountModuleRedirect({
      pathname: "/sub/15/rules",
      role: "subaccount_user",
      currentSubId: 15,
      moduleKeys: [],
      loading: false,
    });

    expect(redirect).toBe("/subaccount/15/settings/profile");
  });
});
