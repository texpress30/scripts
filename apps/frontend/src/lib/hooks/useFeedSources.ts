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
import { apiRequest } from "@/lib/api";

const SOURCES_KEY = (subId: number) => ["feed-sources", subId] as const;
const SOURCE_KEY = (subId: number, id: string) => ["feed-sources", subId, id] as const;
const IMPORTS_KEY = (subId: number, sourceId: string) => ["feed-imports", subId, sourceId] as const;

// ---------------------------------------------------------------------------
// Normalize backend response to frontend FeedSource
// ---------------------------------------------------------------------------

function normalizeSource(raw: Record<string, unknown>): FeedSource {
  return {
    id: String(raw.id ?? ""),
    name: String(raw.name ?? ""),
    source_type: String(raw.source_type ?? "csv") as FeedSource["source_type"],
    catalog_type: String(raw.catalog_type ?? "product") as FeedSource["catalog_type"],
    status: raw.is_active === false ? "inactive" : "active",
    last_sync: (raw.last_sync_at as string) ?? (raw.last_sync as string) ?? null,
    product_count: Number(raw.product_count ?? 0),
    url: String(raw.config && typeof raw.config === "object" ? (raw.config as Record<string, unknown>).store_url ?? (raw.config as Record<string, unknown>).file_url ?? "" : ""),
    config: raw.config as Record<string, unknown> | undefined,
    is_active: raw.is_active as boolean | undefined,
    subaccount_id: raw.subaccount_id as number | undefined,
    sync_schedule: (raw.sync_schedule as FeedSource["sync_schedule"]) ?? "manual",
    next_scheduled_sync: (raw.next_scheduled_sync as string) ?? null,
    created_at: String(raw.created_at ?? ""),
    updated_at: String(raw.updated_at ?? ""),
  };
}

// ---------------------------------------------------------------------------
// API functions (all require subaccountId)
// ---------------------------------------------------------------------------

async function fetchSources(subId: number): Promise<FeedSourcesResponse> {
  const data = await apiRequest<{ items: Record<string, unknown>[] }>(
    `/subaccount/${subId}/feed-sources`,
    { cache: "no-store" },
  );
  const items = (data.items ?? []).map(normalizeSource);
  return { items, total: items.length };
}

async function fetchSource(subId: number, id: string): Promise<FeedSource> {
  const raw = await apiRequest<Record<string, unknown>>(
    `/subaccount/${subId}/feed-sources/${id}`,
    { cache: "no-store" },
  );
  return normalizeSource(raw);
}

async function fetchImports(subId: number, sourceId: string): Promise<FeedImportsResponse> {
  const data = await apiRequest<{ items: unknown[] }>(
    `/subaccount/${subId}/feed-sources/${sourceId}/imports`,
    { cache: "no-store" },
  );
  return { items: data.items ?? [], total: (data.items ?? []).length } as FeedImportsResponse;
}

async function createSourceApi(subId: number, data: CreateFeedSourcePayload): Promise<FeedSource> {
  const config: Record<string, unknown> = { ...(data.config ?? {}) };
  if (data.url) {
    if (data.source_type === "shopify") {
      config.store_url = config.shop_url ?? config.store_url ?? data.url;
    } else if (data.source_type === "woocommerce" || data.source_type === "magento" || data.source_type === "bigcommerce") {
      config.store_url = config.store_url ?? data.url;
    } else {
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

async function deleteSourceApi(subId: number, id: string): Promise<void> {
  await apiRequest(`/subaccount/${subId}/feed-sources/${id}`, { method: "DELETE" });
}

async function syncSourceApi(subId: number, id: string): Promise<void> {
  await apiRequest(`/subaccount/${subId}/feed-sources/${id}/sync`, { method: "POST" });
}

async function updateScheduleApi(subId: number, id: string, schedule: string): Promise<void> {
  await apiRequest(`/subaccount/${subId}/feed-sources/${id}/schedule`, {
    method: "PUT",
    body: JSON.stringify({ schedule }),
  });
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
        consumer_key: config?.consumer_key ?? config?.api_key ?? "",
        consumer_secret: config?.consumer_secret ?? config?.api_secret ?? "",
      }),
    });
  }

  return { success: true, message: "File URL provided — will be validated on sync." };
}

