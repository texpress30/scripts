"use client";

/**
 * Thin client for the Magento-specific endpoints under
 * ``/integrations/magento/*`` delivered in PR #939. The generic
 * ``useFeedSources`` hook stays focused on the multi-platform
 * ``/subaccount/{id}/feed-sources/*`` CRUD; Magento gets its own helpers
 * because the wizard needs both the pre-save ``test-connection`` call
 * (credentials in body) and a dedicated create endpoint.
 *
 * All functions here are plain ``async`` helpers — callers wrap them in
 * React Query / useState themselves, mirroring how ``createShopifySourceApi``
 * is exposed from ``useFeedSources``.
 */

import { apiRequest, ApiRequestError } from "@/lib/api";

export type MagentoSourceCreateRequest = {
  source_name: string;
  magento_base_url: string;
  magento_store_code: string;
  consumer_key: string;
  consumer_secret: string;
  access_token: string;
  access_token_secret: string;
  catalog_type?: string;
  catalog_variant?: string;
};

export type MagentoSourceResponse = {
  id: string;
  subaccount_id: number;
  source_name: string;
  magento_base_url: string;
  magento_store_code: string;
  catalog_type: string;
  catalog_variant: string;
  connection_status: string;
  has_credentials: boolean;
  consumer_key_masked: string;
  consumer_secret_masked: string;
  access_token_masked: string;
  access_token_secret_masked: string;
  last_connection_check: string | null;
  last_error: string | null;
  created_at: string | null;
  updated_at: string | null;
};

export type MagentoTestConnectionRequest = {
  magento_base_url: string;
  magento_store_code: string;
  consumer_key: string;
  consumer_secret: string;
  access_token: string;
  access_token_secret: string;
};

export type MagentoTestConnectionResponse = {
  success: boolean;
  store_name: string | null;
  base_currency: string | null;
  magento_version: string | null;
  error: string | null;
};

/** Probe Magento credentials BEFORE persisting a source (wizard Step 3). */
export async function testMagentoConnectionBeforeSave(
  payload: MagentoTestConnectionRequest,
): Promise<MagentoTestConnectionResponse> {
  try {
    return await apiRequest<MagentoTestConnectionResponse>(
      "/integrations/magento/test-connection",
      {
        method: "POST",
        body: JSON.stringify(payload),
      },
    );
  } catch (err) {
    if (err instanceof ApiRequestError) {
      return {
        success: false,
        store_name: null,
        base_currency: null,
        magento_version: null,
        error: err.message || `Request failed (${err.status})`,
      };
    }
    throw err;
  }
}

/** Create a new Magento source scoped to ``subaccountId``. */
export async function createMagentoSourceApi(
  subaccountId: number,
  payload: MagentoSourceCreateRequest,
): Promise<MagentoSourceResponse> {
  return apiRequest<MagentoSourceResponse>(
    `/integrations/magento/sources?subaccount_id=${subaccountId}`,
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
  );
}

/** Probe an existing Magento source by id (stored creds). */
export async function testMagentoSourceConnection(
  subaccountId: number,
  sourceId: string,
): Promise<MagentoTestConnectionResponse> {
  try {
    return await apiRequest<MagentoTestConnectionResponse>(
      `/integrations/magento/sources/${sourceId}/test-connection?subaccount_id=${subaccountId}`,
      { method: "POST" },
    );
  } catch (err) {
    if (err instanceof ApiRequestError) {
      return {
        success: false,
        store_name: null,
        base_currency: null,
        magento_version: null,
        error: err.message || `Request failed (${err.status})`,
      };
    }
    throw err;
  }
}
