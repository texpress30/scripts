import { describe, expect, it } from "vitest";

import { isReadOnlyRole, normalizeAppRole } from "./session";

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
});
