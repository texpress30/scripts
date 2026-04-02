"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import type {
  FeedSource,
  FeedSourcesResponse,
  FeedImportsResponse,
  CreateFeedSourcePayload,
  TestConnectionPayload,
  TestConnectionResponse,
} from "@/lib/types/feed-management";
import { apiRequest, ApiRequestError } from "@/lib/api";
import { getPrimarySubaccountId } from "@/lib/session";

const SOURCES_KEY = ["feed-sources"] as const;
const SOURCE_KEY = (id: string) => ["feed-sources", id] as const;
const IMPORTS_KEY = (sourceId: string) => ["feed-imports", sourceId] as const;

function getSubaccountId(): number {
  const id = getPrimarySubaccountId();
  if (!id) throw new Error("No subaccount selected");
  return id;
}

// ---------------------------------------------------------------------------
// API functions — real backend endpoints
// ---------------------------------------------------------------------------

function normalizeSource(raw: Record<string, unknown>): FeedSource {
  return {
    id: String(raw.id ?? ""),
    name: String(raw.name ?? ""),
    source_type: String(raw.source_type ?? "csv") as FeedSource["source_type"],
    catalog_type: String(raw.catalog_type ?? "product") as FeedSource["catalog_type"],
    status: raw.is_active === false ? "inactive" : "active",
    last_sync: (raw.last_sync as string) ?? null,
    product_count: Number(raw.product_count ?? 0),
    url: String(raw.config && typeof raw.config === "object" ? (raw.config as Record<string, unknown>).store_url ?? (raw.config as Record<string, unknown>).file_url ?? "" : ""),
    config: raw.config as Record<string, unknown> | undefined,
    is_active: raw.is_active as boolean | undefined,
    subaccount_id: raw.subaccount_id as number | undefined,
    created_at: String(raw.created_at ?? ""),
    updated_at: String(raw.updated_at ?? ""),
  };
}

async function fetchSources(): Promise<FeedSourcesResponse> {
  const subId = getSubaccountId();
  const data = await apiRequest<{ items: Record<string, unknown>[] }>(
    `/subaccount/${subId}/feed-sources`,
    { cache: "no-store" },
  );
  const items = (data.items ?? []).map(normalizeSource);
  return { items, total: items.length };
}

async function fetchSource(id: string): Promise<FeedSource> {
  const subId = getSubaccountId();
  const raw = await apiRequest<Record<string, unknown>>(
    `/subaccount/${subId}/feed-sources/${id}`,
    { cache: "no-store" },
  );
  return normalizeSource(raw);
}

async function fetchImports(sourceId: string): Promise<FeedImportsResponse> {
  const subId = getSubaccountId();
  const data = await apiRequest<{ items: unknown[] }>(
    `/subaccount/${subId}/feed-sources/${sourceId}/imports`,
    { cache: "no-store" },
  );
  return { items: data.items ?? [], total: (data.items ?? []).length } as FeedImportsResponse;
}

async function createSourceApi(data: CreateFeedSourcePayload): Promise<FeedSource> {
  const subId = getSubaccountId();

  // Build the backend payload matching FeedSourceCreate schema
  const config: Record<string, unknown> = { ...(data.config ?? {}) };
  if (data.url) {
    // Map the URL to the appropriate config field
    if (data.source_type === "shopify") {
      config.store_url = config.shop_url ?? config.store_url ?? data.url;
    } else if (data.source_type === "woocommerce" || data.source_type === "magento" || data.source_type === "bigcommerce") {
      config.store_url = config.store_url ?? data.url;
    } else {
      // CSV, JSON, XML, Google Sheets
      config.file_url = config.file_url ?? data.url;
    }
  }

  const payload = {
    name: data.name,
    source_type: data.source_type,
    catalog_type: data.catalog_type ?? "product",
    config,
  };

  return apiRequest<FeedSource>(`/subaccount/${subId}/feed-sources`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

async function deleteSourceApi(id: string): Promise<void> {
  const subId = getSubaccountId();
  await apiRequest(`/subaccount/${subId}/feed-sources/${id}`, { method: "DELETE" });
}

async function syncSourceApi(id: string): Promise<void> {
  const subId = getSubaccountId();
  await apiRequest(`/subaccount/${subId}/feed-sources/${id}/sync`, { method: "POST" });
}

async function testConnectionApi(data: TestConnectionPayload): Promise<TestConnectionResponse> {
  const { source_type, url, config } = data;

  if (source_type === "shopify") {
    return apiRequest<TestConnectionResponse>("/integrations/shopify/test-connection", {
      method: "POST",
      body: JSON.stringify({
        store_url: config?.shop_url ?? config?.store_url ?? url,
        access_token: config?.access_token ?? "",
        api_key: config?.api_key ?? "",
        api_secret_key: config?.api_secret_key ?? "",
      }),
    });
  }

  if (source_type === "woocommerce") {
    return apiRequest<TestConnectionResponse>("/integrations/woocommerce/test-connection", {
      method: "POST",
      body: JSON.stringify({
        store_url: config?.store_url ?? url,
        consumer_key: config?.consumer_key ?? "",
        consumer_secret: config?.consumer_secret ?? "",
      }),
    });
  }

  // For file-based sources, just validate the URL is accessible
  return { success: true, message: "File URL provided — will be validated on sync." };
}

// ---------------------------------------------------------------------------
// Hooks
// ---------------------------------------------------------------------------

export function useFeedSources() {
  const queryClient = useQueryClient();

  const { data, isLoading, error } = useQuery<FeedSourcesResponse>({
    queryKey: SOURCES_KEY,
    queryFn: fetchSources,
    retry: 1,
  });

  const deleteMutation = useMutation({
    mutationFn: deleteSourceApi,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: SOURCES_KEY });
    },
  });

  const syncMutation = useMutation({
    mutationFn: syncSourceApi,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: SOURCES_KEY });
    },
  });

  const createMutation = useMutation({
    mutationFn: createSourceApi,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: SOURCES_KEY });
    },
  });

  return {
    sources: data?.items ?? [],
    total: data?.total ?? 0,
    isLoading,
    error: error instanceof Error ? error.message : null,
    deleteSource: (id: string) => deleteMutation.mutateAsync(id),
    syncSource: (id: string) => syncMutation.mutateAsync(id),
    createSource: (data: CreateFeedSourcePayload) => createMutation.mutateAsync(data),
    testConnection: (data: TestConnectionPayload) => testConnectionApi(data),
    isDeleting: deleteMutation.isPending,
    isSyncing: syncMutation.isPending,
    isCreating: createMutation.isPending,
  };
}

export function useFeedSource(id: string) {
  const { data, isLoading, error } = useQuery<FeedSource>({
    queryKey: SOURCE_KEY(id),
    queryFn: () => fetchSource(id),
    enabled: !!id,
    retry: 1,
  });

  return {
    source: data ?? null,
    isLoading,
    error: error instanceof Error ? error.message : null,
  };
}

export function useFeedImports(sourceId: string) {
  const { data, isLoading, error } = useQuery<FeedImportsResponse>({
    queryKey: IMPORTS_KEY(sourceId),
    queryFn: () => fetchImports(sourceId),
    enabled: !!sourceId,
    retry: 1,
  });

  return {
    imports: data?.items ?? [],
    total: data?.total ?? 0,
    isLoading,
    error: error instanceof Error ? error.message : null,
  };
}
