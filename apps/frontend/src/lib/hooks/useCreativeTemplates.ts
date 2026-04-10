"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiRequest } from "@/lib/api";

export interface CanvasElement {
  element_id: string | null;
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
  format_group_id: string | null;
  format_label: string | null;
  style_sync_enabled: boolean;
  created_at: string;
  updated_at: string;
}

export interface CreateTemplatePayload {
  name: string;
  canvas_width?: number;
  canvas_height?: number;
  elements?: CanvasElement[];
  background_color?: string;
  format_group_id?: string;
  format_label?: string;
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

const FORMAT_SIBLINGS_KEY = (templateId: string) => ["format-siblings", templateId] as const;

async function fetchFormatSiblings(templateId: string): Promise<CreativeTemplate[]> {
  const data = await apiRequest<{ items: CreativeTemplate[] }>(
    `/creative/templates/${templateId}/format-siblings`,
    { cache: "no-store" },
  );
  return data.items ?? [];
}

export function useFormatSiblings(templateId: string | null) {
  return useQuery({
    queryKey: FORMAT_SIBLINGS_KEY(templateId ?? ""),
    queryFn: () => fetchFormatSiblings(templateId!),
    enabled: !!templateId,
  });
}

/** Group flat templates list by format_group_id. Ungrouped templates become solo groups. */
export function groupTemplatesByFormat(templates: CreativeTemplate[]): { groupId: string; groupName: string; templates: CreativeTemplate[] }[] {
  const grouped = new Map<string, CreativeTemplate[]>();
  const soloTemplates: CreativeTemplate[] = [];

  for (const t of templates) {
    if (t.format_group_id) {
      const existing = grouped.get(t.format_group_id);
      if (existing) {
        existing.push(t);
      } else {
        grouped.set(t.format_group_id, [t]);
      }
    } else {
      soloTemplates.push(t);
    }
  }

  const result: { groupId: string; groupName: string; templates: CreativeTemplate[] }[] = [];

  for (const [groupId, groupTemplates] of grouped) {
    // Derive group name from the first template (strip format suffix)
    const firstName = groupTemplates[0].name;
    const groupName = firstName.replace(/\s*-\s*(Square|Landscape|Stories)$/i, "") || firstName;
    result.push({ groupId, groupName, templates: groupTemplates });
  }

  for (const t of soloTemplates) {
    result.push({ groupId: t.id, groupName: t.name, templates: [t] });
  }

  return result;
}
