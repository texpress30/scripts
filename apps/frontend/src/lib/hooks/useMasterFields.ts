"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiRequest } from "@/lib/api";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type MasterFieldMapping = {
  id: string;
  feed_source_id: string;
  target_field: string;
  source_field: string | null;
  mapping_type: "direct" | "static" | "template";
  static_value: string | null;
  template_value: string | null;
  is_required: boolean;
  sort_order: number;
  created_at: string;
  updated_at: string;
};

export type FieldSuggestion = {
  target_field: string;
  display_name: string;
  description: string;
  field_type: string;
  required: boolean;
  category: string;
  suggested_source_field: string | null;
  enum_values: string[] | null;
  google_attribute: string | null;
  facebook_attribute: string | null;
};

export type SourceField = {
  field: string;
  type: string;
  sample: string | null;
};

export type MasterFieldsResponse = {
  source_id: string;
  source_name: string;
  catalog_type: string;
  mappings: MasterFieldMapping[];
  suggestions: FieldSuggestion[];
  source_fields: SourceField[];
  mapped_count: number;
  total_schema_fields: number;
};

export type BulkMappingItem = {
  target_field: string;
  source_field?: string | null;
  mapping_type?: "direct" | "static" | "template";
  static_value?: string | null;
  template_value?: string | null;
  is_required?: boolean;
  sort_order?: number;
};

// Channel types
export type FeedChannel = {
  id: string;
  feed_source_id: string;
  name: string;
  channel_type: string;
  status: string;
  feed_format: string;
  public_token: string;
  feed_url: string | null;
  s3_key: string | null;
  included_products: number;
  excluded_products: number;
  last_generated_at: string | null;
  error_message: string | null;
  settings: Record<string, unknown>;
  created_at: string;
  updated_at: string;
};

export type ChannelPreviewItem = {
  original: Record<string, unknown>;
  transformed: Record<string, unknown>;
};

// ---------------------------------------------------------------------------
// Query keys
// ---------------------------------------------------------------------------

const MASTER_FIELDS_KEY = (sourceId: string) => ["master-fields", sourceId] as const;
const SOURCE_FIELDS_KEY = (sourceId: string) => ["source-fields", sourceId] as const;
const CHANNELS_KEY = (sourceId: string) => ["channels", sourceId] as const;
const CHANNEL_KEY = (channelId: string) => ["channel", channelId] as const;
const CHANNEL_PREVIEW_KEY = (channelId: string) => ["channel-preview", channelId] as const;

// ---------------------------------------------------------------------------
// Master Fields hooks
// ---------------------------------------------------------------------------

export function useMasterFields(sourceId: string | null) {
  const { data, isLoading, error } = useQuery<MasterFieldsResponse>({
    queryKey: MASTER_FIELDS_KEY(sourceId ?? ""),
    queryFn: () => apiRequest<MasterFieldsResponse>(`/feed-sources/${sourceId}/master-fields`, { cache: "no-store" }),
    enabled: !!sourceId,
    retry: 1,
  });

  return {
    data: data ?? null,
    isLoading: sourceId ? isLoading : false,
    error: error instanceof Error ? error.message : null,
  };
}

export function useSaveMasterFields(sourceId: string | null) {
  const queryClient = useQueryClient();

  const mutation = useMutation({
    mutationFn: (mappings: BulkMappingItem[]) =>
      apiRequest<{ items: MasterFieldMapping[]; saved_count: number }>(
        `/feed-sources/${sourceId}/master-fields`,
        { method: "POST", body: JSON.stringify({ mappings }) },
      ),
    onSuccess: () => {
      if (sourceId) {
        void queryClient.invalidateQueries({ queryKey: MASTER_FIELDS_KEY(sourceId) });
      }
    },
  });

  return {
    save: mutation.mutateAsync,
    isSaving: mutation.isPending,
  };
}

