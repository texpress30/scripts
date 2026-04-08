"use client";

/**
 * Thin client for the BigCommerce-specific endpoints under
 * ``/integrations/bigcommerce/*`` delivered in PRs #942–#944.
 *
 * Unlike Magento (where the agency types four OAuth 1.0a credentials into
 * a form), BigCommerce installs flow through the merchant's BigCommerce
 * Marketplace: the merchant clicks "Install" on the Omarosa app, BC fires
 * the OAuth callback on our backend, the access token is stored
 * encrypted-at-rest in ``integration_secrets`` keyed by store hash, and
 * **no feed_sources row is created yet**. The agency user then comes into
 * the wizard and "claims" one of the installed-but-unbound stores by
 * binding it to a subaccount.
 *
 * This hook exposes the four endpoints the wizard needs:
 *
 * * ``fetchAvailableStores`` — list installed stores not yet claimed
 * * ``claimStore`` — bind a store to a subaccount
 * * ``testConnectionByStoreHash`` — pre-claim probe (by store_hash)
 * * ``testConnectionBySource`` — post-claim probe (by source_id)
 *
 * Mirrors the plain-async style of ``useMagentoSource`` (no React Query)
 * so callers can wrap them in their own ``useState`` / ``useEffect``.
 */

import { apiRequest, ApiRequestError } from "@/lib/api";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type BigCommerceAvailableStore = {
  store_hash: string;
  installed_at: string | null;
  user_email: string | null;
  scope: string | null;
};

export type BigCommerceAvailableStoresResponse = {
  stores: BigCommerceAvailableStore[];
  total: number;
};

export type BigCommerceClaimRequest = {
  store_hash: string;
  source_name: string;
  catalog_type?: string;
  catalog_variant?: string;
};

export type BigCommerceSourceResponse = {
  source_id: string;
  subaccount_id: number;
  source_name: string;
  store_hash: string;
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

export type BigCommerceTestConnectionResponse = {
  success: boolean;
  store_name: string | null;
  domain: string | null;
  secure_url: string | null;
  currency: string | null;
  error: string | null;
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function failedTestResponse(message: string): BigCommerceTestConnectionResponse {
  return {
    success: false,
    store_name: null,
    domain: null,
    secure_url: null,
    currency: null,
    error: message,
  };
}

// ---------------------------------------------------------------------------
// API calls
// ---------------------------------------------------------------------------

/** List the installed BigCommerce stores that have not yet been claimed. */
export async function fetchAvailableBigCommerceStores(): Promise<BigCommerceAvailableStoresResponse> {
  return apiRequest<BigCommerceAvailableStoresResponse>(
    "/integrations/bigcommerce/stores/available",
    { cache: "no-store" },
  );
}

/** Bind an installed BigCommerce store to ``subaccountId``. */
export async function claimBigCommerceStore(
  subaccountId: number,
  payload: BigCommerceClaimRequest,
): Promise<BigCommerceSourceResponse> {
  return apiRequest<BigCommerceSourceResponse>(
    `/integrations/bigcommerce/sources/claim?subaccount_id=${subaccountId}`,
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
  );
}

/** Probe a BigCommerce store BEFORE claiming it (by store_hash). */
export async function testBigCommerceConnectionByStoreHash(
  storeHash: string,
): Promise<BigCommerceTestConnectionResponse> {
  try {
    return await apiRequest<BigCommerceTestConnectionResponse>(
      "/integrations/bigcommerce/test-connection",
      {
        method: "POST",
        body: JSON.stringify({ store_hash: storeHash }),
      },
    );
  } catch (err) {
    if (err instanceof ApiRequestError) {
      return failedTestResponse(err.message || `Request failed (${err.status})`);
    }
    throw err;
  }
}

/** Probe a previously-claimed BigCommerce source by id (uses stored creds). */
export async function testBigCommerceSourceConnection(
  subaccountId: number,
  sourceId: string,
): Promise<BigCommerceTestConnectionResponse> {
  try {
    return await apiRequest<BigCommerceTestConnectionResponse>(
      `/integrations/bigcommerce/sources/${sourceId}/test-connection?subaccount_id=${subaccountId}`,
      { method: "POST" },
    );
  } catch (err) {
    if (err instanceof ApiRequestError) {
      return failedTestResponse(err.message || `Request failed (${err.status})`);
    }
    throw err;
  }
}

/** List every BigCommerce source bound to ``subaccountId``. */
export async function listBigCommerceSources(
  subaccountId: number,
): Promise<BigCommerceSourceResponse[]> {
  return apiRequest<BigCommerceSourceResponse[]>(
    `/integrations/bigcommerce/sources?subaccount_id=${subaccountId}`,
    { cache: "no-store" },
  );
}

/** Patch the cosmetic fields of an existing BigCommerce source. */
export async function updateBigCommerceSource(
  subaccountId: number,
  sourceId: string,
  payload: Partial<{
    source_name: string;
    catalog_type: string;
    catalog_variant: string;
    is_active: boolean;
  }>,
): Promise<BigCommerceSourceResponse> {
  return apiRequest<BigCommerceSourceResponse>(
    `/integrations/bigcommerce/sources/${sourceId}?subaccount_id=${subaccountId}`,
    {
      method: "PUT",
      body: JSON.stringify(payload),
    },
  );
}

/** Delete a BigCommerce source row. The encrypted credentials are NOT touched
 *  — the merchant must uninstall the app from the BigCommerce control panel
 *  to wipe them. */
export async function deleteBigCommerceSource(
  subaccountId: number,
  sourceId: string,
): Promise<{ status: string; id: string }> {
  return apiRequest<{ status: string; id: string }>(
    `/integrations/bigcommerce/sources/${sourceId}?subaccount_id=${subaccountId}`,
    { method: "DELETE" },
  );
}
