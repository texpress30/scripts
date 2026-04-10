"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiRequest } from "@/lib/api";

export interface BrandPreset {
  id: string;
  subaccount_id: number;
  name: string;
  colors: string[];
  fonts: string[];
  logo_url: string | null;
  is_default: boolean;
  created_at: string;
  updated_at: string;
}

export interface CreateBrandPresetPayload {
  name: string;
  colors?: string[];
  fonts?: string[];
  logo_url?: string;
  is_default?: boolean;
}

export interface UpdateBrandPresetPayload {
  name?: string;
  colors?: string[];
  fonts?: string[];
  logo_url?: string;
  is_default?: boolean;
}

const PRESETS_KEY = (subId: number) => ["brand-presets", subId] as const;

async function fetchPresets(subId: number): Promise<BrandPreset[]> {
  const data = await apiRequest<{ items: BrandPreset[] }>(
    `/creative/brand-presets?subaccount_id=${subId}`,
    { cache: "no-store" },
  );
  return data.items ?? [];
}

async function createPreset(subId: number, payload: CreateBrandPresetPayload): Promise<BrandPreset> {
  return apiRequest<BrandPreset>(`/creative/brand-presets?subaccount_id=${subId}`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

async function updatePreset(id: string, payload: UpdateBrandPresetPayload): Promise<BrandPreset> {
  return apiRequest<BrandPreset>(`/creative/brand-presets/${id}`, {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}

async function deletePreset(id: string): Promise<void> {
  await apiRequest(`/creative/brand-presets/${id}`, { method: "DELETE" });
}

export function useBrandPresets(subaccountId: number | null) {
  const queryClient = useQueryClient();

  const presetsQuery = useQuery({
    queryKey: PRESETS_KEY(subaccountId ?? 0),
    queryFn: () => fetchPresets(subaccountId!),
    enabled: subaccountId !== null && subaccountId > 0,
  });

  const createMutation = useMutation({
    mutationFn: (payload: CreateBrandPresetPayload) => createPreset(subaccountId!, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: PRESETS_KEY(subaccountId ?? 0) });
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: UpdateBrandPresetPayload }) =>
      updatePreset(id, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: PRESETS_KEY(subaccountId ?? 0) });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => deletePreset(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: PRESETS_KEY(subaccountId ?? 0) });
    },
  });

  return {
    presets: presetsQuery.data ?? [],
    isLoading: presetsQuery.isLoading,
    create: createMutation.mutateAsync,
    isCreating: createMutation.isPending,
    update: updateMutation.mutateAsync,
    remove: deleteMutation.mutateAsync,
  };
}