export function useSourceFields(sourceId: string | null) {
  const { data, isLoading, error } = useQuery<{ source_id: string; fields: SourceField[]; count: number }>({
    queryKey: SOURCE_FIELDS_KEY(sourceId ?? ""),
    queryFn: () => apiRequest(`/feed-sources/${sourceId}/source-fields`, { cache: "no-store" }),
    enabled: !!sourceId,
    retry: 1,
  });

  return {
    fields: data?.fields ?? [],
    isLoading: sourceId ? isLoading : false,
    error: error instanceof Error ? error.message : null,
  };
}

// ---------------------------------------------------------------------------
// Channel hooks
// ---------------------------------------------------------------------------

export function useChannels(sourceId: string | null) {
  const queryClient = useQueryClient();

  const { data, isLoading, error } = useQuery<{ items: FeedChannel[] }>({
    queryKey: CHANNELS_KEY(sourceId ?? ""),
    queryFn: () => apiRequest(`/feed-sources/${sourceId}/channels`, { cache: "no-store" }),
    enabled: !!sourceId,
    retry: 1,
  });

  const createMutation = useMutation({
    mutationFn: (payload: { name: string; channel_type: string; feed_format?: string }) =>
      apiRequest<FeedChannel>(`/feed-sources/${sourceId}/channels`, {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    onSuccess: () => {
      if (sourceId) void queryClient.invalidateQueries({ queryKey: CHANNELS_KEY(sourceId) });
    },
  });

  return {
    channels: data?.items ?? [],
    isLoading: sourceId ? isLoading : false,
    error: error instanceof Error ? error.message : null,
    createChannel: createMutation.mutateAsync,
    isCreating: createMutation.isPending,
  };
}

export function useChannel(channelId: string | null) {
  const queryClient = useQueryClient();

  const { data, isLoading, error } = useQuery<FeedChannel>({
    queryKey: CHANNEL_KEY(channelId ?? ""),
    queryFn: () => apiRequest(`/channels/${channelId}`, { cache: "no-store" }),
    enabled: !!channelId,
    retry: 1,
  });

  const updateMutation = useMutation({
    mutationFn: (payload: Partial<FeedChannel>) =>
      apiRequest<FeedChannel>(`/channels/${channelId}`, {
        method: "PUT",
        body: JSON.stringify(payload),
      }),
    onSuccess: () => {
      if (channelId) void queryClient.invalidateQueries({ queryKey: CHANNEL_KEY(channelId) });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: () =>
      apiRequest<{ status: string }>(`/channels/${channelId}`, { method: "DELETE" }),
    onSuccess: () => {
      if (channelId) void queryClient.invalidateQueries({ queryKey: CHANNEL_KEY(channelId) });
    },
  });

  const generateMutation = useMutation({
    mutationFn: () =>
      apiRequest<{ status: string }>(`/channels/${channelId}/generate`, { method: "POST" }),
    onSuccess: () => {
      if (channelId) void queryClient.invalidateQueries({ queryKey: CHANNEL_KEY(channelId) });
    },
  });

  return {
    channel: data ?? null,
    isLoading: channelId ? isLoading : false,
    error: error instanceof Error ? error.message : null,
    updateChannel: updateMutation.mutateAsync,
    isUpdating: updateMutation.isPending,
    deleteChannel: deleteMutation.mutateAsync,
    isDeleting: deleteMutation.isPending,
    generateFeed: generateMutation.mutateAsync,
    isGenerating: generateMutation.isPending,
  };
}

export function useChannelPreview(channelId: string | null) {
  const { data, isLoading, error, refetch } = useQuery<{ channel_id: string; preview: ChannelPreviewItem[]; count: number }>({
    queryKey: CHANNEL_PREVIEW_KEY(channelId ?? ""),
    queryFn: () => apiRequest(`/channels/${channelId}/preview`, { cache: "no-store" }),
    enabled: !!channelId,
    retry: 1,
  });

  return {
    preview: data?.preview ?? [],
    isLoading: channelId ? isLoading : false,
    error: error instanceof Error ? error.message : null,
    refresh: refetch,
  };
}
