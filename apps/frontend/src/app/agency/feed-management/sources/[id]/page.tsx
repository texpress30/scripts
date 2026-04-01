"use client";

import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, RefreshCw, Trash2, Loader2 } from "lucide-react";
import { SourceTypeIcon } from "@/components/feed-management/SourceTypeIcon";
import { FeedSourceStatusBadge } from "@/components/feed-management/FeedSourceStatusBadge";
import { ImportHistoryTable } from "@/components/feed-management/ImportHistoryTable";
import { useFeedSource, useFeedImports, useFeedSources } from "@/lib/hooks/useFeedSources";

function formatDate(value: string | null): string {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString();
}

export default function SourceDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const sourceId = Number(params.id);
  const { source, isLoading, error } = useFeedSource(sourceId);
  const { imports, isLoading: importsLoading } = useFeedImports(sourceId);
  const { syncSource, deleteSource, isSyncing, isDeleting } = useFeedSources();

  async function handleSync() {
    await syncSource(sourceId);
  }

  async function handleDelete() {
    if (!window.confirm("Sigur vrei să ștergi această sursă? Acțiunea este ireversibilă.")) return;
    await deleteSource(sourceId);
    router.push("/agency/feed-management/sources");
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
          <button type="button" onClick={() => void handleSync()} disabled={isSyncing} className="wm-btn-primary gap-2">
            {isSyncing ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
            Sync Now
          </button>
          <button type="button" onClick={() => void handleDelete()} disabled={isDeleting} className="inline-flex items-center gap-2 rounded-lg border border-red-200 bg-white px-4 py-2 text-sm font-medium text-red-600 transition hover:bg-red-50 dark:border-red-800 dark:bg-slate-900 dark:text-red-400 dark:hover:bg-red-900/20">
            {isDeleting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Trash2 className="h-4 w-4" />}
            Delete
          </button>
        </div>
      </div>

      <section className="wm-card mb-6 p-6">
        <h2 className="mb-4 text-base font-semibold text-slate-900 dark:text-slate-100">Configuration</h2>
        <dl className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <DetailRow label="Source Type"><SourceTypeIcon type={source.source_type} showLabel /></DetailRow>
          <DetailRow label="Status"><FeedSourceStatusBadge status={source.status} /></DetailRow>
          {source.url ? (<DetailRow label="URL"><span className="break-all text-sm text-slate-700 dark:text-slate-300">{source.url}</span></DetailRow>) : null}
          <DetailRow label="Products"><span className="text-sm text-slate-700 dark:text-slate-300">{source.product_count.toLocaleString()}</span></DetailRow>
          <DetailRow label="Last Sync"><span className="text-sm text-slate-700 dark:text-slate-300">{formatDate(source.last_sync)}</span></DetailRow>
          <DetailRow label="Created"><span className="text-sm text-slate-700 dark:text-slate-300">{formatDate(source.created_at)}</span></DetailRow>
        </dl>
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
