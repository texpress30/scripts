"use client";

/**
 * Thin client for the generic-API-key e-commerce platform endpoints.
 *
 * Six platforms share the same parametrised CRUD shape on the backend
 * (PrestaShop, OpenCart, Shopware, Lightspeed, Volusion, Cart Storefront).
 * This module exposes one set of plain async helpers that take
 * ``platform`` as the first argument so callers don't have to maintain
 * six near-identical hooks.
 *
 * Mirrors the style of ``useMagentoSource.ts`` (no React Query) so the
 * wizard can wrap them in its own ``useState`` / ``useEffect``.
 */

import { apiRequest, ApiRequestError } from "@/lib/api";

// ---------------------------------------------------------------------------
// Platform metadata (kept in lockstep with backend
// ``app/integrations/generic_api_key/config.py::PLATFORM_DEFINITIONS``)
// ---------------------------------------------------------------------------

export type GenericApiKeyPlatformKey =
  | "prestashop"
  | "opencart"
  | "volusion"
  | "cart_storefront"
  | "gomag"
  | "contentspeed";

export type GenericApiKeyPlatformDefinition = {
  key: GenericApiKeyPlatformKey;
  displayName: string;
  apiKeyLabel: string;
  apiSecretLabel?: string;
  hasApiSecret: boolean;
  apiKeyPlaceholder: string;
  apiSecretPlaceholder?: string;
  // Inline help text shown beneath the form (where to find the credentials).
  helpText: string;
};

export const GENERIC_API_KEY_PLATFORMS: Record<
  GenericApiKeyPlatformKey,
  GenericApiKeyPlatformDefinition
> = {
  prestashop: {
    key: "prestashop",
    displayName: "PrestaShop",
    apiKeyLabel: "Authorization Token",
    hasApiSecret: false,
    apiKeyPlaceholder: "ex: your-prestashop-token",
    helpText:
      "Solicită clientului Authorization Token-ul din PrestaShop. Clientul trebuie să instaleze modulul conector în PrestaShop Admin → Modules → Module Manager, apoi să-l configureze. Token-ul se găsește în pagina de configurare a modulului.",
  },
  opencart: {
    key: "opencart",
    displayName: "OpenCart",
    apiKeyLabel: "Store Key",
    hasApiSecret: false,
    apiKeyPlaceholder: "ex: your-opencart-store-key",
    helpText:
      "Solicită clientului Store Key-ul din OpenCart. Clientul trebuie să instaleze conectorul în OpenCart Admin → Extensions → Extension Installer, apoi să-l activeze din Extensions → Modules. Store Key-ul apare în pagina de editare a conectorului.",
  },
  volusion: {
    key: "volusion",
    displayName: "Volusion",
    apiKeyLabel: "API Login",
    apiSecretLabel: "API Encrypted Password",
    hasApiSecret: true,
    apiKeyPlaceholder: "ex: your-api-login",
    apiSecretPlaceholder: "ex: your-encrypted-password",
    helpText:
      "Solicită clientului API Login și Encrypted Password din Volusion Admin → Inventory → Import/Export → Volusion API. Clientul trebuie să activeze 'Enable public XML for Featured Products' și 'Enable Public XML for All Products', apoi din Get Help → Volusion API Integration Help → Generic Products → Query String, copiază API Login și Encrypted Password.",
  },
  cart_storefront: {
    key: "cart_storefront",
    displayName: "Cart Storefront",
    apiKeyLabel: "Authorization Token",
    hasApiSecret: false,
    apiKeyPlaceholder: "ex: your-authorization-token",
    helpText:
      "Solicită clientului tokenul din Cart.com Admin → Tools → Apps & Addons → API Token Manager. Clientul trebuie să creeze o aplicație cu Authentication Flow: Single Token Flow, cu permisiuni Catalog Permissions → View catalog data. Apoi din API Token Manager → Access Tokens, copiază tokenul generat.",
  },
  gomag: {
    key: "gomag",
    displayName: "GoMag",
    apiKeyLabel: "API Key",
    hasApiSecret: false,
    apiKeyPlaceholder: "ex: your-gomag-api-key",
    helpText:
      "Solicită clientului API Key-ul din panoul de administrare GoMag.",
  },
  contentspeed: {
    key: "contentspeed",
    displayName: "ContentSpeed",
    apiKeyLabel: "API Key",
    hasApiSecret: false,
    apiKeyPlaceholder: "ex: your-contentspeed-api-key",
    helpText:
      "Solicită clientului API Key-ul din panoul de administrare ContentSpeed.",
  },
};

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type GenericApiKeySourceCreateRequest = {
  source_name: string;
  store_url: string;
  api_key: string;
  api_secret?: string;
  catalog_type?: string;
  catalog_variant?: string;
};

