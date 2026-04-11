"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiRequest } from "@/lib/api";

/**
 * Cutouts dashboard + bulk-batch hooks.
 *
 * - {@link useCutoutBatch}: polls a single cutout batch job until it reaches
 *   a terminal state so the UI can render a progress bar during the first
 *   bulk run on a new feed.
 * - {@link useEnqueueCutoutBatch}: kicks off that first bulk run.
 * - {@link useCutoutsList}: lists recent cutouts for a client so the admin
 *   UI can surface counts / status chips without re-querying Mongo.
 */

export interface CutoutBatchJob {
  job_id: number;
  subaccount_id: number;
  client_id: number;
  feed_source_id: string | null;
  kind: "bulk" | "prime" | "delta";
  total: number;
  done: number;
  failed: number;
  status: "pending" | "in_progress" | "completed" | "failed";
  error: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface CutoutRow {
  id: number;
  source_hash: string;
  source_url: string;
  media_id: string | null;
  model: string;
  status: "pending" | "in_progress" | "ready" | "failed";
  has_native_alpha: boolean;
  cutout_width: number;
  cutout_height: number;
  error: string | null;
  last_referenced_at: string | null;
  created_at: string | null;
  updated_at: string | null;
}

const BATCH_KEY = (jobId: number) => ["cutout-batch", jobId] as const;
const LIST_KEY = (subId: number) => ["cutouts-list", subId] as const;

function isTerminal(status: string | undefined): boolean {
  return status === "completed" || status === "failed";
}

export function useCutoutBatch(jobId: number | null) {
  return useQuery<CutoutBatchJob>({
    queryKey: BATCH_KEY(jobId ?? 0),
    queryFn: () => apiRequest<CutoutBatchJob>(`/cutouts/batch/${jobId}`, { cache: "no-store" }),
    enabled: jobId !== null && jobId > 0,
    // Poll aggressively while the batch is running; stop as soon as it
    // hits a terminal state so we don't hammer the API for nothing.
    refetchInterval: (query) => (isTerminal(query.state.data?.status) ? false : 2_000),
    refetchIntervalInBackground: false,
  });
}

export function useEnqueueCutoutBatch() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (payload: {
      subaccount_id: number;
      feed_source_id: string;
      limit?: number;
    }) => {
      return apiRequest<{ job_id: number; enqueued: number }>(`/cutouts/batch`, {
        method: "POST",
        body: JSON.stringify(payload),
      });
    },
    onSuccess: (data, vars) => {
      queryClient.invalidateQueries({ queryKey: LIST_KEY(vars.subaccount_id) });
      queryClient.setQueryData(BATCH_KEY(data.job_id), {
        job_id: data.job_id,
        subaccount_id: vars.subaccount_id,
        client_id: vars.subaccount_id,
        feed_source_id: vars.feed_source_id,
        kind: "bulk",
        total: data.enqueued,
        done: 0,
        failed: 0,
        status: "in_progress",
        error: null,
        created_at: null,
        updated_at: null,
      } satisfies CutoutBatchJob);
    },
  });
}

export function useCutoutsList(subaccountId: number | null, limit: number = 200) {
  return useQuery<{ items: CutoutRow[] }>({
    queryKey: LIST_KEY(subaccountId ?? 0),
    queryFn: () =>
      apiRequest<{ items: CutoutRow[] }>(
        `/cutouts?subaccount_id=${subaccountId}&limit=${limit}`,
        { cache: "no-store" },
      ),
    enabled: subaccountId !== null && subaccountId > 0,
    staleTime: 10_000,
  });
}
