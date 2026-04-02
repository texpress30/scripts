"use client";

import { useState, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, RefreshCw, Trash2, Loader2, Clock } from "lucide-react";
import { SourceTypeIcon } from "@/components/feed-management/SourceTypeIcon";
import { FeedSourceStatusBadge } from "@/components/feed-management/FeedSourceStatusBadge";
import { ImportHistoryTable } from "@/components/feed-management/ImportHistoryTable";
import { SyncScheduleSelector } from "@/components/feed-management/SyncScheduleSelector";
import { useFeedSource, useFeedImports, useFeedSources } from "@/lib/hooks/useFeedSources";
import { useFeedManagement } from "@/lib/contexts/FeedManagementContext";
import type { SyncSchedule } from "@/lib/types/feed-management";

function formatDate(value: string | null): string {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString();
}

function timeAgo(value: string | null): string {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  const seconds = Math.floor((Date.now() - date.getTime()) / 1000);
  if (seconds < 60) return "just now";
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

export default function SourceDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const sourceId = params.id;
  const { selectedId } = useFeedManagement();
  const { source, isLoading, error, refetch: refetchSource } = useFeedSource(selectedId, sourceId);
  const { imports, isLoading: importsLoading, refetch: refetchImports, hasPendingSync } = useFeedImports(selectedId, sourceId);
  const { syncSource, deleteSource, updateSchedule, isSyncing, isDeleting } = useFeedSources(selectedId);
  const [syncTriggered, setSyncTriggered] = useState(false);
  const [scheduleSaving, setScheduleSaving] = useState(false);

  const isActivelySyncing = syncTriggered || hasPendingSync;

  const handleSync = useCallback(async () => {
    setSyncTriggered(true);
    try {
      await syncSource(sourceId);
    } catch {
      setSyncTriggered(false);
    }
    // Polling will detect completion and reset
  }, [syncSource, sourceId]);

  // When polling detects sync completed, reset and refresh
  const handleSyncCompleted = useCallback(() => {
    if (syncTriggered && !hasPendingSync) {
      setSyncTriggered(false);
      void refetchSource();
    }
  }, [syncTriggered, hasPendingSync, refetchSource]);

  // Call on each render to check
  if (syncTriggered && !hasPendingSync && imports.length > 0) {
    setTimeout(() => {
      setSyncTriggered(false);
      void refetchSource();
      void refetchImports();
    }, 500);
  }

  async function handleScheduleChange(schedule: SyncSchedule) {
    setScheduleSaving(true);
    try {
      await updateSchedule(sourceId, schedule);
      void refetchSource();
    } finally {
      setScheduleSaving(false);
    }
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-16">
        <Loader2 className="h-6 w-6 animate-spin text-slate-400" />
      </div>
    );
  }

  if (error || !source) {
    return (
      <div className="py-8">
        <Link href="/agency/feed-management/sources" className="mb-4 inline-flex items-center gap-1 text-sm text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-300">
          <ArrowLeft className="h-4 w-4" />
          Înapoi la surse
        </Link>
        <p className="text-red-600">{error ?? "Sursa nu a fost găsită."}</p>
      </div>
    );
  }

  // Compute product count from latest completed import if available
  const latestCompleted = imports.find((i) => i.status === "completed");
  const productCount = (latestCompleted?.imported_products ?? latestCompleted?.total_products ?? source.product_count ?? 0);
  const lastSync = latestCompleted?.completed_at ?? latestCompleted?.started_at ?? source.last_sync;

  return (
    <>
      <Link href="/agency/feed-management/sources" className="mb-4 inline-flex items-center gap-1 text-sm text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-300">
        <ArrowLeft className="h-4 w-4" />
        Înapoi la surse
      </Link>

      <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-3">
          <SourceTypeIcon type={source.source_type} className="scale-150" />
          <div>
            <h1 className="text-xl font-semibold text-slate-900 dark:text-slate-100">{source.name}</h1>
            <div className="mt-1 flex items-center gap-2">
              <SourceTypeIcon type={source.source_type} showLabel />
              <span className="text-slate-300 dark:text-slate-600">|</span>
              <FeedSourceStatusBadge status={source.status} />
            </div>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => void handleSync()}
            disabled={isSyncing || isActivelySyncing}
            className="wm-btn-primary gap-2"
          >
            {isActivelySyncing ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <RefreshCw className="h-4 w-4" />
            )}
            {isActivelySyncing ? "Syncing..." : "Sync Now"}
          </button>
          <button type="button" onClick={() => { if (window.confirm("Sigur vrei să ștergi această sursă? Acțiunea este ireversibilă.")) { void deleteSource(sourceId).then(() => router.push("/agency/feed-management/sources")); } }} disabled={isDeleting} className="inline-flex items-center gap-2 rounded-lg border border-red-200 bg-white px-4 py-2 text-sm font-medium text-red-600 transition hover:bg-red-50 dark:border-red-800 dark:bg-slate-900 dark:text-red-400 dark:hover:bg-red-900/20">
            {isDeleting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Trash2 className="h-4 w-4" />}
            Delete
          </button>
        </div>
      </div>

      {/* Sync progress banner */}
      {isActivelySyncing && (
        <div className="mb-4 flex items-center gap-3 rounded-lg border border-blue-200 bg-blue-50 px-4 py-3 text-sm text-blue-700 dark:border-blue-800 dark:bg-blue-900/20 dark:text-blue-400">
          <Loader2 className="h-4 w-4 animate-spin" />
          <span>Sincronizare în curs... Produsele se importă din sursă.</span>
        </div>
      )}

      <section className="wm-card mb-6 p-6">
        <h2 className="mb-4 text-base font-semibold text-slate-900 dark:text-slate-100">Configuration</h2>
        <dl className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <DetailRow label="Source Type"><SourceTypeIcon type={source.source_type} showLabel /></DetailRow>
          <DetailRow label="Status"><FeedSourceStatusBadge status={source.status} /></DetailRow>
          {source.url ? (<DetailRow label="URL"><span className="break-all text-sm text-slate-700 dark:text-slate-300">{source.url}</span></DetailRow>) : null}
          <DetailRow label="Products">
            <span className="text-sm font-medium text-slate-900 dark:text-slate-100">{productCount.toLocaleString()}</span>
          </DetailRow>
          <DetailRow label="Last Sync">
            <div className="flex items-center gap-1.5">
              <Clock className="h-3.5 w-3.5 text-slate-400" />
              <span className="text-sm text-slate-700 dark:text-slate-300" title={formatDate(lastSync)}>{timeAgo(lastSync)}</span>
            </div>
          </DetailRow>
          <DetailRow label="Created"><span className="text-sm text-slate-700 dark:text-slate-300">{formatDate(source.created_at)}</span></DetailRow>
        </dl>

        <div className="mt-4 border-t border-slate-100 pt-4 dark:border-slate-800">
          <SyncScheduleSelector
            currentSchedule={source.sync_schedule ?? "manual"}
            nextSync={source.next_scheduled_sync}
            onScheduleChange={(s) => void handleScheduleChange(s)}
            isSaving={scheduleSaving}
          />
        </div>
      </section>

      <section className="wm-card overflow-hidden">
        <div className="border-b border-slate-200 px-6 py-4 dark:border-slate-700">
          <h2 className="text-base font-semibold text-slate-900 dark:text-slate-100">Sync History</h2>
        </div>
        {importsLoading ? (
          <div className="flex items-center justify-center py-8">
            <Loader2 className="h-5 w-5 animate-spin text-slate-400" />
          </div>
        ) : (
          <ImportHistoryTable imports={imports} />
        )}
      </section>
    </>
  );
}

function DetailRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <dt className="text-xs font-medium text-slate-500 dark:text-slate-400">{label}</dt>
      <dd className="mt-1">{children}</dd>
    </div>
  );
}
