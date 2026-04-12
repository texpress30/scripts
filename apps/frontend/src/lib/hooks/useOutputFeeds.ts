"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiRequest } from "@/lib/api";

export interface OutputFeed {
  id: string;
  subaccount_id: number;
  name: string;
  feed_source_id: string | null;
  status: "draft" | "rendering" | "published" | "error";
  enriched_feed_url: string | null;
  last_render_at: string | null;
  created_at: string;
  updated_at: string;
  feed_format: string;
  public_token: string | null;
  refresh_interval_hours: number;
  last_generated_at: string | null;
  products_count: number;
  file_size_bytes: number;
  field_mapping_id: string | null;
  s3_key: string | null;
  channel_id: string | null;
  treatment_mode: "single" | "multi";
}

export interface OutputFeedWithTreatments extends OutputFeed {
  treatments?: unknown[];
}

export interface CreateOutputFeedPayload {
  name: string;
  feed_source_id?: string;
  feed_format?: string;
  field_mapping_id?: string;
  channel_id?: string;
  treatment_mode?: "single" | "multi";
}

export interface RenderJob {
  id: string;
  template_id: string;
  output_feed_id: string;
  status: "pending" | "in_progress" | "completed" | "failed" | "no_jobs";
  total_products: number;
  rendered_products: number;
  errors: { product_id: string; error: string }[];
  started_at: string | null;
  completed_at: string | null;
}

export interface FeedStats {
  output_feed_id: string;
  products_count: number;
  file_size_bytes: number;
  last_generated_at: string | null;
  feed_format: string;
  refresh_interval_hours: number;
  status: string;
  s3_key: string | null;
}

const FEEDS_KEY = (subId: number) => ["output-feeds", subId] as const;
const FEED_KEY = (id: string) => ["output-feed", id] as const;
const RENDER_STATUS_KEY = (id: string) => ["render-status", id] as const;
const FEED_STATS_KEY = (id: string) => ["feed-stats", id] as const;

async function fetchOutputFeeds(subId: number): Promise<OutputFeed[]> {
  const data = await apiRequest<{ items: OutputFeed[] }>(
    `/creative/output-feeds?subaccount_id=${subId}`,
    { cache: "no-store" },
  );
  return data.items ?? [];
}

async function fetchOutputFeed(id: string): Promise<OutputFeedWithTreatments> {
  return apiRequest<OutputFeedWithTreatments>(`/creative/output-feeds/${id}`, { cache: "no-store" });
}

async function createOutputFeed(subId: number, payload: CreateOutputFeedPayload): Promise<OutputFeed> {
  return apiRequest<OutputFeed>(`/creative/output-feeds?subaccount_id=${subId}`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

async function updateOutputFeed(id: string, payload: Partial<CreateOutputFeedPayload>): Promise<OutputFeed> {
  return apiRequest<OutputFeed>(`/creative/output-feeds/${id}`, {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}

async function deleteOutputFeed(id: string): Promise<void> {
  await apiRequest(`/creative/output-feeds/${id}`, { method: "DELETE" });
}

async function startRender(id: string, templateId: string, products: Record<string, unknown>[]): Promise<RenderJob> {
  return apiRequest<RenderJob>(`/creative/output-feeds/${id}/render`, {
    method: "POST",
    body: JSON.stringify({ template_id: templateId, products }),
  });
}

async function fetchRenderStatus(id: string): Promise<RenderJob> {
  return apiRequest<RenderJob>(`/creative/output-feeds/${id}/render-status`, { cache: "no-store" });
}

async function generateFeed(id: string): Promise<{ status: string }> {
  return apiRequest<{ status: string }>(`/creative/output-feeds/${id}/generate`, { method: "POST" });
}

async function fetchFeedStats(id: string): Promise<FeedStats> {
  return apiRequest<FeedStats>(`/creative/output-feeds/${id}/stats`, { cache: "no-store" });
}

async function fetchPublicUrl(id: string): Promise<string> {
  const data = await apiRequest<{ public_url: string }>(`/creative/output-feeds/${id}/public-url`);
  return data.public_url;
}

async function regenerateToken(id: string): Promise<{ token: string; public_url: string }> {
  return apiRequest<{ token: string; public_url: string }>(`/creative/output-feeds/${id}/regenerate-token`, {
    method: "POST",
  });
}

async function setRefreshSchedule(id: string, hours: number): Promise<void> {
  await apiRequest(`/creative/output-feeds/${id}/schedule`, {
    method: "PUT",
    body: JSON.stringify({ interval_hours: hours }),
  });
}

export function useOutputFeeds(subaccountId: number | null) {
  const queryClient = useQueryClient();

  const feedsQuery = useQuery({
    queryKey: FEEDS_KEY(subaccountId ?? 0),
    queryFn: () => fetchOutputFeeds(subaccountId!),
    enabled: subaccountId !== null && subaccountId > 0,
  });

  const createMutation = useMutation({
    mutationFn: (payload: CreateOutputFeedPayload) => createOutputFeed(subaccountId!, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: FEEDS_KEY(subaccountId ?? 0) });
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: Partial<CreateOutputFeedPayload> }) =>
      updateOutputFeed(id, payload),
    onSuccess: (_data, vars) => {
      queryClient.invalidateQueries({ queryKey: FEEDS_KEY(subaccountId ?? 0) });
      queryClient.invalidateQueries({ queryKey: FEED_KEY(vars.id) });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => deleteOutputFeed(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: FEEDS_KEY(subaccountId ?? 0) });
    },
  });

  const generateMutation = useMutation({
    mutationFn: (id: string) => generateFeed(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: FEEDS_KEY(subaccountId ?? 0) });
    },
  });

  return {
    feeds: feedsQuery.data ?? [],
    isLoading: feedsQuery.isLoading,
    error: feedsQuery.error,
    create: createMutation.mutateAsync,
    isCreating: createMutation.isPending,
    update: updateMutation.mutateAsync,
    remove: deleteMutation.mutateAsync,
    generate: generateMutation.mutateAsync,
    isGenerating: generateMutation.isPending,
  };
}

export function useOutputFeed(feedId: string | null) {
  return useQuery({
    queryKey: FEED_KEY(feedId ?? ""),
    queryFn: () => fetchOutputFeed(feedId!),
    enabled: !!feedId,
  });
}

export function useRenderStatus(feedId: string | null, enabled = false) {
  return useQuery({
    queryKey: RENDER_STATUS_KEY(feedId ?? ""),
    queryFn: () => fetchRenderStatus(feedId!),
    enabled: !!feedId && enabled,
    refetchInterval: enabled ? 3000 : false,
  });
}

export function useFeedStats(feedId: string | null) {
  return useQuery({
    queryKey: FEED_STATS_KEY(feedId ?? ""),
    queryFn: () => fetchFeedStats(feedId!),
    enabled: !!feedId,
  });
}

export { fetchPublicUrl, regenerateToken, setRefreshSchedule, startRender };
