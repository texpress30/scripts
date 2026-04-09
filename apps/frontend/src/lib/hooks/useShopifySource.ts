"use client";

/**
 * Thin client for the Shopify deferred-claim endpoints under
 * ``/integrations/shopify/*``.
 *
 * The deferred-claim flow mirrors the BigCommerce pattern delivered in
 * PR #942–#948: the merchant installs VOXEL from the Shopify App Store,
 * the OAuth callback fires on our backend, the access token is stored
 * encrypted-at-rest in ``integration_secrets`` keyed by ``shop_domain``
 * — and **no feed_sources row is created yet**. The agency user then
 * comes into the wizard and "claims" one of the installed-but-unbound
 * shops by binding it to a subaccount.
 *
 * This hook exposes the three endpoints the wizard needs:
 *
 * * ``fetchAvailableShopifyStores`` — list installed shops not yet claimed
 * * ``claimShopifyStore`` — bind a shop to a subaccount
 * * ``testShopifyConnectionByShopDomain`` — pre-claim probe
 *
 * Mirrors the plain-async style of ``useBigCommerceSource.ts`` (no
 * React Query) so callers can wrap them in their own ``useState`` /
 * ``useEffect``.
 *
 * Backward compatibility: the legacy ``createShopifySource`` path on
 * ``useFeedSources`` (agency-initiated OAuth) is untouched. That code
 * path still works for merchants who haven't installed the app yet or
 * for edge cases where the App Store install isn't available.
 */

import { apiRequest, ApiRequestError } from "@/lib/api";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type ShopifyAvailableStore = {
  shop_domain: string;
  installed_at: string | null;
  scope: string | null;
};

export type ShopifyAvailableStoresResponse = {
  stores: ShopifyAvailableStore[];
  total: number;
};

export type ShopifyClaimRequest = {
  shop_domain: string;
  source_name: string;
  catalog_type?: string;
  catalog_variant?: string;
};

export type ShopifySourceResponse = {
  source_id: string;
  subaccount_id: number;
  source_name: string;
  shop_domain: string;
  catalog_type: string;
  catalog_variant: string;
  connection_status: string;
  has_token: boolean;
  token_scopes: string | null;
  last_connection_check: string | null;
  last_error: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
};

export type ShopifyPreClaimTestResponse = {
  success: boolean;
  store_name: string | null;
  domain: string | null;
  currency: string | null;
  error: string | null;
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function failedTestResponse(message: string): ShopifyPreClaimTestResponse {
  return {
    success: false,
    store_name: null,
    domain: null,
    currency: null,
    error: message,
  };
}

// ---------------------------------------------------------------------------
// API calls
// ---------------------------------------------------------------------------

/** List the installed Shopify shops that have not yet been claimed. */
export async function fetchAvailableShopifyStores(): Promise<ShopifyAvailableStoresResponse> {
  return apiRequest<ShopifyAvailableStoresResponse>(
    "/integrations/shopify/stores/available",
    { cache: "no-store" },
  );
}

/** Bind an installed Shopify shop to ``subaccountId``. */
export async function claimShopifyStore(
  subaccountId: number,
  payload: ShopifyClaimRequest,
): Promise<ShopifySourceResponse> {
  return apiRequest<ShopifySourceResponse>(
    `/integrations/shopify/sources/claim?subaccount_id=${subaccountId}`,
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
  );
}

/** Probe a Shopify shop BEFORE claiming it (by shop_domain). */
export async function testShopifyConnectionByShopDomain(
  shopDomain: string,
): Promise<ShopifyPreClaimTestResponse> {
  try {
    return await apiRequest<ShopifyPreClaimTestResponse>(
      "/integrations/shopify/test-connection/by-shop",
      {
        method: "POST",
        body: JSON.stringify({ shop_domain: shopDomain }),
      },
    );
  } catch (err) {
    if (err instanceof ApiRequestError) {
      return failedTestResponse(err.message || `Request failed (${err.status})`);
    }
    throw err;
  }
}
