"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiRequest } from "@/lib/api";

/**
 * Shuffle-pool hook.
 *
 * The template editor needs an instant "swap the sample product" experience,
 * so we can't download/process a random photo each time the user clicks the
 * Shuffle button. Instead the backend returns a pre-filtered pool of products
 * that (a) already have a ready background-removed cutout and (b) match the
 * current template's treatment filters.
 *
 * The pool is refreshed every 5s while it's not full — that way as the
 * priming worker finishes each cutout, the pool grows and the user sees an
 * increasing "ready count" chip in the editor top bar without hard-refreshing.
 */

export interface ShufflePoolProduct {
  id?: string;
  product_id?: string;
  title?: string;
  image_src?: string | null;
  /**
   * Background-removed PNG URL for this product's primary image. Populated
   * by the backend when the corresponding ``image_cutouts`` row is ``ready``
   * and the media_files lookup resolved a storage URL. When present, the
   * canvas editor should use this instead of ``image_src`` for any layer
   * bound to ``{{image_src}}``.
   */
  cutout_url?: string | null;
  images?: unknown;
  [key: string]: unknown;
}

export interface ShufflePoolResponse {
  template_id: string;
  output_feed_id: string | null;
  pool: ShufflePoolProduct[];
  pool_ready_count: number;
  total_products: number;
}

const SHUFFLE_POOL_KEY = (templateId: string) => ["shuffle-pool", templateId] as const;

async function fetchShufflePool(templateId: string, limit: number): Promise<ShufflePoolResponse> {
  return apiRequest<ShufflePoolResponse>(
    `/creative/templates/${templateId}/shuffle-pool?limit=${limit}`,
    { cache: "no-store" },
  );
}

export function useShufflePool(
  templateId: string | null,
  options: { limit?: number; enabled?: boolean } = {},
) {
  const { limit = 50, enabled = true } = options;

  return useQuery<ShufflePoolResponse>({
    queryKey: SHUFFLE_POOL_KEY(templateId ?? ""),
    queryFn: () => fetchShufflePool(templateId!, limit),
    enabled: !!templateId && enabled,
    // Poll while the pool is still filling up. Once it hits the target size
    // or matches the total feed, stop polling — no point hammering the API
    // for an already-complete pool.
    refetchInterval: (query) => {
      const data = query.state.data as ShufflePoolResponse | undefined;
      if (!data) return 5_000;
      if (data.pool_ready_count >= limit) return false;
      if (data.total_products > 0 && data.pool_ready_count >= data.total_products) return false;
      return 5_000;
    },
    refetchIntervalInBackground: false,
    staleTime: 2_000,
  });
}

/**
 * POST /creative/templates/{id}/prime-cutouts
 *
 * Fire-and-forget mutation called when the template editor mounts. The
 * backend enqueues background-removal tasks for the top-N products of the
 * linked feed so that by the time the user clicks Shuffle a few seconds
 * later, the pool already has candidates.
 *
 * Idempotent on the backend side — safe to call on every editor open.
 */
export function usePrimeCutouts() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ templateId, limit = 200 }: { templateId: string; limit?: number }) => {
      return apiRequest<{ enqueued: number; feed_source_id?: string; reason?: string }>(
        `/creative/templates/${templateId}/prime-cutouts?limit=${limit}`,
        { method: "POST" },
      );
    },
    onSuccess: (_data, vars) => {
      // Trigger an immediate re-fetch of the pool so the ready count starts
      // climbing without waiting for the 5s polling interval.
      queryClient.invalidateQueries({ queryKey: SHUFFLE_POOL_KEY(vars.templateId) });
    },
  });
}
