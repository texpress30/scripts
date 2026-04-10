"use client";

/**
 * Client for the dedicated Shopware integration endpoints.
 *
 * Shopware connections need Store Key, Bridge Endpoint, and API Access
 * Key — three fields from the Shopware connector extension.
 */

import { apiRequest, ApiRequestError } from "@/lib/api";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type ShopwareSourceCreateRequest = {
  source_name: string;
  store_url: string;
  store_key: string;
  bridge_endpoint: string;
  api_access_key: string;
  catalog_type?: string;
  catalog_variant?: string;
};

export type ShopwareSourceUpdateRequest = Partial<{
  source_name: string;
  store_url: string;
  store_key: string;
  bridge_endpoint: string;
  api_access_key: string;
  catalog_type: string;
  catalog_variant: string;
  is_active: boolean;
}>;

export type ShopwareSourceResponse = {
  source_id: string;
  subaccount_id: number;
  source_name: string;
  platform: "shopware";
  store_url: string;
  bridge_endpoint: string;
  has_credentials: boolean;
  store_key_masked: string | null;
  api_access_key_masked: string | null;
  catalog_type: string;
  catalog_variant: string;
  connection_status: string;
  last_connection_check: string | null;
  last_error: string | null;
  is_active: boolean;
  created_at: string | null;
  updated_at: string | null;
};

export type ShopwareTestConnectionResponse = {
  success: boolean;
  message: string;
  details: Record<string, unknown>;
};

// ---------------------------------------------------------------------------
// API helpers
// ---------------------------------------------------------------------------

function failedTestResponse(message: string): ShopwareTestConnectionResponse {
  return { success: false, message, details: {} };
}

export async function createShopwareSource(
  subaccountId: number,
  payload: ShopwareSourceCreateRequest,
): Promise<ShopwareSourceResponse> {
  return apiRequest<ShopwareSourceResponse>(
    `/integrations/shopware/sources?subaccount_id=${subaccountId}`,
    { method: "POST", body: JSON.stringify(payload) },
  );
}

export async function listShopwareSources(
  subaccountId: number,
): Promise<ShopwareSourceResponse[]> {
  return apiRequest<ShopwareSourceResponse[]>(
    `/integrations/shopware/sources?subaccount_id=${subaccountId}`,
    { cache: "no-store" },
  );
}

export async function getShopwareSource(
  subaccountId: number,
  sourceId: string,
): Promise<ShopwareSourceResponse> {
  return apiRequest<ShopwareSourceResponse>(
    `/integrations/shopware/sources/${sourceId}?subaccount_id=${subaccountId}`,
    { cache: "no-store" },
  );
}

export async function updateShopwareSource(
  subaccountId: number,
  sourceId: string,
  payload: ShopwareSourceUpdateRequest,
): Promise<ShopwareSourceResponse> {
  return apiRequest<ShopwareSourceResponse>(
    `/integrations/shopware/sources/${sourceId}?subaccount_id=${subaccountId}`,
    { method: "PUT", body: JSON.stringify(payload) },
  );
}

export async function deleteShopwareSource(
  subaccountId: number,
  sourceId: string,
): Promise<{ status: string; id: string }> {
  return apiRequest<{ status: string; id: string }>(
    `/integrations/shopware/sources/${sourceId}?subaccount_id=${subaccountId}`,
    { method: "DELETE" },
  );
}

export async function testShopwareConnectionPreSave(
  storeUrl: string,
): Promise<ShopwareTestConnectionResponse> {
  try {
    return await apiRequest<ShopwareTestConnectionResponse>(
      `/integrations/shopware/test-connection?store_url=${encodeURIComponent(storeUrl)}`,
      { method: "POST" },
    );
  } catch (err) {
    if (err instanceof ApiRequestError) {
      return failedTestResponse(err.message || `Request failed (${err.status})`);
    }
    throw err;
  }
}

export async function testShopwareSourceConnection(
  subaccountId: number,
  sourceId: string,
): Promise<ShopwareTestConnectionResponse> {
  try {
    return await apiRequest<ShopwareTestConnectionResponse>(
      `/integrations/shopware/sources/${sourceId}/test-connection?subaccount_id=${subaccountId}`,
      { method: "POST" },
    );
  } catch (err) {
    if (err instanceof ApiRequestError) {
      return failedTestResponse(err.message || `Request failed (${err.status})`);
    }
    throw err;
  }
}
