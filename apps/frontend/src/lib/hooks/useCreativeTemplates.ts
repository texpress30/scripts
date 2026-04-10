"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiRequest } from "@/lib/api";

export interface CanvasElement {
  type: "text" | "image" | "shape" | "dynamic_field";
  position_x: number;
  position_y: number;
  width: number;
  height: number;
  style: Record<string, unknown>;
  dynamic_binding: string | null;
  content: string;
}

export interface CreativeTemplate {
  id: string;
  subaccount_id: number;
  name: string;
  canvas_width: number;
  canvas_height: number;
  elements: CanvasElement[];
  background_color: string;
  created_at: string;
  updated_at: string;
}

export interface CreateTemplatePayload {
  name: string;
  canvas_width?: number;
  canvas_height?: number;
  elements?: CanvasElement[];
  background_color?: string;
}

export interface UpdateTemplatePayload {
  name?: string;
  canvas_width?: number;
  canvas_height?: number;
  elements?: CanvasElement[];
  background_color?: string;
}

const TEMPLATES_KEY = (subId: number) => ["creative-templates", subId] as const;
const TEMPLATE_KEY = (id: string) => ["creative-template", id] as const;

async function fetchTemplates(subId: number): Promise<CreativeTemplate[]> {
  const data = await apiRequest<{ items: CreativeTemplate[] }>(
    `/creative/templates?subaccount_id=${subId}`,
    { cache: "no-store" },
  );
  return data.items ?? [];
}

async function fetchTemplate(id: string): Promise<CreativeTemplate> {
  return apiRequest<CreativeTemplate>(`/creative/templates/${id}`, { cache: "no-store" });
}

async function createTemplate(subId: number, payload: CreateTemplatePayload): Promise<CreativeTemplate> {
  return apiRequest<CreativeTemplate>(`/creative/templates?subaccount_id=${subId}`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

async function updateTemplate(id: string, payload: UpdateTemplatePayload): Promise<CreativeTemplate> {
  return apiRequest<CreativeTemplate>(`/creative/templates/${id}`, {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}

async function deleteTemplate(id: string): Promise<void> {
  await apiRequest(`/creative/templates/${id}`, { method: "DELETE" });
}

async function duplicateTemplate(id: string, newName: string): Promise<CreativeTemplate> {
  return apiRequest<CreativeTemplate>(`/creative/templates/${id}/duplicate`, {
    method: "POST",
    body: JSON.stringify({ new_name: newName }),
  });
}

export function useCreativeTemplates(subaccountId: number | null) {
  const queryClient = useQueryClient();

  const templatesQuery = useQuery({
    queryKey: TEMPLATES_KEY(subaccountId ?? 0),
    queryFn: () => fetchTemplates(subaccountId!),
    enabled: subaccountId !== null && subaccountId > 0,
  });

  const createMutation = useMutation({
    mutationFn: (payload: CreateTemplatePayload) => createTemplate(subaccountId!, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: TEMPLATES_KEY(subaccountId ?? 0) });
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: UpdateTemplatePayload }) =>
      updateTemplate(id, payload),
    onSuccess: (_data, vars) => {
      queryClient.invalidateQueries({ queryKey: TEMPLATES_KEY(subaccountId ?? 0) });
      queryClient.invalidateQueries({ queryKey: TEMPLATE_KEY(vars.id) });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => deleteTemplate(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: TEMPLATES_KEY(subaccountId ?? 0) });
    },
  });

  const duplicateMutation = useMutation({
    mutationFn: ({ id, newName }: { id: string; newName: string }) => duplicateTemplate(id, newName),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: TEMPLATES_KEY(subaccountId ?? 0) });
    },
  });

  return {
    templates: templatesQuery.data ?? [],
    isLoading: templatesQuery.isLoading,
    error: templatesQuery.error,
    refetch: templatesQuery.refetch,
    create: createMutation.mutateAsync,
    isCreating: createMutation.isPending,
    update: updateMutation.mutateAsync,
    isUpdating: updateMutation.isPending,
    remove: deleteMutation.mutateAsync,
    isDeleting: deleteMutation.isPending,
    duplicate: duplicateMutation.mutateAsync,
    isDuplicating: duplicateMutation.isPending,
  };
}

export function useCreativeTemplate(templateId: string | null) {
  return useQuery({
    queryKey: TEMPLATE_KEY(templateId ?? ""),
    queryFn: () => fetchTemplate(templateId!),
    enabled: !!templateId,
  });
}
