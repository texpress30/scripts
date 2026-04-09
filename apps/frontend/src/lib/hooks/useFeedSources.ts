"use client";

import { useState, useEffect, useRef } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import type {
  FeedSource,
  FeedSourcesResponse,
  FeedImportsResponse,
  CreateFeedSourcePayload,
  CreateShopifySourceResponse,
  ShopifyImportResult,
  ShopifyReconnectResult,
  FeedConnectionStatus,
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
  const config = (raw.config as Record<string, unknown> | undefined) ?? undefined;
  const shopDomain = (raw.shop_domain as string | null | undefined) ?? null;
  return {
    id: String(raw.id ?? ""),
    name: String(raw.name ?? ""),
    source_type: String(raw.source_type ?? "csv") as FeedSource["source_type"],
    catalog_type: String(raw.catalog_type ?? "product") as FeedSource["catalog_type"],
    status: raw.is_active === false ? "inactive" : "active",
    last_sync: (raw.last_sync_at as string) ?? (raw.last_sync as string) ?? null,
    product_count: Number(raw.product_count ?? 0),
    url: String(
      shopDomain ??
        (config ? (config.store_url as string | undefined) ?? (config.file_url as string | undefined) ?? "" : ""),
    ),
    config,
    is_active: raw.is_active as boolean | undefined,
    subaccount_id: raw.subaccount_id as number | undefined,
    shop_domain: shopDomain,
    connection_status: (raw.connection_status as FeedConnectionStatus | undefined) ?? "pending",
    last_connection_check: (raw.last_connection_check as string | null | undefined) ?? null,
    last_error: (raw.last_error as string | null | undefined) ?? null,
    has_token: Boolean(raw.has_token),
    has_file_auth: Boolean(raw.has_file_auth),
    file_auth_username: (raw.file_auth_username as string | null | undefined) ?? null,
    file_auth_password_masked: (raw.file_auth_password_masked as string | null | undefined) ?? null,
    last_import_at: (raw.last_import_at as string | null | undefined) ?? null,
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
    if (data.source_type === "woocommerce" || data.source_type === "magento" || data.source_type === "bigcommerce") {
      config.store_url = config.store_url ?? data.url;
    } else if (data.source_type !== "shopify") {
      config.file_url = config.file_url ?? data.url;
    }
  }

  const payload: Record<string, unknown> = {
    name: data.name,
    source_type: data.source_type,
    catalog_type: data.catalog_type ?? "product",
    config,
  };
  if (data.catalog_variant) payload.catalog_variant = data.catalog_variant;
  if (data.shop_domain) payload.shop_domain = data.shop_domain;
  // Only forward HTTP Basic Auth credentials for file sources that
  // actually supplied both halves of the pair. The backend rejects
  // half-configured auth with a 400, so we gate the forward client-side
  // to keep the API contract tight.
  if (data.feed_auth_username && data.feed_auth_password) {
    payload.feed_auth_username = data.feed_auth_username;
    payload.feed_auth_password = data.feed_auth_password;
  }

  const raw = await apiRequest<Record<string, unknown>>(`/subaccount/${subId}/feed-sources`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
  return normalizeSource(raw);
}

async function createShopifySourceApi(
  subId: number,
  data: { name: string; shop_domain: string; catalog_type?: string; catalog_variant?: string },
): Promise<CreateShopifySourceResponse> {
  const payload = {
    name: data.name,
    source_type: "shopify",
    catalog_type: data.catalog_type ?? "product",
    catalog_variant: data.catalog_variant ?? "physical_products",
    shop_domain: data.shop_domain,
    config: {},
  };
  const raw = await apiRequest<{ source: Record<string, unknown>; authorize_url: string | null; state: string | null }>(
    `/subaccount/${subId}/feed-sources`,
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
  );
  return {
    source: normalizeSource(raw.source),
    authorize_url: raw.authorize_url ?? null,
    state: raw.state ?? null,
  };
}

async function completeShopifyOAuthApi(
  subId: number,
  sourceId: string,
  payload: { code: string; state: string; shop?: string },
): Promise<FeedSource> {
  const raw = await apiRequest<Record<string, unknown>>(
    `/subaccount/${subId}/feed-sources/${sourceId}/complete-oauth`,
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
  );
  return normalizeSource(raw);
}

async function reconnectShopifySourceApi(subId: number, sourceId: string): Promise<ShopifyReconnectResult> {
  return apiRequest<ShopifyReconnectResult>(`/subaccount/${subId}/feed-sources/${sourceId}/reconnect`, {
    method: "POST",
  });
}

async function importShopifySourceApi(subId: number, sourceId: string): Promise<ShopifyImportResult> {
  return apiRequest<ShopifyImportResult>(`/subaccount/${subId}/feed-sources/${sourceId}/import`, {
    method: "POST",
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

  // Shopify no longer exposes a "test connection" button: the new OAuth-based
  // flow defers connectivity checks to the per-source endpoint
  // POST /subaccount/{id}/feed-sources/{source_id}/test-connection, which uses
  // the stored access token instead of collecting API key/secret up-front.
  if (source_type === "shopify") {
    return { success: true, message: "Shopify conectarea se verifică după OAuth exchange." };
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

  // Track which sources are currently syncing + their last_sync at trigger time
  const [syncingIds, setSyncingIds] = useState<Set<string>>(new Set());
  const syncSnapshotsRef = useRef<Map<string, string | null>>(new Map());

  const { data, isLoading, error } = useQuery<FeedSourcesResponse>({
    queryKey: SOURCES_KEY(subId),
    queryFn: () => fetchSources(subId),
    enabled: subId > 0,
    retry: 1,
    refetchInterval: syncingIds.size > 0 ? 3000 : false,
  });

  // Detect sync completion: when a syncing source's last_sync changes
  useEffect(() => {
    if (!data?.items || syncingIds.size === 0) return;
    const completed = new Set<string>();
    for (const source of data.items) {
      if (syncingIds.has(source.id)) {
        const snapshotSync = syncSnapshotsRef.current.get(source.id) ?? null;
        if (source.last_sync && source.last_sync !== snapshotSync) {
          completed.add(source.id);
        }
      }
    }
    if (completed.size > 0) {
      setSyncingIds((prev) => {
        const next = new Set(prev);
        completed.forEach((id) => next.delete(id));
        return next;
      });
      completed.forEach((id) => syncSnapshotsRef.current.delete(id));
    }
  }, [data, syncingIds]);

  const deleteMutation = useMutation({
    mutationFn: (id: string) => deleteSourceApi(subId, id),
    onSuccess: () => { void queryClient.invalidateQueries({ queryKey: SOURCES_KEY(subId) }); },
  });

  const syncMutation = useMutation({
    mutationFn: (id: string) => syncSourceApi(subId, id),
    onSuccess: (_data, id) => {
      // Snapshot last_sync at trigger time so we can detect when it changes
      const current = data?.items?.find((s) => s.id === id);
      syncSnapshotsRef.current.set(id, current?.last_sync ?? null);
      setSyncingIds((prev) => new Set(prev).add(id));
      void queryClient.invalidateQueries({ queryKey: SOURCES_KEY(subId) });
      void queryClient.invalidateQueries({ queryKey: ["source-fields", id] });
      void queryClient.invalidateQueries({ queryKey: ["master-fields", id] });
    },
  });

  const createMutation = useMutation({
    mutationFn: (payload: CreateFeedSourcePayload) => createSourceApi(subId, payload),
    onSuccess: () => { void queryClient.invalidateQueries({ queryKey: SOURCES_KEY(subId) }); },
  });

  const createShopifyMutation = useMutation({
    mutationFn: (payload: { name: string; shop_domain: string; catalog_type?: string; catalog_variant?: string }) =>
      createShopifySourceApi(subId, payload),
    onSuccess: () => { void queryClient.invalidateQueries({ queryKey: SOURCES_KEY(subId) }); },
  });

  const reconnectMutation = useMutation({
    mutationFn: (sourceId: string) => reconnectShopifySourceApi(subId, sourceId),
  });

  const importMutation = useMutation({
    mutationFn: (sourceId: string) => importShopifySourceApi(subId, sourceId),
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
    createShopifySource: (payload: { name: string; shop_domain: string; catalog_type?: string; catalog_variant?: string }) =>
      createShopifyMutation.mutateAsync(payload),
    completeShopifyOAuth: (sourceId: string, payload: { code: string; state: string; shop?: string }) =>
      completeShopifyOAuthApi(subId, sourceId, payload),
    reconnectShopifySource: (sourceId: string) => reconnectMutation.mutateAsync(sourceId),
    importShopifySource: (sourceId: string) => importMutation.mutateAsync(sourceId),
    testConnection: (payload: TestConnectionPayload) => testConnectionApi(payload),
    updateSchedule: (id: string, schedule: string) => scheduleMutation.mutateAsync({ id, schedule }),
    isDeleting: deleteMutation.isPending,
    isSyncing: syncMutation.isPending,
    isCreating: createMutation.isPending || createShopifyMutation.isPending,
    isImporting: importMutation.isPending,
    isReconnecting: reconnectMutation.isPending,
    syncingIds,
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
