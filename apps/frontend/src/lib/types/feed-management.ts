export type FeedSourceType =
  | "shopify"
  | "woocommerce"
  | "magento"
  | "bigcommerce"
  | "prestashop"
  | "opencart"
  | "shopware"
  | "lightspeed"
  | "volusion"
  | "cart_storefront"
  | "csv"
  | "json"
  | "xml"
  | "google_sheets";

export type FeedSourceStatus = "active" | "syncing" | "error" | "inactive";

export type FeedConnectionStatus = "connected" | "pending" | "error" | "disconnected";

export type SyncSchedule = "manual" | "hourly" | "every_6h" | "every_12h" | "daily" | "weekly";

export type FeedSource = {
  id: string;
  name: string;
  source_type: FeedSourceType;
  catalog_type: CatalogType;
  status: FeedSourceStatus;
  last_sync: string | null;
  product_count: number;
  url?: string;
  config?: Record<string, unknown>;
  credentials_secret_id?: string | null;
  is_active?: boolean;
  subaccount_id?: number;
  shop_domain?: string | null;
  connection_status?: FeedConnectionStatus;
  last_connection_check?: string | null;
  last_error?: string | null;
  has_token?: boolean;
  // Optional HTTP Basic Auth metadata for file sources (CSV / JSON / XML).
  // Populated by the backend from ``integration_secrets`` — the password
  // itself is never exposed; only ``file_auth_password_masked`` (e.g.
  // ``"****"``) comes back for display.
  has_file_auth?: boolean;
  file_auth_username?: string | null;
  file_auth_password_masked?: string | null;
  last_import_at?: string | null;
  sync_schedule?: SyncSchedule;
  next_scheduled_sync?: string | null;
  created_at: string;
  updated_at: string;
};

export type CreateShopifySourceResponse = {
  source: FeedSource;
  authorize_url: string | null;
  state: string | null;
};

export type ShopifyImportResult = {
  import_id: string;
  status: string;
  total: number;
  imported: number;
  deactivated: number;
  errors: unknown[];
  message: string;
};

export type ShopifyReconnectResult = {
  authorize_url: string;
  state: string;
  source_id: string;
};

export type FeedSourcesResponse = {
  items: FeedSource[];
  total: number;
};

export type FeedImportStatus = "pending" | "running" | "in_progress" | "completed" | "failed";

export type FeedImport = {
  id: string;
  source_id?: string;
  feed_source_id?: string;
  source_name?: string;
  status: FeedImportStatus;
  total_products?: number;
  imported_products?: number;
  products_imported?: number;
  products_updated?: number;
  products_failed?: number;
  errors?: unknown[];
  started_at: string | null;
  completed_at: string | null;
  created_at?: string;
  error_message?: string | null;
};

export type FeedImportsResponse = {
  items: FeedImport[];
  total: number;
};

export type CreateFeedSourcePayload = {
  name: string;
  source_type: FeedSourceType;
  catalog_type: CatalogType;
  catalog_variant?: string;
  url?: string;
  shop_domain?: string;
  config?: Record<string, string>;
  // Optional HTTP Basic Auth for file sources (CSV / JSON / XML).
  // Absent or empty for every other source type.
  feed_auth_username?: string;
  feed_auth_password?: string;
};

export type TestConnectionPayload = {
  source_type: FeedSourceType;
  url: string;
  config?: Record<string, string>;
};

export type TestConnectionResponse = {
  success: boolean;
  message: string;
};

// --- Catalog Types ---

export type CatalogType =
  | "product"
  | "vehicle"
  | "home_listing"
  | "hotel"
  | "flight"
  | "media"
  | "destination"
  | "service";

export type CatalogFieldType = "string" | "number" | "boolean" | "url" | "currency" | "date" | "enum" | "array";

export type CatalogField = {
  key: string;
  label: string;
  type: CatalogFieldType;
  description: string;
  required: boolean;
  enum_values?: string[];
};

export type CatalogSchema = {
  catalog_type: CatalogType;
  label: string;
  description: string;
  fields: CatalogField[];
};

// --- Field Mapping ---

export type TransformationType =
  | "direct"
  | "template"
  | "conditional"
  | "truncate"
  | "replace"
  | "static"
  | "concatenate"
  | "lowercase"
  | "uppercase";

export type FieldMappingRule = {
  id: string | number;
  target_field: string;
  source_field: string | null;
  transformation: TransformationType;
  config: Record<string, string>;
  preview_value?: string;
};

export type FieldMapping = {
  id: string | number;
  source_id: string | number;
  source_name: string;
  catalog_type: CatalogType;
  rules: FieldMappingRule[];
  created_at: string;
  updated_at: string;
};

export type FieldMappingsResponse = {
  items: FieldMapping[];
  total: number;
};

export type CreateFieldMappingPayload = {
  source_id: string | number;
};

export type UpdateMappingRulePayload = {
  target_field: string;
  source_field: string | null;
  transformation: TransformationType;
  config: Record<string, string>;
};

export type FieldMappingPreviewRow = {
  product_name: string;
  source_value: string;
  transformed_value: string;
  error?: string;
};
