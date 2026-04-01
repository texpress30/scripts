"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import type { FeedSource, FeedSourcesResponse } from "@/lib/types/feed-management";
import { mockFeedSources } from "@/lib/mocks/feedSources";

// TODO: replace mock with real API calls when backend is ready
// import { apiRequest } from "@/lib/api";

const QUERY_KEY = ["feed-sources"] as const;

async function fetchSourcesMock(): Promise<FeedSourcesResponse> {
  // Simulate network delay
  await new Promise((resolve) => setTimeout(resolve, 400));
  return { items: mockFeedSources, total: mockFeedSources.length };
}

// async function fetchSourcesReal(): Promise<FeedSourcesResponse> {
//   return apiRequest<FeedSourcesResponse>("/feed-management/sources");
// }

// async function createSourceReal(data: Partial<FeedSource>): Promise<FeedSource> {
//   return apiRequest<FeedSource>("/feed-management/sources", {
//     method: "POST",
//     body: JSON.stringify(data),
//   });
// }

// async function deleteSourceReal(id: number): Promise<void> {
//   await apiRequest(`/feed-management/sources/${id}`, { method: "DELETE" });
// }

// async function syncSourceReal(id: number): Promise<void> {
//   await apiRequest(`/feed-management/sources/${id}/sync`, { method: "POST" });
// }

export function useFeedSources() {
  const queryClient = useQueryClient();

  const {
    data,
    isLoading,
    error,
  } = useQuery<FeedSourcesResponse>({
    queryKey: QUERY_KEY,
    queryFn: fetchSourcesMock,
  });

  const deleteMutation = useMutation({
    mutationFn: async (id: number) => {
      // TODO: replace with deleteSourceReal(id)
      await new Promise((resolve) => setTimeout(resolve, 300));
      return id;
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: QUERY_KEY });
    },
  });

  const syncMutation = useMutation({
    mutationFn: async (id: number) => {
      // TODO: replace with syncSourceReal(id)
      await new Promise((resolve) => setTimeout(resolve, 300));
      return id;
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: QUERY_KEY });
    },
  });

  return {
    sources: data?.items ?? [],
    total: data?.total ?? 0,
    isLoading,
    error: error instanceof Error ? error.message : null,
    deleteSource: (id: number) => deleteMutation.mutateAsync(id),
    syncSource: (id: number) => syncMutation.mutateAsync(id),
    isDeleting: deleteMutation.isPending,
    isSyncing: syncMutation.isPending,
  };
}
