import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  claimBigCommerceStore,
  deleteBigCommerceSource,
  fetchAvailableBigCommerceStores,
  listBigCommerceSources,
  testBigCommerceConnectionByStoreHash,
  testBigCommerceSourceConnection,
  updateBigCommerceSource,
} from "./useBigCommerceSource";

const apiRequestMock = vi.fn();

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    apiRequest: (...args: unknown[]) => apiRequestMock(...args),
  };
});

describe("useBigCommerceSource", () => {
  beforeEach(() => {
    apiRequestMock.mockReset();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("fetchAvailableBigCommerceStores hits the right endpoint", async () => {
    apiRequestMock.mockResolvedValueOnce({ stores: [], total: 0 });
    const result = await fetchAvailableBigCommerceStores();
    expect(apiRequestMock).toHaveBeenCalledWith(
      "/integrations/bigcommerce/stores/available",
      { cache: "no-store" },
    );
    expect(result.total).toBe(0);
  });

  it("claimBigCommerceStore POSTs the claim payload", async () => {
    apiRequestMock.mockResolvedValueOnce({
      source_id: "src-1",
      subaccount_id: 42,
      source_name: "My Store",
      store_hash: "abc123",
      catalog_type: "product",
      catalog_variant: "physical_products",
      connection_status: "connected",
      has_token: true,
      token_scopes: null,
      last_connection_check: null,
      last_error: null,
      is_active: true,
      created_at: "2026-04-08T12:00:00Z",
      updated_at: "2026-04-08T12:00:00Z",
    });

    const result = await claimBigCommerceStore(42, {
      store_hash: "abc123",
      source_name: "My Store",
      catalog_type: "product",
      catalog_variant: "physical_products",
    });

    expect(apiRequestMock).toHaveBeenCalledWith(
      "/integrations/bigcommerce/sources/claim?subaccount_id=42",
      {
        method: "POST",
        body: JSON.stringify({
          store_hash: "abc123",
          source_name: "My Store",
          catalog_type: "product",
          catalog_variant: "physical_products",
        }),
      },
    );
    expect(result.source_id).toBe("src-1");
  });

  it("testBigCommerceConnectionByStoreHash returns failure shape on ApiRequestError", async () => {
    const { ApiRequestError } = await import("@/lib/api");
    apiRequestMock.mockRejectedValueOnce(
      new ApiRequestError("Invalid credentials", 401),
    );
    const result = await testBigCommerceConnectionByStoreHash("abc123");
    expect(result.success).toBe(false);
    expect(result.error).toBe("Invalid credentials");
  });

  it("testBigCommerceConnectionByStoreHash returns the success payload as-is", async () => {
    apiRequestMock.mockResolvedValueOnce({
      success: true,
      store_name: "Acme",
      domain: "acme.example.com",
      secure_url: "https://acme.example.com",
      currency: "USD",
      error: null,
    });
    const result = await testBigCommerceConnectionByStoreHash("abc123");
    expect(apiRequestMock).toHaveBeenCalledWith(
      "/integrations/bigcommerce/test-connection",
      {
        method: "POST",
        body: JSON.stringify({ store_hash: "abc123" }),
      },
    );
    expect(result.success).toBe(true);
    expect(result.store_name).toBe("Acme");
  });

  it("testBigCommerceSourceConnection POSTs to the source endpoint", async () => {
    apiRequestMock.mockResolvedValueOnce({
      success: true,
      store_name: "Acme",
      domain: "acme.example.com",
      secure_url: "https://acme.example.com",
      currency: "USD",
      error: null,
    });

    await testBigCommerceSourceConnection(42, "src-1");
    expect(apiRequestMock).toHaveBeenCalledWith(
      "/integrations/bigcommerce/sources/src-1/test-connection?subaccount_id=42",
      { method: "POST" },
    );
  });

  it("listBigCommerceSources hits the scoped endpoint", async () => {
    apiRequestMock.mockResolvedValueOnce([]);
    await listBigCommerceSources(42);
    expect(apiRequestMock).toHaveBeenCalledWith(
      "/integrations/bigcommerce/sources?subaccount_id=42",
      { cache: "no-store" },
    );
  });

  it("updateBigCommerceSource PUTs only the supplied fields", async () => {
    apiRequestMock.mockResolvedValueOnce({
      source_id: "src-1",
      subaccount_id: 42,
      source_name: "Renamed",
      store_hash: "abc123",
      catalog_type: "product",
      catalog_variant: "physical_products",
      connection_status: "connected",
      has_token: true,
      token_scopes: null,
      last_connection_check: null,
      last_error: null,
      is_active: true,
      created_at: "",
      updated_at: "",
    });

    await updateBigCommerceSource(42, "src-1", { source_name: "Renamed" });
    expect(apiRequestMock).toHaveBeenCalledWith(
      "/integrations/bigcommerce/sources/src-1?subaccount_id=42",
      {
        method: "PUT",
        body: JSON.stringify({ source_name: "Renamed" }),
      },
    );
  });

  it("deleteBigCommerceSource DELETEs the source", async () => {
    apiRequestMock.mockResolvedValueOnce({ status: "ok", id: "src-1" });
    await deleteBigCommerceSource(42, "src-1");
    expect(apiRequestMock).toHaveBeenCalledWith(
      "/integrations/bigcommerce/sources/src-1?subaccount_id=42",
      { method: "DELETE" },
    );
  });
});
