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
  manually_edited: boolean;
  created_at: string;
  updated_at: string;
};

export type ChannelBadge = {
  channel_slug: string;
  is_required: boolean;
  channel_field_name: string;
};

export type FieldAlias = {
  alias_key: string;
  platform_hint: string;
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
  channels?: ChannelBadge[];
  is_system?: boolean;
  aliases_count?: number;
  aliases?: FieldAlias[];
  all_channels?: string[];
  channels_count?: number;
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
  manually_edited?: boolean;
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
  const { data, isLoading, error } = useQuery<{ source_id: string; fields: SourceField[]; count: number; total_products_scanned: number }>({
    queryKey: SOURCE_FIELDS_KEY(sourceId ?? ""),
    queryFn: () => apiRequest(`/feed-sources/${sourceId}/source-fields`, { cache: "no-store" }),
    enabled: !!sourceId,
    retry: 1,
    staleTime: 5 * 60 * 1000, // 5 minutes cache
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

// ---------------------------------------------------------------------------
// Channel schema fields (with inheritance)
// ---------------------------------------------------------------------------

export type ChannelFieldMapping = {
  type: string;
  source_field: string | null;
  static_value: string | null;
  template_value: string | null;
  inherited_from: "master_fields" | "channel_override";
};

export type ChannelSchemaField = {
  canonical_key: string;
  channel_field_name: string;
  display_name: string;
  data_type: string;
  is_required: boolean;
  sort_order: number;
  source_description: string | null;
  mapping: ChannelFieldMapping | null;
};

export type ChannelFieldsResponse = {
  channel_id: string;
  channel_type: string;
  channel_name: string;
  catalog_type: string;
  source_id: string;
  fields: ChannelSchemaField[];
  total: number;
  required_count: number;
  optional_count: number;
  mapped_count: number;
};

const CHANNEL_FIELDS_KEY = (channelId: string) => ["channel-fields", channelId] as const;

export function useChannelFields(channelId: string | null) {
  const queryClient = useQueryClient();

  const { data, isLoading, error } = useQuery<ChannelFieldsResponse>({
    queryKey: CHANNEL_FIELDS_KEY(channelId ?? ""),
    queryFn: () => apiRequest<ChannelFieldsResponse>(`/channels/${channelId}/schema-fields`, { cache: "no-store" }),
    enabled: !!channelId,
    retry: 1,
  });

  return {
    data: data ?? null,
    isLoading: channelId ? isLoading : false,
    error: error instanceof Error ? error.message : null,
    refetch: () => {
      if (channelId) void queryClient.invalidateQueries({ queryKey: CHANNEL_FIELDS_KEY(channelId) });
    },
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
