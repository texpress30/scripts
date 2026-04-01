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

// ── Products ──

export type ProductVariant = {
  sku: string;
  title: string;
  price: number;
  compare_at_price: number | null;
  inventory_quantity: number;
};

export type Product = {
  id: string;
  title: string;
  description: string;
  price: number;
  compare_at_price: number | null;
  currency: string;
  images: string[];
  variants: ProductVariant[];
  category: string;
  tags: string[];
  inventory_quantity: number;
  sku: string;
  url: string;
};

export type ProductsListResponse = {
  items: Product[];
  total: number;
  skip: number;
  limit: number;
};

export type ProductStats = {
  total: number;
  by_category: Record<string, number>;
  last_sync: string | null;
};
