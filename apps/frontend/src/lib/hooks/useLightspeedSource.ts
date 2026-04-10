"use client";

/**
 * Client for the dedicated Lightspeed eCom integration endpoints.
 *
 * Lightspeed connections don't use API credentials — they need
 * Shop ID, Shop Language, and Shop Region instead.  These are
 * non-sensitive metadata stored in the feed source config JSONB.
 */

import { apiRequest, ApiRequestError } from "@/lib/api";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

export const LIGHTSPEED_REGIONS = ["eu1", "us1"] as const;
export type LightspeedRegion = (typeof LIGHTSPEED_REGIONS)[number];

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type LightspeedSourceCreateRequest = {
  source_name: string;
  store_url: string;
  shop_id: string;
  shop_language: string;
  shop_region: string;
  catalog_type?: string;
  catalog_variant?: string;
};

export type LightspeedSourceUpdateRequest = Partial<{
  source_name: string;
  store_url: string;
  shop_id: string;
  shop_language: string;
  shop_region: string;
  catalog_type: string;
  catalog_variant: string;
  is_active: boolean;
}>;

export type LightspeedSourceResponse = {
  source_id: string;
  subaccount_id: number;
  source_name: string;
  platform: "lightspeed";
  store_url: string;
  shop_id: string;
  shop_language: string;
  shop_region: string;
  catalog_type: string;
  catalog_variant: string;
  connection_status: string;
  last_connection_check: string | null;
  last_error: string | null;
  is_active: boolean;
  created_at: string | null;
  updated_at: string | null;
};

export type LightspeedTestConnectionResponse = {
  success: boolean;
  message: string;
  details: Record<string, unknown>;
};

// ---------------------------------------------------------------------------
// API helpers
// ---------------------------------------------------------------------------

function failedTestResponse(
  message: string,
): LightspeedTestConnectionResponse {
  return { success: false, message, details: {} };
}

/** Create a new Lightspeed source. */
export async function createLightspeedSource(
  subaccountId: number,
  payload: LightspeedSourceCreateRequest,
): Promise<LightspeedSourceResponse> {
  return apiRequest<LightspeedSourceResponse>(
    `/integrations/lightspeed/sources?subaccount_id=${subaccountId}`,
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
  );
}

/** List all Lightspeed sources for a subaccount. */
export async function listLightspeedSources(
  subaccountId: number,
): Promise<LightspeedSourceResponse[]> {
  return apiRequest<LightspeedSourceResponse[]>(
    `/integrations/lightspeed/sources?subaccount_id=${subaccountId}`,
    { cache: "no-store" },
  );
}

/** Read a single Lightspeed source. */
export async function getLightspeedSource(
  subaccountId: number,
  sourceId: string,
): Promise<LightspeedSourceResponse> {
  return apiRequest<LightspeedSourceResponse>(
    `/integrations/lightspeed/sources/${sourceId}?subaccount_id=${subaccountId}`,
    { cache: "no-store" },
  );
}

/** Update an existing Lightspeed source. */
export async function updateLightspeedSource(
  subaccountId: number,
  sourceId: string,
  payload: LightspeedSourceUpdateRequest,
): Promise<LightspeedSourceResponse> {
  return apiRequest<LightspeedSourceResponse>(
    `/integrations/lightspeed/sources/${sourceId}?subaccount_id=${subaccountId}`,
    {
      method: "PUT",
      body: JSON.stringify(payload),
    },
  );
}

/** Delete a Lightspeed source. */
export async function deleteLightspeedSource(
  subaccountId: number,
  sourceId: string,
): Promise<{ status: string; id: string }> {
  return apiRequest<{ status: string; id: string }>(
    `/integrations/lightspeed/sources/${sourceId}?subaccount_id=${subaccountId}`,
    { method: "DELETE" },
  );
}

/** Probe the store URL BEFORE saving (wizard pre-save button). */
export async function testLightspeedConnectionPreSave(
  storeUrl: string,
): Promise<LightspeedTestConnectionResponse> {
  try {
    return await apiRequest<LightspeedTestConnectionResponse>(
      `/integrations/lightspeed/test-connection?store_url=${encodeURIComponent(storeUrl)}`,
      { method: "POST" },
    );
  } catch (err) {
    if (err instanceof ApiRequestError) {
      return failedTestResponse(
        err.message || `Request failed (${err.status})`,
      );
    }
    throw err;
  }
}

/** Probe the stored URL on a previously-saved source. */
export async function testLightspeedSourceConnection(
  subaccountId: number,
  sourceId: string,
): Promise<LightspeedTestConnectionResponse> {
  try {
    return await apiRequest<LightspeedTestConnectionResponse>(
      `/integrations/lightspeed/sources/${sourceId}/test-connection?subaccount_id=${subaccountId}`,
      { method: "POST" },
    );
  } catch (err) {
    if (err instanceof ApiRequestError) {
      return failedTestResponse(
        err.message || `Request failed (${err.status})`,
      );
    }
    throw err;
  }
}
