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
import { mockFeedSources } from "@/lib/mocks/feedSources";
import { mockFeedImports } from "@/lib/mocks/feedImports";

const SOURCES_KEY = ["feed-sources"] as const;
const SOURCE_KEY = (id: number) => ["feed-sources", id] as const;
const IMPORTS_KEY = (sourceId: number) => ["feed-imports", sourceId] as const;

async function fetchSources(): Promise<FeedSourcesResponse> {
  try {
    return await apiRequest<FeedSourcesResponse>("/feed-management/sources", { cache: "no-store" });
  } catch (err) {
    if (err instanceof ApiRequestError && err.status === 404) {
      await delay(300);
      return { items: mockFeedSources, total: mockFeedSources.length };
    }
    throw err;
  }
}

async function fetchSource(id: number): Promise<FeedSource> {
  try {
    return await apiRequest<FeedSource>(`/feed-management/sources/${id}`, { cache: "no-store" });
  } catch (err) {
    if (err instanceof ApiRequestError && err.status === 404) {
      const mock = mockFeedSources.find((s: FeedSource) => s.id === id);
      if (mock) {
        await delay(200);
        return mock;
      }
    }
    throw err;
  }
}

async function fetchImports(sourceId: number): Promise<FeedImportsResponse> {
  try {
    return await apiRequest<FeedImportsResponse>(`/feed-management/sources/${sourceId}/imports`, { cache: "no-store" });
  } catch (err) {
    if (err instanceof ApiRequestError && err.status === 404) {
      await delay(200);
      const items = mockFeedImports.filter((i) => i.source_id === sourceId);
      return { items, total: items.length };
    }
    throw err;
  }
}

async function createSourceApi(data: CreateFeedSourcePayload): Promise<FeedSource> {
  try {
    return await apiRequest<FeedSource>("/feed-management/sources", {
      method: "POST",
      body: JSON.stringify(data),
    });
  } catch (err) {
    if (err instanceof ApiRequestError && err.status === 404) {
      await delay(400);
      return {
        id: Date.now(),
        name: data.name,
        source_type: data.source_type,
        catalog_type: data.catalog_type,
        status: "inactive",
        last_sync: null,
        product_count: 0,
        url: data.url,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      };
    }
    throw err;
  }
}

async function deleteSourceApi(id: number): Promise<void> {
  try {
    await apiRequest(`/feed-management/sources/${id}`, { method: "DELETE" });
  } catch (err) {
    if (err instanceof ApiRequestError && err.status === 404) {
      await delay(300);
      return;
    }
    throw err;
  }
}

async function syncSourceApi(id: number): Promise<void> {
  try {
    await apiRequest(`/feed-management/sources/${id}/sync`, { method: "POST" });
  } catch (err) {
    if (err instanceof ApiRequestError && err.status === 404) {
      await delay(300);
      return;
    }
    throw err;
  }
}

async function testConnectionApi(data: TestConnectionPayload): Promise<TestConnectionResponse> {
  try {
    return await apiRequest<TestConnectionResponse>("/feed-management/test-connection", {
      method: "POST",
      body: JSON.stringify(data),
    });
  } catch (err) {
    if (err instanceof ApiRequestError && err.status === 404) {
      await delay(800);
      return { success: true, message: "Conexiune reușită (mock)." };
    }
    throw err;
  }
}

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

export function useFeedSources() {
  const queryClient = useQueryClient();

  const { data, isLoading, error } = useQuery<FeedSourcesResponse>({
    queryKey: SOURCES_KEY,
    queryFn: fetchSources,
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
    deleteSource: (id: number) => deleteMutation.mutateAsync(id),
    syncSource: (id: number) => syncMutation.mutateAsync(id),
    createSource: (data: CreateFeedSourcePayload) => createMutation.mutateAsync(data),
    testConnection: (data: TestConnectionPayload) => testConnectionApi(data),
    isDeleting: deleteMutation.isPending,
    isSyncing: syncMutation.isPending,
    isCreating: createMutation.isPending,
  };
}

export function useFeedSource(id: number) {
  const { data, isLoading, error } = useQuery<FeedSource>({
    queryKey: SOURCE_KEY(id),
    queryFn: () => fetchSource(id),
    enabled: id > 0,
  });

  return {
    source: data ?? null,
    isLoading,
    error: error instanceof Error ? error.message : null,
  };
}

export function useFeedImports(sourceId: number) {
  const { data, isLoading, error } = useQuery<FeedImportsResponse>({
    queryKey: IMPORTS_KEY(sourceId),
    queryFn: () => fetchImports(sourceId),
    enabled: sourceId > 0,
  });

  return {
    imports: data?.items ?? [],
    total: data?.total ?? 0,
    isLoading,
    error: error instanceof Error ? error.message : null,
  };
}
