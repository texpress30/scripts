export type FeedSourceType =
  | "shopify"
  | "woocommerce"
  | "magento"
  | "bigcommerce"
  | "csv"
  | "json"
  | "xml"
  | "google_sheets";

export type FeedSourceStatus = "active" | "syncing" | "error" | "inactive";

export type FeedSource = {
  id: number;
  name: string;
  source_type: FeedSourceType;
  catalog_type: CatalogType;
  status: FeedSourceStatus;
  last_sync: string | null;
  product_count: number;
  url?: string;
  created_at: string;
  updated_at: string;
};

export type FeedSourcesResponse = {
  items: FeedSource[];
  total: number;
};

export type FeedImportStatus = "pending" | "running" | "completed" | "failed";

export type FeedImport = {
  id: number;
  source_id: number;
  source_name: string;
  status: FeedImportStatus;
  products_imported: number;
  products_updated: number;
  products_failed: number;
  started_at: string;
  completed_at: string | null;
  error_message: string | null;
};

export type FeedImportsResponse = {
  items: FeedImport[];
  total: number;
};

export type CreateFeedSourcePayload = {
  name: string;
  source_type: FeedSourceType;
  catalog_type: CatalogType;
  url?: string;
  config?: Record<string, string>;
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
  | "media";

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
  id: number;
  target_field: string;
  source_field: string | null;
  transformation: TransformationType;
  config: Record<string, string>;
  preview_value?: string;
};

export type FieldMapping = {
  id: number;
  source_id: number;
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
  source_id: number;
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
