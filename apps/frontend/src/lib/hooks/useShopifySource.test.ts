import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  claimShopifyStore,
  fetchAvailableShopifyStores,
  testShopifyConnectionByShopDomain,
} from "./useShopifySource";

const apiRequestMock = vi.fn();

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    apiRequest: (...args: unknown[]) => apiRequestMock(...args),
  };
});

describe("useShopifySource", () => {
  beforeEach(() => {
    apiRequestMock.mockReset();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("fetchAvailableShopifyStores hits the right endpoint", async () => {
    apiRequestMock.mockResolvedValueOnce({ stores: [], total: 0 });
    const result = await fetchAvailableShopifyStores();
    expect(apiRequestMock).toHaveBeenCalledWith(
      "/integrations/shopify/stores/available",
      { cache: "no-store" },
    );
    expect(result.total).toBe(0);
  });

  it("claimShopifyStore POSTs the claim payload", async () => {
    apiRequestMock.mockResolvedValueOnce({
      source_id: "src-1",
      subaccount_id: 42,
      source_name: "My Store",
      shop_domain: "my-store.myshopify.com",
      catalog_type: "product",
      catalog_variant: "physical_products",
      connection_status: "connected",
      has_token: true,
      token_scopes: null,
      last_connection_check: null,
      last_error: null,
      is_active: true,
      created_at: "2026-04-09T12:00:00Z",
      updated_at: "2026-04-09T12:00:00Z",
    });

    const result = await claimShopifyStore(42, {
      shop_domain: "my-store.myshopify.com",
      source_name: "My Store",
      catalog_type: "product",
      catalog_variant: "physical_products",
    });

    expect(apiRequestMock).toHaveBeenCalledWith(
      "/integrations/shopify/sources/claim?subaccount_id=42",
      {
        method: "POST",
        body: JSON.stringify({
          shop_domain: "my-store.myshopify.com",
          source_name: "My Store",
          catalog_type: "product",
          catalog_variant: "physical_products",
        }),
      },
    );
    expect(result.source_id).toBe("src-1");
    expect(result.shop_domain).toBe("my-store.myshopify.com");
  });

  it("testShopifyConnectionByShopDomain returns failure shape on ApiRequestError", async () => {
    const { ApiRequestError } = await import("@/lib/api");
    apiRequestMock.mockRejectedValueOnce(
      new ApiRequestError("Invalid token", 401),
    );
    const result = await testShopifyConnectionByShopDomain(
      "my-store.myshopify.com",
    );
    expect(result.success).toBe(false);
    expect(result.error).toBe("Invalid token");
  });

  it("testShopifyConnectionByShopDomain returns the success payload as-is", async () => {
    apiRequestMock.mockResolvedValueOnce({
      success: true,
      store_name: "My Store",
      domain: "my-store.myshopify.com",
      currency: "USD",
      error: null,
    });
    const result = await testShopifyConnectionByShopDomain(
      "my-store.myshopify.com",
    );
    expect(apiRequestMock).toHaveBeenCalledWith(
      "/integrations/shopify/test-connection/by-shop",
      {
        method: "POST",
        body: JSON.stringify({ shop_domain: "my-store.myshopify.com" }),
      },
    );
    expect(result.success).toBe(true);
    expect(result.store_name).toBe("My Store");
    expect(result.currency).toBe("USD");
  });
});
