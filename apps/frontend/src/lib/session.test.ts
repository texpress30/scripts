import { describe, expect, it } from "vitest";

import { getCurrentRole, getSessionInfo, isReadOnlyRole, normalizeAppRole } from "./session";

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

  it("parses old and new token payloads without breaking compatibility", () => {
    localStorage.setItem("mcc_token", makeToken({ email: "old@example.com", role: "agency_admin" }));
    expect(getCurrentRole()).toBe("agency_admin");
    expect(getSessionInfo().email).toBe("old@example.com");

    localStorage.setItem(
      "mcc_token",
      makeToken({
        email: "new@example.com",
        role: "subaccount_user",
        user_id: 7,
        scope_type: "subaccount",
        membership_id: 22,
        subaccount_id: 3,
        subaccount_name: "Client A",
      })
    );
    expect(getCurrentRole()).toBe("subaccount_user");
    expect(getSessionInfo().email).toBe("new@example.com");
  });
});
