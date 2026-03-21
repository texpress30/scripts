import { describe, expect, it } from "vitest";

import {
  getAllowedSubaccountIds,
  getCurrentRole,
  getPrimarySubaccountId,
  getSessionAccessContext,
  getSessionAccessContextFromToken,
  getSessionInfo,
  isSubaccountScopedContext,
  isReadOnlyRole,
  normalizeAppRole,
} from "./session";

function makeToken(payload: Record<string, unknown>) {
  const encoded = Buffer.from(JSON.stringify(payload), "utf-8").toString("base64url");
  return `${encoded}.sig`;
}

describe("session role normalization", () => {
  it("maps legacy roles to canonical roles", () => {
    expect(normalizeAppRole("account_manager")).toBe("subaccount_user");
    expect(normalizeAppRole("client_viewer")).toBe("subaccount_viewer");
  });

  it("keeps canonical and special roles", () => {
    expect(normalizeAppRole("agency_member")).toBe("agency_member");
    expect(normalizeAppRole("subaccount_admin")).toBe("subaccount_admin");
    expect(normalizeAppRole("agency_owner")).toBe("agency_owner");
  });

  it("marks read-only roles correctly", () => {
    expect(isReadOnlyRole("agency_viewer")).toBe(true);
    expect(isReadOnlyRole("subaccount_viewer")).toBe(true);
    expect(isReadOnlyRole("client_viewer")).toBe(true);
    expect(isReadOnlyRole("subaccount_user")).toBe(false);
  });

  it("parses legacy single-subaccount token into allowed list", () => {
    localStorage.setItem(
      "mcc_token",
      makeToken({
        email: "legacy@example.com",
        role: "subaccount_user",
        scope_type: "subaccount",
        subaccount_id: 3,
        subaccount_name: "Client Legacy",
      })
    );

    const context = getSessionAccessContext();
    expect(getCurrentRole()).toBe("subaccount_user");
    expect(getSessionInfo().email).toBe("legacy@example.com");
    expect(context.allowed_subaccount_ids).toEqual([3]);
    expect(context.primary_subaccount_id).toBe(3);
    expect(getAllowedSubaccountIds()).toEqual([3]);
    expect(getPrimarySubaccountId()).toBe(3);
  });

  it("parses multi-subaccount token payload and keeps listed primary", () => {
    localStorage.setItem(
      "mcc_token",
      makeToken({
        email: "new@example.com",
        role: "subaccount_user",
        access_scope: "subaccount",
        allowed_subaccount_ids: [5, 8],
        allowed_subaccounts: [
          { id: 5, name: "Client A" },
          { id: 8, name: "Client B" },
        ],
        primary_subaccount_id: 8,
      })
    );

    const context = getSessionAccessContext();
    expect(context.allowed_subaccount_ids).toEqual([5, 8]);
    expect(context.allowed_subaccounts.map((entry) => entry.name)).toEqual(["Client A", "Client B"]);
    expect(context.primary_subaccount_id).toBe(8);
  });

  it("provides token parser helper for login routing decisions", () => {
    const token = makeToken({
      email: "login@example.com",
      role: "subaccount_viewer",
      allowed_subaccount_ids: [42],
      access_scope: "subaccount",
    });

    const context = getSessionAccessContextFromToken(token);
    expect(context.role).toBe("subaccount_viewer");
    expect(context.allowed_subaccount_ids).toEqual([42]);
    expect(context.primary_subaccount_id).toBe(42);
  });

  it("treats access_scope=subaccount as scoped even when role is agency", () => {
    expect(
      isSubaccountScopedContext({
        email: "user@example.com",
        role: "agency_member",
        access_scope: "subaccount",
        allowed_subaccount_ids: [9],
        allowed_subaccounts: [{ id: 9, name: "Client 9" }],
        primary_subaccount_id: 9,
      })
    ).toBe(true);
  });
});