export type GenericApiKeySourceUpdateRequest = Partial<{
  source_name: string;
  store_url: string;
  api_key: string;
  api_secret: string;
  catalog_type: string;
  catalog_variant: string;
  is_active: boolean;
}>;

export type GenericApiKeySourceResponse = {
  source_id: string;
  subaccount_id: number;
  source_name: string;
  platform: GenericApiKeyPlatformKey;
  store_url: string;
  catalog_type: string;
  catalog_variant: string;
  has_credentials: boolean;
  api_key_masked: string | null;
  api_secret_masked: string | null;
  connection_status: string;
  last_connection_check: string | null;
  last_error: string | null;
  is_active: boolean;
  created_at: string | null;
  updated_at: string | null;
};

export type GenericApiKeyTestConnectionResponse = {
  success: boolean;
  message: string;
  details: Record<string, unknown>;
};

// ---------------------------------------------------------------------------
// API helpers
// ---------------------------------------------------------------------------

function failedTestResponse(message: string): GenericApiKeyTestConnectionResponse {
  return { success: false, message, details: {} };
}

/** Create a new source for a generic-API-key platform. */
export async function createGenericApiKeySource(
  platform: GenericApiKeyPlatformKey,
  subaccountId: number,
  payload: GenericApiKeySourceCreateRequest,
): Promise<GenericApiKeySourceResponse> {
  return apiRequest<GenericApiKeySourceResponse>(
    `/integrations/${platform}/sources?subaccount_id=${subaccountId}`,
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
  );
}

/** List every source for a generic-API-key platform on the given subaccount. */
export async function listGenericApiKeySources(
  platform: GenericApiKeyPlatformKey,
  subaccountId: number,
): Promise<GenericApiKeySourceResponse[]> {
  return apiRequest<GenericApiKeySourceResponse[]>(
    `/integrations/${platform}/sources?subaccount_id=${subaccountId}`,
    { cache: "no-store" },
  );
}

/** Read a single source. */
export async function getGenericApiKeySource(
  platform: GenericApiKeyPlatformKey,
  subaccountId: number,
  sourceId: string,
): Promise<GenericApiKeySourceResponse> {
  return apiRequest<GenericApiKeySourceResponse>(
    `/integrations/${platform}/sources/${sourceId}?subaccount_id=${subaccountId}`,
    { cache: "no-store" },
  );
}

/** Patch the cosmetic / credential fields of an existing source. */
export async function updateGenericApiKeySource(
  platform: GenericApiKeyPlatformKey,
  subaccountId: number,
  sourceId: string,
  payload: GenericApiKeySourceUpdateRequest,
): Promise<GenericApiKeySourceResponse> {
  return apiRequest<GenericApiKeySourceResponse>(
    `/integrations/${platform}/sources/${sourceId}?subaccount_id=${subaccountId}`,
    {
      method: "PUT",
      body: JSON.stringify(payload),
    },
  );
}

/** Delete a source row + wipe its encrypted credentials. */
export async function deleteGenericApiKeySource(
  platform: GenericApiKeyPlatformKey,
  subaccountId: number,
  sourceId: string,
): Promise<{ status: string; id: string }> {
  return apiRequest<{ status: string; id: string }>(
    `/integrations/${platform}/sources/${sourceId}?subaccount_id=${subaccountId}`,
    { method: "DELETE" },
  );
}

/** Probe the store URL BEFORE saving the source (wizard pre-claim button). */
export async function testGenericApiKeyConnectionPreSave(
  platform: GenericApiKeyPlatformKey,
  storeUrl: string,
): Promise<GenericApiKeyTestConnectionResponse> {
  try {
    return await apiRequest<GenericApiKeyTestConnectionResponse>(
      `/integrations/${platform}/test-connection?store_url=${encodeURIComponent(storeUrl)}`,
      { method: "POST" },
    );
  } catch (err) {
    if (err instanceof ApiRequestError) {
      return failedTestResponse(err.message || `Request failed (${err.status})`);
    }
    throw err;
  }
}

/** Probe the stored URL on a previously-saved source. */
export async function testGenericApiKeySourceConnection(
  platform: GenericApiKeyPlatformKey,
  subaccountId: number,
  sourceId: string,
): Promise<GenericApiKeyTestConnectionResponse> {
  try {
    return await apiRequest<GenericApiKeyTestConnectionResponse>(
      `/integrations/${platform}/sources/${sourceId}/test-connection?subaccount_id=${subaccountId}`,
      { method: "POST" },
    );
  } catch (err) {
    if (err instanceof ApiRequestError) {
      return failedTestResponse(err.message || `Request failed (${err.status})`);
    }
    throw err;
  }
}
