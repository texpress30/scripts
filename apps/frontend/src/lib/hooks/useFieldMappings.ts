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
import { apiRequest, ApiRequestError } from "@/lib/api";
import { mockCatalogSchemas } from "@/lib/mocks/catalogSchemas";
import { mockFieldMappings } from "@/lib/mocks/fieldMappings";

const SCHEMAS_KEY = ["catalog-schemas"] as const;
const SCHEMA_KEY = (type: CatalogType) => ["catalog-schemas", type] as const;
const MAPPINGS_KEY = (sourceId?: number) => sourceId ? ["field-mappings", sourceId] as const : ["field-mappings"] as const;
const MAPPING_KEY = (id: number) => ["field-mapping", id] as const;
const PREVIEW_KEY = (id: number) => ["field-mapping-preview", id] as const;

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function fetchCatalogSchemas(): Promise<CatalogSchema[]> {
  try {
    return await apiRequest<CatalogSchema[]>("/catalog-schemas", { cache: "no-store" });
  } catch (err) {
    if (err instanceof ApiRequestError && err.status === 404) {
      await delay(200);
      return mockCatalogSchemas;
    }
    throw err;
  }
}

async function fetchFieldMappings(sourceId?: number): Promise<FieldMappingsResponse> {
  try {
    const path = sourceId ? `/field-mappings?source_id=${sourceId}` : "/field-mappings";
    return await apiRequest<FieldMappingsResponse>(path, { cache: "no-store" });
  } catch (err) {
    if (err instanceof ApiRequestError && err.status === 404) {
      await delay(200);
      const items = sourceId
        ? mockFieldMappings.filter((m) => m.source_id === sourceId)
        : mockFieldMappings;
      return { items, total: items.length };
    }
    throw err;
  }
}

async function fetchFieldMapping(id: number): Promise<FieldMapping> {
  try {
    return await apiRequest<FieldMapping>(`/field-mappings/${id}`, { cache: "no-store" });
  } catch (err) {
    if (err instanceof ApiRequestError && err.status === 404) {
      const mock = mockFieldMappings.find((m) => m.id === id);
      if (mock) {
        await delay(200);
        return mock;
      }
    }
    throw err;
  }
}

async function createFieldMappingApi(data: CreateFieldMappingPayload): Promise<FieldMapping> {
  try {
    return await apiRequest<FieldMapping>("/field-mappings", {
      method: "POST",
      body: JSON.stringify(data),
    });
  } catch (err) {
    if (err instanceof ApiRequestError && err.status === 404) {
      await delay(400);
      return {
        id: Date.now(),
        source_id: data.source_id,
        source_name: "New Mapping",
        catalog_type: "product",
        rules: [],
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      };
    }
    throw err;
  }
}

async function updateMappingRuleApi(mappingId: number, ruleData: UpdateMappingRulePayload): Promise<FieldMapping> {
  try {
    return await apiRequest<FieldMapping>(`/field-mappings/${mappingId}/rules`, {
      method: "POST",
      body: JSON.stringify(ruleData),
    });
  } catch (err) {
    if (err instanceof ApiRequestError && err.status === 404) {
      await delay(300);
      const existing = mockFieldMappings.find((m) => m.id === mappingId);
      if (existing) {
        const newRule = {
          id: Date.now(),
          ...ruleData,
        };
        return { ...existing, rules: [...existing.rules, newRule], updated_at: new Date().toISOString() };
      }
    }
    throw err;
  }
}

async function fetchMappingPreview(mappingId: number): Promise<FieldMappingPreviewRow[]> {
  try {
    return await apiRequest<FieldMappingPreviewRow[]>(`/field-mappings/${mappingId}/preview`, { cache: "no-store" });
  } catch (err) {
    if (err instanceof ApiRequestError && err.status === 404) {
      await delay(500);
      return [
        { product_name: "Blue Widget", source_value: "Blue Widget Pro", transformed_value: "Blue Widget Pro" },
        { product_name: "Red Gadget", source_value: "49.99", transformed_value: "$49.99" },
        { product_name: "Green Tool", source_value: "15", transformed_value: "in_stock" },
        { product_name: "Yellow Item", source_value: "", transformed_value: "", error: "Empty source value" },
        { product_name: "Purple Device", source_value: "purple-device-handle", transformed_value: "https://my-store.myshopify.com/products/purple-device-handle" },
      ];
    }
    throw err;
  }
}

export function useCatalogSchemas() {
  const { data, isLoading, error } = useQuery<CatalogSchema[]>({
    queryKey: SCHEMAS_KEY,
    queryFn: fetchCatalogSchemas,
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
  });

  const schema = data?.find((s) => s.catalog_type === type) ?? null;
  return {
    schema,
    isLoading,
    error: error instanceof Error ? error.message : null,
  };
}

export function useFieldMappings(sourceId?: number) {
  const queryClient = useQueryClient();

  const { data, isLoading, error } = useQuery<FieldMappingsResponse>({
    queryKey: MAPPINGS_KEY(sourceId),
    queryFn: () => fetchFieldMappings(sourceId),
  });

  const createMutation = useMutation({
    mutationFn: createFieldMappingApi,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: MAPPINGS_KEY(sourceId) });
    },
  });

  return {
    mappings: data?.items ?? [],
    total: data?.total ?? 0,
    isLoading,
    error: error instanceof Error ? error.message : null,
    createMapping: (payload: CreateFieldMappingPayload) => createMutation.mutateAsync(payload),
    isCreating: createMutation.isPending,
  };
}

export function useFieldMapping(id: number) {
  const queryClient = useQueryClient();

  const { data, isLoading, error } = useQuery<FieldMapping>({
    queryKey: MAPPING_KEY(id),
    queryFn: () => fetchFieldMapping(id),
    enabled: id > 0,
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

export function useFieldMappingPreview(mappingId: number) {
  const { data, isLoading, error, refetch } = useQuery<FieldMappingPreviewRow[]>({
    queryKey: PREVIEW_KEY(mappingId),
    queryFn: () => fetchMappingPreview(mappingId),
    enabled: mappingId > 0,
  });

  return {
    preview: data ?? [],
    isLoading,
    error: error instanceof Error ? error.message : null,
    refresh: refetch,
  };
}
