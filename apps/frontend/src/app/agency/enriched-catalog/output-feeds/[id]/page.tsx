"use client";

import { useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { ArrowLeft, Copy, ExternalLink, Eye, Loader2, Play, Plus, RefreshCw, Layers } from "lucide-react";
import { useOutputFeed, useRenderStatus, useFeedStats, fetchPublicUrl, regenerateToken, setRefreshSchedule } from "@/lib/hooks/useOutputFeeds";
import { useTreatments } from "@/lib/hooks/useTreatments";
import { useCreativeTemplates } from "@/lib/hooks/useCreativeTemplates";
import { useFeedManagement } from "@/lib/contexts/FeedManagementContext";
import { TreatmentEditor } from "@/components/enriched-catalog/TreatmentEditor";
import { apiRequest } from "@/lib/api";

export default function OutputFeedDetailPage() {
  const params = useParams();
  const router = useRouter();
  const feedId = params.id as string;
  const { selectedId } = useFeedManagement();

  const { data: feed, isLoading: feedLoading } = useOutputFeed(feedId);
  const { treatments, isLoading: treatmentsLoading, create: createTreatment, isCreating, remove: removeTreatment } = useTreatments(feedId);
  const { templates } = useCreativeTemplates(selectedId);
  const { data: stats } = useFeedStats(feedId);
  const [showRenderStatus, setShowRenderStatus] = useState(false);
  const { data: renderStatus } = useRenderStatus(feedId, showRenderStatus);

  const [showTreatmentEditor, setShowTreatmentEditor] = useState(false);
  const [publicUrl, setPublicUrl] = useState<string | null>(null);
  const [generating, setGenerating] = useState(false);
  const [showMultiFormat, setShowMultiFormat] = useState(false);
  const [selectedFormatIds, setSelectedFormatIds] = useState<Set<string>>(new Set());
  const [webhookUrl, setWebhookUrl] = useState("");
  const [multiFormatGenerating, setMultiFormatGenerating] = useState(false);

  const handleGenerate = async () => {
    setGenerating(true);
    setShowRenderStatus(true);
    try {
      await apiRequest(`/creative/output-feeds/${feedId}/generate`, { method: "POST" });
    } catch (err) {
      console.error("Generate failed:", err);
    } finally {
      setGenerating(false);
    }
  };

  const handleMultiFormatRender = async () => {
    if (selectedFormatIds.size === 0) return;
    setMultiFormatGenerating(true);
    setShowRenderStatus(true);
    try {
      await apiRequest(`/creative/output-feeds/${feedId}/render-multi-format`, {
        method: "POST",
        body: JSON.stringify({
          template_ids: [...selectedFormatIds],
          products: [],
          webhook_url: webhookUrl.trim() || undefined,
        }),
      });
      setShowMultiFormat(false);
    } catch (err) {
      console.error("Multi-format render failed:", err);
      alert("Multi-format render failed. Check console for details.");
    } finally {
      setMultiFormatGenerating(false);
    }
  };

  const toggleFormatId = (id: string) => {
    setSelectedFormatIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const handleGetPublicUrl = async () => {
    try {
      const url = await fetchPublicUrl(feedId);
      setPublicUrl(url);
    } catch (err) {
      console.error("Failed to get public URL:", err);
    }
  };

  const handleRegenerateToken = async () => {
    try {
      const result = await regenerateToken(feedId);
      setPublicUrl(result.public_url);
    } catch (err) {
      console.error("Failed to regenerate token:", err);
    }
  };

  const handleSetSchedule = async (hours: number) => {
    try {
      await setRefreshSchedule(feedId, hours);
    } catch (err) {
      console.error("Failed to set schedule:", err);
    }
  };

  const handleDeleteTreatment = async (id: string) => {
    if (confirm("Delete this treatment?")) {
      await removeTreatment(id);
    }
  };

  if (feedLoading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <Loader2 className="h-6 w-6 animate-spin text-slate-400" />
      </div>
    );
  }

  if (!feed) {
    return (
      <div className="flex h-64 items-center justify-center text-sm text-slate-500">
        Output feed not found.
      </div>
    );
  }

  const STATUS_BADGE: Record<string, string> = {
    draft: "bg-slate-100 text-slate-600 dark:bg-slate-700 dark:text-slate-400",
    rendering: "bg-amber-100 text-amber-700 dark:bg-amber-900/20 dark:text-amber-400",
    published: "bg-green-100 text-green-700 dark:bg-green-900/20 dark:text-green-400",
    error: "bg-red-100 text-red-700 dark:bg-red-900/20 dark:text-red-400",
  };

  return (
    <div className="mx-auto max-w-3xl">
      <button
        onClick={() => router.push("/agency/enriched-catalog/output-feeds")}
        className="mb-4 flex items-center gap-1 text-sm text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-300"
      >
        <ArrowLeft className="h-4 w-4" /> Back to Output Feeds
      </button>

      {/* Header */}
      <div className="mb-6 flex items-start justify-between">
        <div>
          <h2 className="text-lg font-semibold text-slate-900 dark:text-slate-100">{feed.name}</h2>
          <div className="mt-1 flex items-center gap-2">
            <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${STATUS_BADGE[feed.status] || STATUS_BADGE.draft}`}>
              {feed.status}
            </span>
            <span className="text-xs text-slate-500 dark:text-slate-400">
              Format: {feed.feed_format.toUpperCase()}
            </span>
          </div>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => router.push(`/agency/enriched-catalog/output-feeds/${feedId}/preview`)}
            className="flex items-center gap-1.5 rounded-md border border-slate-200 px-3 py-1.5 text-sm text-slate-700 hover:bg-slate-50 dark:border-slate-600 dark:text-slate-300 dark:hover:bg-slate-700"
          >
            <Eye className="h-3.5 w-3.5" /> Preview
          </button>
          <button
            onClick={handleGenerate}
            disabled={generating}
            className="wm-btn-primary flex items-center gap-1.5 rounded-md px-4 py-1.5 text-sm font-medium text-white disabled:opacity-50"
          >
            {generating ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Play className="h-3.5 w-3.5" />}
            Generate Feed
          </button>
          <button
            onClick={() => setShowMultiFormat(true)}
            className="flex items-center gap-1.5 rounded-md border border-indigo-300 bg-indigo-50 px-3 py-1.5 text-sm font-medium text-indigo-700 hover:bg-indigo-100 dark:border-indigo-600 dark:bg-indigo-900/20 dark:text-indigo-400 dark:hover:bg-indigo-900/30"
          >
            <Layers className="h-3.5 w-3.5" /> Multi-Format
          </button>
        </div>
      </div>

      {/* Stats */}
      {stats && (
        <div className="mb-6 grid grid-cols-4 gap-4">
          {[
            { label: "Products", value: stats.products_count },
            { label: "Size", value: stats.file_size_bytes > 0 ? `${(stats.file_size_bytes / 1024).toFixed(1)} KB` : "-" },
            { label: "Refresh", value: `${stats.refresh_interval_hours}h` },
            { label: "Last Generated", value: stats.last_generated_at ? new Date(stats.last_generated_at).toLocaleDateString() : "Never" },
          ].map((s) => (
            <div key={s.label} className="rounded-lg border border-slate-200 bg-white p-3 text-center dark:border-slate-700 dark:bg-slate-800">
              <p className="text-lg font-semibold text-slate-900 dark:text-slate-100">{s.value}</p>
              <p className="text-xs text-slate-500 dark:text-slate-400">{s.label}</p>
            </div>
          ))}
        </div>
      )}

      {/* Render Status */}
      {showRenderStatus && renderStatus && renderStatus.status !== "no_jobs" && (
        <div className="mb-6 rounded-lg border border-slate-200 bg-white p-4 dark:border-slate-700 dark:bg-slate-800">
          <h3 className="mb-2 text-sm font-semibold text-slate-900 dark:text-slate-100">Render Progress</h3>
          <div className="mb-2 h-2 w-full overflow-hidden rounded-full bg-slate-100 dark:bg-slate-700">
            <div
              className="h-full rounded-full bg-indigo-500 transition-all"
              style={{
                width: `${renderStatus.total_products > 0 ? (renderStatus.rendered_products / renderStatus.total_products) * 100 : 0}%`,
              }}
            />
          </div>
          <p className="text-xs text-slate-500 dark:text-slate-400">
            {renderStatus.rendered_products} / {renderStatus.total_products} products rendered
            {renderStatus.errors.length > 0 && ` (${renderStatus.errors.length} errors)`}
          </p>
        </div>
      )}

      {/* Public URL */}
      <div className="mb-6 rounded-lg border border-slate-200 bg-white p-4 dark:border-slate-700 dark:bg-slate-800">
        <h3 className="mb-3 text-sm font-semibold text-slate-900 dark:text-slate-100">Public Feed URL</h3>
        {publicUrl ? (
          <div className="flex items-center gap-2">
            <code className="flex-1 rounded bg-slate-50 px-3 py-2 text-xs text-slate-700 dark:bg-slate-900 dark:text-slate-300">
              {publicUrl}
            </code>
            <button
              onClick={() => navigator.clipboard.writeText(publicUrl)}
              className="rounded p-1.5 text-slate-400 hover:text-slate-600"
              title="Copy URL"
            >
              <Copy className="h-4 w-4" />
            </button>
            <a
              href={publicUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="rounded p-1.5 text-slate-400 hover:text-slate-600"
            >
              <ExternalLink className="h-4 w-4" />
            </a>
          </div>
        ) : (
          <button
            onClick={handleGetPublicUrl}
            className="flex items-center gap-1.5 text-sm text-indigo-600 hover:text-indigo-700 dark:text-indigo-400"
          >
            <ExternalLink className="h-3.5 w-3.5" /> Get Public URL
          </button>
        )}
        <div className="mt-3 flex gap-2">
          <button
            onClick={handleRegenerateToken}
            className="flex items-center gap-1 text-xs text-slate-500 hover:text-slate-700 dark:text-slate-400"
          >
            <RefreshCw className="h-3 w-3" /> Regenerate Token
          </button>
          <select
            defaultValue={feed.refresh_interval_hours}
            onChange={(e) => handleSetSchedule(Number(e.target.value))}
            className="mcc-input rounded border px-2 py-0.5 text-xs"
          >
            <option value={1}>Refresh: 1h</option>
            <option value={6}>Refresh: 6h</option>
            <option value={12}>Refresh: 12h</option>
            <option value={24}>Refresh: 24h</option>
            <option value={48}>Refresh: 48h</option>
          </select>
        </div>
      </div>

      {/* Treatments */}
      <div className="rounded-lg border border-slate-200 bg-white p-4 dark:border-slate-700 dark:bg-slate-800">
        <div className="mb-4 flex items-center justify-between">
          <h3 className="text-sm font-semibold text-slate-900 dark:text-slate-100">
            Treatments ({treatments.length})
          </h3>
          <button
            onClick={() => setShowTreatmentEditor(true)}
            className="flex items-center gap-1 text-sm text-indigo-600 hover:text-indigo-700 dark:text-indigo-400"
          >
            <Plus className="h-3.5 w-3.5" /> Add Treatment
          </button>
        </div>

        {showTreatmentEditor && (
          <div className="mb-4">
            <TreatmentEditor
              outputFeedId={feedId}
              templates={templates}
              onSave={async (payload) => {
                await createTreatment(payload);
                setShowTreatmentEditor(false);
              }}
              onCancel={() => setShowTreatmentEditor(false)}
              isSaving={isCreating}
            />
          </div>
        )}

        {treatmentsLoading ? (
          <div className="flex h-20 items-center justify-center">
            <Loader2 className="h-5 w-5 animate-spin text-slate-400" />
          </div>
        ) : treatments.length === 0 ? (
          <p className="py-6 text-center text-sm text-slate-400 dark:text-slate-500">
            No treatments yet. Add one to define how products are matched to templates.
          </p>
        ) : (
          <div className="space-y-2">
            {treatments.map((t) => {
              const tpl = templates.find((tp) => tp.id === t.template_id);
              return (
                <div key={t.id} className="flex items-center justify-between rounded-md border border-slate-100 px-3 py-2 dark:border-slate-700">
                  <div>
                    <span className="text-sm font-medium text-slate-900 dark:text-slate-100">{t.name}</span>
                    {t.is_default && (
                      <span className="ml-2 rounded bg-indigo-100 px-1.5 py-0.5 text-xs text-indigo-600 dark:bg-indigo-900/20 dark:text-indigo-400">
                        default
                      </span>
                    )}
                    <p className="text-xs text-slate-500 dark:text-slate-400">
                      Template: {tpl?.name || t.template_id.slice(0, 8)} | {t.filters.length} filter{t.filters.length !== 1 ? "s" : ""} | Priority: {t.priority}
                    </p>
                  </div>
                  <button
                    onClick={() => handleDeleteTreatment(t.id)}
                    className="text-xs text-red-500 hover:text-red-600"
                  >
                    Remove
                  </button>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Multi-format generation modal */}
      {showMultiFormat && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="w-full max-w-lg rounded-lg bg-white p-6 shadow-xl dark:bg-slate-800">
            <h3 className="mb-4 text-lg font-semibold text-slate-900 dark:text-slate-100">
              Multi-Format Generation
            </h3>
            <p className="mb-4 text-sm text-slate-500 dark:text-slate-400">
              Render all products across multiple template formats in a single batch.
              Select which templates/formats to include.
            </p>

            <label className="mb-2 block text-sm font-medium text-slate-700 dark:text-slate-300">
              Select Templates
            </label>
            <div className="mb-4 max-h-48 space-y-2 overflow-y-auto rounded-md border border-slate-200 p-2 dark:border-slate-600">
              {templates.length === 0 ? (
                <p className="py-2 text-center text-xs text-slate-400">No templates available</p>
              ) : (
                templates.map((t) => (
                  <label
                    key={t.id}
                    className={`flex cursor-pointer items-center gap-3 rounded-md border px-3 py-2 text-sm transition ${
                      selectedFormatIds.has(t.id)
                        ? "border-indigo-500 bg-indigo-50 dark:border-indigo-400 dark:bg-indigo-900/20"
                        : "border-slate-100 hover:border-slate-200 dark:border-slate-700 dark:hover:border-slate-600"
                    }`}
                  >
                    <input
                      type="checkbox"
                      checked={selectedFormatIds.has(t.id)}
                      onChange={() => toggleFormatId(t.id)}
                      className="accent-indigo-600"
                    />
                    <span className="flex-1 text-slate-700 dark:text-slate-300">{t.name}</span>
                    <span className="text-xs text-slate-400">
                      {t.canvas_width}x{t.canvas_height}
                    </span>
                  </label>
                ))
              )}
            </div>

            {templates.length > 0 && (
              <button
                onClick={() => {
                  if (selectedFormatIds.size === templates.length) {
                    setSelectedFormatIds(new Set());
                  } else {
                    setSelectedFormatIds(new Set(templates.map((t) => t.id)));
                  }
                }}
                className="mb-4 text-xs text-indigo-600 hover:text-indigo-700 dark:text-indigo-400"
              >
                {selectedFormatIds.size === templates.length ? "Deselect All" : "Select All"}
              </button>
            )}

            <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">
              Webhook URL <span className="font-normal text-slate-400">(optional)</span>
            </label>
            <input
              type="url"
              value={webhookUrl}
              onChange={(e) => setWebhookUrl(e.target.value)}
              placeholder="https://your-app.com/webhook/render-complete"
              className="mcc-input mb-2 w-full rounded-md border px-3 py-2 text-sm"
            />
            <p className="mb-6 text-xs text-slate-400 dark:text-slate-500">
              Receives a POST notification when the batch render completes.
            </p>

            {selectedFormatIds.size > 0 && (
              <div className="mb-4 rounded-md bg-indigo-50 px-3 py-2 text-xs text-indigo-700 dark:bg-indigo-900/20 dark:text-indigo-400">
                Will render products across {selectedFormatIds.size} template{selectedFormatIds.size > 1 ? "s" : ""}.
              </div>
            )}

            <div className="flex justify-end gap-3">
              <button
                onClick={() => { setShowMultiFormat(false); setSelectedFormatIds(new Set()); setWebhookUrl(""); }}
                className="rounded-md px-4 py-2 text-sm text-slate-600 hover:bg-slate-100 dark:text-slate-400 dark:hover:bg-slate-700"
              >
                Cancel
              </button>
              <button
                onClick={handleMultiFormatRender}
                disabled={selectedFormatIds.size === 0 || multiFormatGenerating}
                className="wm-btn-primary inline-flex items-center gap-2 rounded-md px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
              >
                {multiFormatGenerating && <Loader2 className="h-4 w-4 animate-spin" />}
                Render {selectedFormatIds.size} Format{selectedFormatIds.size !== 1 ? "s" : ""}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
