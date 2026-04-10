"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiRequest } from "@/lib/api";

export interface TreatmentFilter {
  field_name: string;
  operator: "equals" | "contains" | "in_list";
  value: string | string[];
}

export interface Treatment {
  id: string;
  output_feed_id: string;
  name: string;
  template_id: string;
  filters: TreatmentFilter[];
  priority: number;
  is_default: boolean;
  created_at: string;
  updated_at: string;
}

export interface CreateTreatmentPayload {
  name: string;
  template_id: string;
  output_feed_id: string;
  filters?: TreatmentFilter[];
  priority?: number;
  is_default?: boolean;
}

export interface UpdateTreatmentPayload {
  name?: string;
  template_id?: string;
  filters?: TreatmentFilter[];
  priority?: number;
  is_default?: boolean;
}

const TREATMENTS_KEY = (feedId: string) => ["treatments", feedId] as const;

async function fetchTreatments(feedId: string): Promise<Treatment[]> {
  const data = await apiRequest<{ items: Treatment[] }>(
    `/creative/output-feeds/${feedId}/treatments`,
    { cache: "no-store" },
  );
  return data.items ?? [];
}

async function createTreatment(feedId: string, payload: CreateTreatmentPayload): Promise<Treatment> {
  return apiRequest<Treatment>(`/creative/output-feeds/${feedId}/treatments`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

async function updateTreatment(id: string, payload: UpdateTreatmentPayload): Promise<Treatment> {
  return apiRequest<Treatment>(`/creative/treatments/${id}`, {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}

async function deleteTreatment(id: string): Promise<void> {
  await apiRequest(`/creative/treatments/${id}`, { method: "DELETE" });
}

async function reorderTreatments(feedId: string, treatmentIds: string[]): Promise<Treatment[]> {
  const data = await apiRequest<{ items: Treatment[] }>(
    `/creative/output-feeds/${feedId}/treatments/reorder`,
    { method: "POST", body: JSON.stringify({ treatment_ids: treatmentIds }) },
  );
  return data.items ?? [];
}

export function useTreatments(outputFeedId: string | null) {
  const queryClient = useQueryClient();

  const treatmentsQuery = useQuery({
    queryKey: TREATMENTS_KEY(outputFeedId ?? ""),
    queryFn: () => fetchTreatments(outputFeedId!),
    enabled: !!outputFeedId,
  });

  const createMutation = useMutation({
    mutationFn: (payload: CreateTreatmentPayload) => createTreatment(outputFeedId!, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: TREATMENTS_KEY(outputFeedId ?? "") });
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: UpdateTreatmentPayload }) =>
      updateTreatment(id, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: TREATMENTS_KEY(outputFeedId ?? "") });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => deleteTreatment(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: TREATMENTS_KEY(outputFeedId ?? "") });
    },
  });

  const reorderMutation = useMutation({
    mutationFn: (treatmentIds: string[]) => reorderTreatments(outputFeedId!, treatmentIds),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: TREATMENTS_KEY(outputFeedId ?? "") });
    },
  });

  return {
    treatments: treatmentsQuery.data ?? [],
    isLoading: treatmentsQuery.isLoading,
    error: treatmentsQuery.error,
    create: createMutation.mutateAsync,
    isCreating: createMutation.isPending,
    update: updateMutation.mutateAsync,
    remove: deleteMutation.mutateAsync,
    reorder: reorderMutation.mutateAsync,
  };
}