// ---------------------------------------------------------------------------
// Hooks
// ---------------------------------------------------------------------------

export function useFeedSources(subaccountId: number | null) {
  const queryClient = useQueryClient();
  const subId = subaccountId ?? 0;

  const { data, isLoading, error } = useQuery<FeedSourcesResponse>({
    queryKey: SOURCES_KEY(subId),
    queryFn: () => fetchSources(subId),
    enabled: subId > 0,
    retry: 1,
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => deleteSourceApi(subId, id),
    onSuccess: () => { void queryClient.invalidateQueries({ queryKey: SOURCES_KEY(subId) }); },
  });

  const syncMutation = useMutation({
    mutationFn: (id: string) => syncSourceApi(subId, id),
    onSuccess: () => { void queryClient.invalidateQueries({ queryKey: SOURCES_KEY(subId) }); },
  });

  const createMutation = useMutation({
    mutationFn: (payload: CreateFeedSourcePayload) => createSourceApi(subId, payload),
    onSuccess: () => { void queryClient.invalidateQueries({ queryKey: SOURCES_KEY(subId) }); },
  });

  const scheduleMutation = useMutation({
    mutationFn: ({ id, schedule }: { id: string; schedule: string }) => updateScheduleApi(subId, id, schedule),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: SOURCES_KEY(subId) });
    },
  });

  return {
    sources: data?.items ?? [],
    total: data?.total ?? 0,
    isLoading: subId > 0 ? isLoading : false,
    error: error instanceof Error ? error.message : null,
    deleteSource: (id: string) => deleteMutation.mutateAsync(id),
    syncSource: (id: string) => syncMutation.mutateAsync(id),
    createSource: (payload: CreateFeedSourcePayload) => createMutation.mutateAsync(payload),
    testConnection: (payload: TestConnectionPayload) => testConnectionApi(payload),
    updateSchedule: (id: string, schedule: string) => scheduleMutation.mutateAsync({ id, schedule }),
    isDeleting: deleteMutation.isPending,
    isSyncing: syncMutation.isPending,
    isCreating: createMutation.isPending,
  };
}

export function useFeedSource(subaccountId: number | null, id: string) {
  const subId = subaccountId ?? 0;

  const { data, isLoading, error, refetch } = useQuery<FeedSource>({
    queryKey: SOURCE_KEY(subId, id),
    queryFn: () => fetchSource(subId, id),
    enabled: subId > 0 && !!id,
    retry: 1,
  });

  return {
    source: data ?? null,
    isLoading: subId > 0 ? isLoading : false,
    error: error instanceof Error ? error.message : null,
    refetch,
  };
}

export function useFeedImports(subaccountId: number | null, sourceId: string) {
  const subId = subaccountId ?? 0;

  const { data, isLoading, error, refetch } = useQuery<FeedImportsResponse>({
    queryKey: IMPORTS_KEY(subId, sourceId),
    queryFn: () => fetchImports(subId, sourceId),
    enabled: subId > 0 && !!sourceId,
    retry: 1,
    // Poll every 3s when there's an active sync
    refetchInterval: (query) => {
      const items = query.state.data?.items ?? [];
      const hasActive = items.some((i: Record<string, unknown>) => i.status === "pending" || i.status === "in_progress");
      return hasActive ? 3000 : false;
    },
  });

  const items = data?.items ?? [];
  const hasPendingSync = items.some((i) => i.status === "pending" || i.status === "in_progress");

  return {
    imports: items,
    total: data?.total ?? 0,
    isLoading: subId > 0 ? isLoading : false,
    error: error instanceof Error ? error.message : null,
    refetch,
    hasPendingSync,
  };
}
