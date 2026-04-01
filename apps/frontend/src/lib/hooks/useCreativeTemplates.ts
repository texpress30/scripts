"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import type {
  CreativeTemplate,
  CreativeTemplatesResponse,
  CreateTemplatePayload,
  UpdateTemplatePayload,
  DuplicateTemplatePayload,
  PreviewTemplatePayload,
  PreviewTemplateResponse,
} from "@/lib/types/creative-studio";
import { apiRequest, ApiRequestError } from "@/lib/api";
import { mockCreativeTemplates } from "@/lib/mocks/creativeTemplates";

const TEMPLATES_KEY = ["creative-templates"] as const;
const TEMPLATE_KEY = (id: string) => ["creative-templates", id] as const;

async function fetchTemplates(): Promise<CreativeTemplatesResponse> {
  try {
    return await apiRequest<CreativeTemplatesResponse>("/creative/templates?subaccount_id=1", { cache: "no-store" });
  } catch (err) {
    if (err instanceof ApiRequestError && err.status === 404) {
      await delay(300);
      return { items: mockCreativeTemplates };
    }
    throw err;
  }
}

async function fetchTemplate(id: string): Promise<CreativeTemplate> {
  try {
    return await apiRequest<CreativeTemplate>(`/creative/templates/${id}`, { cache: "no-store" });
  } catch (err) {
    if (err instanceof ApiRequestError && err.status === 404) {
      const mock = mockCreativeTemplates.find((t) => t.id === id);
      if (mock) { await delay(200); return mock; }
    }
    throw err;
  }
}

async function createTemplateApi(data: CreateTemplatePayload): Promise<CreativeTemplate> {
  try {
    return await apiRequest<CreativeTemplate>("/creative/templates?subaccount_id=1", {
      method: "POST",
      body: JSON.stringify(data),
    });
  } catch (err) {
    if (err instanceof ApiRequestError && err.status === 404) {
      await delay(400);
      return {
        id: `tpl_${Date.now()}`,
        subaccount_id: 1,
        name: data.name,
        canvas_width: data.canvas_width,
        canvas_height: data.canvas_height,
        background_color: data.background_color,
        elements: data.elements ?? [],
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      };
    }
    throw err;
  }
}

async function updateTemplateApi(id: string, data: UpdateTemplatePayload): Promise<CreativeTemplate> {
  try {
    return await apiRequest<CreativeTemplate>(`/creative/templates/${id}`, {
      method: "PUT",
      body: JSON.stringify(data),
    });
  } catch (err) {
    if (err instanceof ApiRequestError && err.status === 404) {
      await delay(300);
      const mock = mockCreativeTemplates.find((t) => t.id === id);
      return { ...(mock ?? { id, subaccount_id: 1, name: "", canvas_width: 1080, canvas_height: 1080, background_color: "#FFFFFF", elements: [], created_at: "", updated_at: "" }), ...data, updated_at: new Date().toISOString() };
    }
    throw err;
  }
}

async function deleteTemplateApi(id: string): Promise<void> {
  try {
    await apiRequest(`/creative/templates/${id}`, { method: "DELETE" });
  } catch (err) {
    if (err instanceof ApiRequestError && err.status === 404) { await delay(300); return; }
    throw err;
  }
}

async function duplicateTemplateApi(id: string, data: DuplicateTemplatePayload): Promise<CreativeTemplate> {
  try {
    return await apiRequest<CreativeTemplate>(`/creative/templates/${id}/duplicate`, {
      method: "POST",
      body: JSON.stringify(data),
    });
  } catch (err) {
    if (err instanceof ApiRequestError && err.status === 404) {
      await delay(400);
      const mock = mockCreativeTemplates.find((t) => t.id === id);
      return { ...(mock ?? { id: "", subaccount_id: 1, name: "", canvas_width: 1080, canvas_height: 1080, background_color: "#FFFFFF", elements: [], created_at: "", updated_at: "" }), id: `tpl_${Date.now()}`, name: data.new_name, created_at: new Date().toISOString(), updated_at: new Date().toISOString() };
    }
    throw err;
  }
}

async function previewTemplateApi(id: string, data: PreviewTemplatePayload): Promise<PreviewTemplateResponse> {
  try {
    return await apiRequest<PreviewTemplateResponse>(`/creative/templates/${id}/preview`, {
      method: "POST",
      body: JSON.stringify(data),
    });
  } catch (err) {
    if (err instanceof ApiRequestError && err.status === 404) {
      await delay(500);
      const mock = mockCreativeTemplates.find((t) => t.id === id);
      return { template_id: id, rendered_elements: mock?.elements ?? [] };
    }
    throw err;
  }
}

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

export function useCreativeTemplates() {
  const queryClient = useQueryClient();

  const { data, isLoading, error } = useQuery<CreativeTemplatesResponse>({
    queryKey: TEMPLATES_KEY,
    queryFn: fetchTemplates,
  });

  const deleteMutation = useMutation({
    mutationFn: deleteTemplateApi,
    onSuccess: () => { void queryClient.invalidateQueries({ queryKey: TEMPLATES_KEY }); },
  });

  const duplicateMutation = useMutation({
    mutationFn: ({ id, newName }: { id: string; newName: string }) => duplicateTemplateApi(id, { new_name: newName }),
    onSuccess: () => { void queryClient.invalidateQueries({ queryKey: TEMPLATES_KEY }); },
  });

  const createMutation = useMutation({
    mutationFn: createTemplateApi,
    onSuccess: () => { void queryClient.invalidateQueries({ queryKey: TEMPLATES_KEY }); },
  });

  return {
    templates: data?.items ?? [],
    isLoading,
    error: error instanceof Error ? error.message : null,
    createTemplate: (data: CreateTemplatePayload) => createMutation.mutateAsync(data),
    deleteTemplate: (id: string) => deleteMutation.mutateAsync(id),
    duplicateTemplate: (id: string, newName: string) => duplicateMutation.mutateAsync({ id, newName }),
    previewTemplate: (id: string, data: PreviewTemplatePayload) => previewTemplateApi(id, data),
    isCreating: createMutation.isPending,
    isDeleting: deleteMutation.isPending,
  };
}

export function useCreativeTemplate(id: string) {
  const { data, isLoading, error } = useQuery<CreativeTemplate>({
    queryKey: TEMPLATE_KEY(id),
    queryFn: () => fetchTemplate(id),
    enabled: id.length > 0,
  });

  return {
    template: data ?? null,
    isLoading,
    error: error instanceof Error ? error.message : null,
  };
}
