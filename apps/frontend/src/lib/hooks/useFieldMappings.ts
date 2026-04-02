"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import type {
  CatalogType,
  CatalogSchema,
  FieldMapping,
  FieldMappingsResponse,
  CreateFieldMappingPayload,
  UpdateMappingRulePayload,
  FieldMappingPreviewRow,
} from "@/lib/types/feed-management";
import { apiRequest } from "@/lib/api";

const SCHEMAS_KEY = ["catalog-schemas"] as const;
const SCHEMA_KEY = (type: CatalogType) => ["catalog-schemas", type] as const;
const MAPPINGS_KEY = (subId: number, sourceId: string) => ["field-mappings", subId, sourceId] as const;
const MAPPING_KEY = (id: string | number) => ["field-mapping", id] as const;
const PREVIEW_KEY = (id: string | number) => ["field-mapping-preview", id] as const;

// ---------------------------------------------------------------------------
// Catalog schemas (no subaccount needed)
// ---------------------------------------------------------------------------

async function fetchCatalogSchemas(): Promise<CatalogSchema[]> {
  const data = await apiRequest<{ items: { catalog_type: string; required: unknown[]; optional: unknown[] }[] }>("/catalog-schemas", { cache: "no-store" });
  // Backend returns { items: [...] } with CatalogTypeInfo shape — map to CatalogSchema
  return (data.items ?? []).map((item) => ({
    catalog_type: item.catalog_type as CatalogType,
    label: item.catalog_type.replace(/_/g, " ").replace(/\b\w/g, (c: string) => c.toUpperCase()),
    description: "",
    fields: [],
  }));
}

// ---------------------------------------------------------------------------
// Field mappings (subaccount-scoped via feed source)
// ---------------------------------------------------------------------------

async function fetchFieldMappings(subId: number, sourceId: string): Promise<FieldMappingsResponse> {
  const data = await apiRequest<{ items: Record<string, unknown>[] }>(
    `/subaccount/${subId}/feed-sources/${sourceId}/field-mappings`,
    { cache: "no-store" },
  );
  const items = (data.items ?? []).map((raw): FieldMapping => ({
    id: String(raw.id ?? ""),
    source_id: String(raw.feed_source_id ?? sourceId),
    source_name: String(raw.name ?? ""),
    catalog_type: (String(raw.target_channel ?? "product").replace("_catalog", "") as FieldMapping["catalog_type"]),
    rules: Array.isArray(raw.rules) ? raw.rules as FieldMapping["rules"] : [],
    created_at: String(raw.created_at ?? ""),
    updated_at: String(raw.updated_at ?? ""),
  }));
  return { items, total: items.length };
}

async function fetchFieldMapping(id: string | number): Promise<FieldMapping> {
  return apiRequest<FieldMapping>(`/field-mappings/${id}`, { cache: "no-store" });
}

async function createFieldMappingApi(
  subId: number,
  sourceId: string,
  data: CreateFieldMappingPayload,
): Promise<FieldMapping> {
  return apiRequest<FieldMapping>(
    `/subaccount/${subId}/feed-sources/${sourceId}/field-mappings`,
    {
      method: "POST",
      body: JSON.stringify({
        name: `Mapping ${new Date().toLocaleDateString()}`,
        target_channel: "google_shopping",
        from_preset: true,
        ...data,
      }),
    },
  );
}

async function updateMappingRuleApi(mappingId: string | number, ruleData: UpdateMappingRulePayload): Promise<FieldMapping> {
  return apiRequest<FieldMapping>(`/field-mappings/${mappingId}/rules`, {
    method: "POST",
    body: JSON.stringify(ruleData),
  });
}

async function fetchMappingPreview(mappingId: string | number): Promise<FieldMappingPreviewRow[]> {
  const data = await apiRequest<{ results: { original: unknown; transformed: unknown }[] }>(
    `/field-mappings/${mappingId}/preview`,
    { method: "POST", body: JSON.stringify({ limit: 5 }) },
  );
  return (data.results ?? []).map((r) => ({
    product_name: String((r.original as Record<string, unknown>)?.product_id ?? ""),
    source_value: JSON.stringify(r.original).slice(0, 100),
    transformed_value: JSON.stringify(r.transformed).slice(0, 100),
  }));
}

// ---------------------------------------------------------------------------
// Hooks
// ---------------------------------------------------------------------------

export function useCatalogSchemas() {
  const { data, isLoading, error } = useQuery<CatalogSchema[]>({
    queryKey: SCHEMAS_KEY,
    queryFn: fetchCatalogSchemas,
    retry: 1,
  });

  return {
    schemas: data ?? [],
    isLoading,
    error: error instanceof Error ? error.message : null,
  };
}

export function useCatalogSchema(type: CatalogType | null) {
  const { data, isLoading, error } = useQuery<CatalogSchema[]>({
    queryKey: SCHEMA_KEY(type ?? "product"),
    queryFn: fetchCatalogSchemas,
    enabled: type !== null,
    retry: 1,
  });

  const schema = data?.find((s) => s.catalog_type === type) ?? null;
  return {
    schema,
    isLoading,
    error: error instanceof Error ? error.message : null,
  };
}

export function useFieldMappings(subaccountId: number | null, sourceId?: string) {
  const queryClient = useQueryClient();
  const subId = subaccountId ?? 0;
  const srcId = sourceId ?? "";

  const { data, isLoading, error } = useQuery<FieldMappingsResponse>({
    queryKey: MAPPINGS_KEY(subId, srcId),
    queryFn: () => fetchFieldMappings(subId, srcId),
    enabled: subId > 0 && !!srcId,
    retry: 1,
  });

  const createMutation = useMutation({
    mutationFn: (payload: CreateFieldMappingPayload) => createFieldMappingApi(subId, srcId, payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: MAPPINGS_KEY(subId, srcId) });
    },
  });

  return {
    mappings: data?.items ?? [],
    total: data?.total ?? 0,
    isLoading: subId > 0 && !!srcId ? isLoading : false,
    error: error instanceof Error ? error.message : null,
    createMapping: (payload: CreateFieldMappingPayload) => createMutation.mutateAsync(payload),
    isCreating: createMutation.isPending,
  };
}

export function useFieldMapping(id: string | number) {
  const queryClient = useQueryClient();

  const { data, isLoading, error } = useQuery<FieldMapping>({
    queryKey: MAPPING_KEY(id),
    queryFn: () => fetchFieldMapping(id),
    enabled: !!id,
    retry: 1,
  });

  const updateRuleMutation = useMutation({
    mutationFn: (ruleData: UpdateMappingRulePayload) => updateMappingRuleApi(id, ruleData),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: MAPPING_KEY(id) });
    },
  });

  return {
    mapping: data ?? null,
    isLoading,
    error: error instanceof Error ? error.message : null,
    updateRule: (ruleData: UpdateMappingRulePayload) => updateRuleMutation.mutateAsync(ruleData),
    isUpdating: updateRuleMutation.isPending,
  };
}

export function useFieldMappingPreview(mappingId: string | number) {
  const { data, isLoading, error, refetch } = useQuery<FieldMappingPreviewRow[]>({
    queryKey: PREVIEW_KEY(mappingId),
    queryFn: () => fetchMappingPreview(mappingId),
    enabled: !!mappingId,
    retry: 1,
  });

  return {
    preview: data ?? [],
    isLoading,
    error: error instanceof Error ? error.message : null,
    refresh: refetch,
  };
}
