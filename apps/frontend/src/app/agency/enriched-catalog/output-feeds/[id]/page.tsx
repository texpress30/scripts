"use client";

import { useState, useRef, useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  ArrowLeft,
  Copy,
  ExternalLink,
  Loader2,
  Play,
  Plus,
  RefreshCw,
  Layers,
  Settings,
  MoreHorizontal,
  Filter,
  Link2,
  Calendar,
  Clock,
  Package,
} from "lucide-react";
import {
  useOutputFeed,
  useRenderStatus,
  useFeedStats,
  fetchPublicUrl,
  regenerateToken,
  setRefreshSchedule,
} from "@/lib/hooks/useOutputFeeds";
import { useTreatments } from "@/lib/hooks/useTreatments";
import { useCreativeTemplates } from "@/lib/hooks/useCreativeTemplates";
import { useFeedManagement } from "@/lib/contexts/FeedManagementContext";
import { TreatmentEditor } from "@/components/enriched-catalog/TreatmentEditor";
import { apiRequest } from "@/lib/api";

// ---------------------------------------------------------------------------
// Design row context menu
// ---------------------------------------------------------------------------

function DesignContextMenu({
  onClose,
  onRemove,
}: {
  onClose: () => void;
  onRemove: () => void;
}) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) onClose();
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [onClose]);

  return (
    <div
      ref={ref}
      className="absolute right-0 top-full z-30 mt-1 w-48 overflow-hidden rounded-lg border border-slate-200 bg-white py-1 shadow-lg dark:border-slate-600 dark:bg-slate-800"
    >
      {["Add To Board", "Clone", "Rename", "Archive"].map((label) => (
        <button
          key={label}
          onClick={onClose}
          className="flex w-full items-center px-3 py-2 text-left text-sm text-slate-700 hover:bg-slate-50 dark:text-slate-200 dark:hover:bg-slate-700"
        >
          {label}
        </button>
      ))}
      <div className="my-1 border-t border-slate-200 dark:border-slate-700" />
      <button
        onClick={() => { onRemove(); onClose(); }}
        className="flex w-full items-center px-3 py-2 text-left text-sm text-red-500 hover:bg-red-50 dark:hover:bg-red-900/20"
      >
        Remove from treatment
      </button>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function OutputFeedDetailPage() {
  const params = useParams();
  const router = useRouter();
  const feedId = params.id as string;
  const { selectedId } = useFeedManagement();

  const { data: feed, isLoading: feedLoading } = useOutputFeed(feedId);
  const {
    treatments, isLoading: treatmentsLoading,
    create: createTreatment, isCreating,
    remove: removeTreatment,
  } = useTreatments(feedId);
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
  const [metaCatalogSync, setMetaCatalogSync] = useState(false);
  const [openMenu, setOpenMenu] = useState<string | null>(null);
  const [copiedUrl, setCopiedUrl] = useState(false);

  useEffect(() => {
    if (!feedId) return;
    fetchPublicUrl(feedId).then(setPublicUrl).catch(() => {});
  }, [feedId]);

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
        body: JSON.stringify({ template_ids: [...selectedFormatIds], products: [], webhook_url: webhookUrl.trim() || undefined }),
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
    setSelectedFormatIds((prev) => { const n = new Set(prev); if (n.has(id)) n.delete(id); else n.add(id); return n; });
  };

  const handleDeleteTreatment = async (id: string) => {
    if (confirm("Delete this treatment?")) await removeTreatment(id);
  };

  const handleCopyFeedUrl = () => {
    if (!publicUrl) return;
    navigator.clipboard.writeText(publicUrl);
    setCopiedUrl(true);
    setTimeout(() => setCopiedUrl(false), 2000);
  };

  if (feedLoading) {
    return <div className="flex h-64 items-center justify-center"><Loader2 className="h-6 w-6 animate-spin text-slate-400" /></div>;
  }
  if (!feed) {
    return <div className="flex h-64 items-center justify-center text-sm text-slate-500">Output feed not found.</div>;
  }

  const treatmentMode = (feed as unknown as Record<string, unknown>).treatment_mode as string || "single";
  const totalSKUs = stats?.products_count ?? 0;
  const lastUpdated = stats?.last_generated_at ? new Date(stats.last_generated_at).toLocaleDateString() : "N/A";

  return (
    <div>
      <button
        onClick={() => router.push("/agency/enriched-catalog/output-feeds")}
        className="mb-4 flex items-center gap-1 text-sm text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-300"
      >
        <ArrowLeft className="h-4 w-4" /> Back to Output Feeds
      </button>

      {/* Two-column layout */}
      <div className="flex gap-6">
        {/* Main content */}
        <div className="min-w-0 flex-1">
          {/* Header */}
          <div className="mb-1 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <h2 className="text-lg font-semibold text-slate-900 dark:text-slate-100">{feed.name}</h2>
              <span className="rounded bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-600 dark:bg-slate-700 dark:text-slate-400">
                {treatmentMode === "multi" ? `Multi-treatment ${treatments.length}` : "Single treatment"}
              </span>
            </div>
            <button
              onClick={() => router.push(`/agency/enriched-catalog/output-feeds/${feedId}/preview`)}
              className="rounded p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-600 dark:hover:bg-slate-700"
              title="Settings"
            >
              <Settings className="h-4 w-4" />
            </button>
          </div>

          <p className="mb-5 text-[10px] font-medium uppercase tracking-wider text-amber-600 dark:text-amber-400">
            Overlapping SKUs are replaced by designs further to the bottom
          </p>

          {/* Render progress */}
          {showRenderStatus && renderStatus && renderStatus.status !== "no_jobs" && (
            <div className="mb-4 rounded-lg border border-slate-200 bg-white p-3 dark:border-slate-700 dark:bg-slate-800">
              <div className="mb-1.5 flex items-center justify-between text-xs text-slate-500">
                <span>Render Progress</span>
                <span>{renderStatus.rendered_products} / {renderStatus.total_products}{renderStatus.errors.length > 0 && ` (${renderStatus.errors.length} errors)`}</span>
              </div>
              <div className="h-2 w-full overflow-hidden rounded-full bg-slate-100 dark:bg-slate-700">
                <div className="h-full rounded-full bg-indigo-500 transition-all" style={{ width: `${renderStatus.total_products > 0 ? (renderStatus.rendered_products / renderStatus.total_products) * 100 : 0}%` }} />
              </div>
            </div>
          )}

          {/* Treatments */}
          <div className="space-y-4">
            {treatmentsLoading ? (
              <div className="flex h-32 items-center justify-center"><Loader2 className="h-5 w-5 animate-spin text-slate-400" /></div>
            ) : treatments.length === 0 && !showTreatmentEditor ? (
              <div className="rounded-lg border border-slate-200 bg-white py-10 text-center dark:border-slate-700 dark:bg-slate-800">
                <p className="text-sm text-slate-400">No treatments yet. Add one to define how products are matched to templates.</p>
              </div>
            ) : (
              treatments.map((treatment) => {
                const tpl = templates.find((tp) => tp.id === treatment.template_id);
                return (
                  <div key={treatment.id} className="rounded-lg border border-slate-200 bg-white dark:border-slate-700 dark:bg-slate-800">
                    {/* Treatment header */}
                    <div className="flex items-center justify-between border-b border-slate-100 px-4 py-3 dark:border-slate-700">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-semibold text-slate-900 dark:text-slate-100">{treatment.name}</span>
                        {treatment.is_default && (
                          <span className="rounded bg-indigo-100 px-1.5 py-0.5 text-[10px] font-medium text-indigo-600 dark:bg-indigo-900/20 dark:text-indigo-400">default</span>
                        )}
                      </div>
                      <div className="flex items-center gap-2">
                        <span className="text-xs text-slate-500 dark:text-slate-400">{totalSKUs} SKUs</span>
                        <div className="relative">
                          <button onClick={() => setOpenMenu(openMenu === `t-${treatment.id}` ? null : `t-${treatment.id}`)} className="rounded p-1 text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-700">
                            <MoreHorizontal className="h-4 w-4" />
                          </button>
                          {openMenu === `t-${treatment.id}` && <DesignContextMenu onClose={() => setOpenMenu(null)} onRemove={() => handleDeleteTreatment(treatment.id)} />}
                        </div>
                      </div>
                    </div>

                    {/* Design row */}
                    {tpl && (
                      <div className="flex items-center gap-3 px-4 py-3">
                        <div className="flex h-12 w-12 shrink-0 items-center justify-center overflow-hidden rounded-md border border-slate-200 bg-slate-50 dark:border-slate-700 dark:bg-slate-900">
                          <Layers className="h-5 w-5 text-slate-300" />
                        </div>
                        <div className="min-w-0 flex-1">
                          <p className="truncate text-sm font-medium text-slate-800 dark:text-slate-200">{tpl.name}</p>
                          <p className="text-[10px] text-slate-400">{tpl.canvas_width}x{tpl.canvas_height}</p>
                        </div>
                        {treatment.filters.length > 0 && (
                          <div className="flex items-center gap-1 rounded bg-amber-50 px-2 py-0.5 text-xs font-medium text-amber-700 dark:bg-amber-900/20 dark:text-amber-400">
                            <Filter className="h-3 w-3" />{treatment.filters.length}
                          </div>
                        )}
                        <span className="shrink-0 text-xs text-slate-500 dark:text-slate-400">{totalSKUs} SKUs</span>
                        <div className="relative">
                          <button onClick={() => setOpenMenu(openMenu === `d-${treatment.id}` ? null : `d-${treatment.id}`)} className="rounded p-1 text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-700">
                            <MoreHorizontal className="h-4 w-4" />
                          </button>
                          {openMenu === `d-${treatment.id}` && <DesignContextMenu onClose={() => setOpenMenu(null)} onRemove={() => handleDeleteTreatment(treatment.id)} />}
                        </div>
                      </div>
                    )}

                    {/* + Add Design */}
                    <div className="border-t border-slate-100 px-4 py-2 dark:border-slate-700">
                      <button onClick={() => setShowTreatmentEditor(true)} className="flex w-full items-center justify-center gap-1 rounded-md py-1.5 text-xs text-slate-400 hover:bg-slate-50 hover:text-indigo-600 dark:hover:bg-slate-700">
                        <Plus className="h-3.5 w-3.5" /> Add Design
                      </button>
                    </div>
                  </div>
                );
              })
            )}

            {showTreatmentEditor && (
              <div className="rounded-lg border border-slate-200 bg-white p-4 dark:border-slate-700 dark:bg-slate-800">
                <TreatmentEditor
                  outputFeedId={feedId}
                  templates={templates}
                  onSave={async (payload) => { await createTreatment(payload); setShowTreatmentEditor(false); }}
                  onCancel={() => setShowTreatmentEditor(false)}
                  isSaving={isCreating}
                />
              </div>
            )}

            <button
              onClick={() => setShowTreatmentEditor(true)}
              className="flex w-full items-center gap-1.5 rounded-lg border border-dashed border-slate-300 px-4 py-3 text-sm text-slate-500 hover:border-indigo-400 hover:bg-indigo-50 hover:text-indigo-600 dark:border-slate-600 dark:hover:border-indigo-500 dark:hover:bg-indigo-900/20 dark:hover:text-indigo-400"
            >
              <Plus className="h-4 w-4" /> New Treatment
            </button>
          </div>
        </div>

        {/* Right sidebar */}
        <div className="w-72 shrink-0 space-y-4">
          {/* Feed Link */}
          <div className="rounded-lg border border-slate-200 bg-white p-4 dark:border-slate-700 dark:bg-slate-800">
            <div className="mb-2 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
              <Link2 className="h-3.5 w-3.5" /> Feed Link
            </div>
            {publicUrl ? (
              <div className="flex items-center gap-1">
                <code className="min-w-0 flex-1 truncate rounded bg-slate-50 px-2 py-1.5 text-[10px] text-slate-600 dark:bg-slate-900 dark:text-slate-400">{publicUrl}</code>
                <button onClick={handleCopyFeedUrl} className="shrink-0 rounded p-1 text-slate-400 hover:text-slate-600" title="Copy URL"><Copy className="h-3.5 w-3.5" /></button>
                <a href={publicUrl} target="_blank" rel="noopener noreferrer" className="shrink-0 rounded p-1 text-slate-400 hover:text-slate-600"><ExternalLink className="h-3.5 w-3.5" /></a>
              </div>
            ) : (
              <p className="text-xs text-slate-400">Generating link...</p>
            )}
            {copiedUrl && <p className="mt-1 text-[10px] text-emerald-500">Copied!</p>}
          </div>

          {/* Quick actions */}
          <div className="space-y-2">
            <button className="flex w-full items-center justify-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-medium text-slate-600 hover:bg-slate-50 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-300 dark:hover:bg-slate-700">Connected Catalogs</button>
            <button className="flex w-full items-center justify-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-medium text-slate-600 hover:bg-slate-50 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-300 dark:hover:bg-slate-700">Assign Ads</button>
          </div>

          {/* Status */}
          <div className="rounded-lg border border-slate-200 bg-white p-4 dark:border-slate-700 dark:bg-slate-800">
            <div className="space-y-2.5 text-xs">
              <div className="flex items-center justify-between">
                <span className="flex items-center gap-1.5 text-slate-500 dark:text-slate-400"><Clock className="h-3 w-3" /> Last Updated</span>
                <span className="font-medium text-slate-700 dark:text-slate-300">{lastUpdated}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="flex items-center gap-1.5 text-slate-500 dark:text-slate-400"><Calendar className="h-3 w-3" /> Last Requested</span>
                <span className="font-medium text-slate-700 dark:text-slate-300">N/A</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="flex items-center gap-1.5 text-slate-500 dark:text-slate-400"><Package className="h-3 w-3" /> Total SKUs</span>
                <span className="font-medium text-slate-700 dark:text-slate-300">{totalSKUs}</span>
              </div>
            </div>
          </div>

          {/* Meta toggle */}
          <div className="rounded-lg border border-slate-200 bg-white p-4 dark:border-slate-700 dark:bg-slate-800">
            <label className="flex cursor-pointer items-center justify-between gap-2">
              <span className="text-xs text-slate-600 dark:text-slate-300">Update Meta catalogs on publish</span>
              <div className={`relative h-5 w-9 rounded-full transition-colors ${metaCatalogSync ? "bg-emerald-500" : "bg-slate-300 dark:bg-slate-600"}`} onClick={() => setMetaCatalogSync(!metaCatalogSync)}>
                <div className={`absolute top-0.5 h-4 w-4 rounded-full bg-white shadow transition-transform ${metaCatalogSync ? "translate-x-4" : "translate-x-0.5"}`} />
              </div>
            </label>
          </div>

          {/* Publish + Schedule */}
          <div className="space-y-2">
            <button onClick={handleGenerate} disabled={generating} className="flex w-full items-center justify-center gap-2 rounded-lg bg-emerald-500 px-4 py-2.5 text-sm font-semibold text-white shadow hover:bg-emerald-600 disabled:opacity-50">
              {generating ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />} Publish
            </button>
            <button onClick={() => setShowMultiFormat(true)} className="flex w-full items-center justify-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-medium text-slate-600 hover:bg-slate-50 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-300 dark:hover:bg-slate-700">Schedule</button>
          </div>

          <div className="flex items-center gap-2 text-[10px]">
            <button onClick={() => regenerateToken(feedId).then((r) => setPublicUrl(r.public_url)).catch(() => {})} className="flex items-center gap-1 text-slate-400 hover:text-slate-600"><RefreshCw className="h-3 w-3" /> Regenerate Token</button>
            <select defaultValue={feed.refresh_interval_hours} onChange={(e) => setRefreshSchedule(feedId, Number(e.target.value))} className="mcc-input rounded border px-1.5 py-0.5 text-[10px]">
              <option value={1}>1h</option>
              <option value={6}>6h</option>
              <option value={12}>12h</option>
              <option value={24}>24h</option>
              <option value={48}>48h</option>
            </select>
          </div>
        </div>
      </div>

      {/* Multi-format modal */}
      {showMultiFormat && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="w-full max-w-lg rounded-lg bg-white p-6 shadow-xl dark:bg-slate-800">
            <h3 className="mb-4 text-lg font-semibold text-slate-900 dark:text-slate-100">Multi-Format Generation</h3>
            <p className="mb-4 text-sm text-slate-500 dark:text-slate-400">Render all products across multiple template formats in a single batch.</p>
            <label className="mb-2 block text-sm font-medium text-slate-700 dark:text-slate-300">Select Templates</label>
            <div className="mb-4 max-h-48 space-y-2 overflow-y-auto rounded-md border border-slate-200 p-2 dark:border-slate-600">
              {templates.length === 0 ? (
                <p className="py-2 text-center text-xs text-slate-400">No templates available</p>
              ) : templates.map((t) => (
                <label key={t.id} className={`flex cursor-pointer items-center gap-3 rounded-md border px-3 py-2 text-sm transition ${selectedFormatIds.has(t.id) ? "border-indigo-500 bg-indigo-50 dark:border-indigo-400 dark:bg-indigo-900/20" : "border-slate-100 hover:border-slate-200 dark:border-slate-700"}`}>
                  <input type="checkbox" checked={selectedFormatIds.has(t.id)} onChange={() => toggleFormatId(t.id)} className="accent-indigo-600" />
                  <span className="flex-1 text-slate-700 dark:text-slate-300">{t.name}</span>
                  <span className="text-xs text-slate-400">{t.canvas_width}x{t.canvas_height}</span>
                </label>
              ))}
            </div>
            {templates.length > 0 && (
              <button onClick={() => { if (selectedFormatIds.size === templates.length) setSelectedFormatIds(new Set()); else setSelectedFormatIds(new Set(templates.map((t) => t.id))); }} className="mb-4 text-xs text-indigo-600 hover:text-indigo-700 dark:text-indigo-400">
                {selectedFormatIds.size === templates.length ? "Deselect All" : "Select All"}
              </button>
            )}
            <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">Webhook URL <span className="font-normal text-slate-400">(optional)</span></label>
            <input type="url" value={webhookUrl} onChange={(e) => setWebhookUrl(e.target.value)} placeholder="https://your-app.com/webhook/render-complete" className="mcc-input mb-2 w-full rounded-md border px-3 py-2 text-sm" />
            <p className="mb-6 text-xs text-slate-400">Receives a POST notification when the batch render completes.</p>
            {selectedFormatIds.size > 0 && (
              <div className="mb-4 rounded-md bg-indigo-50 px-3 py-2 text-xs text-indigo-700 dark:bg-indigo-900/20 dark:text-indigo-400">
                Will render products across {selectedFormatIds.size} template{selectedFormatIds.size > 1 ? "s" : ""}.
              </div>
            )}
            <div className="flex justify-end gap-3">
              <button onClick={() => { setShowMultiFormat(false); setSelectedFormatIds(new Set()); setWebhookUrl(""); }} className="rounded-md px-4 py-2 text-sm text-slate-600 hover:bg-slate-100 dark:text-slate-400 dark:hover:bg-slate-700">Cancel</button>
              <button onClick={handleMultiFormatRender} disabled={selectedFormatIds.size === 0 || multiFormatGenerating} className="wm-btn-primary inline-flex items-center gap-2 rounded-md px-4 py-2 text-sm font-medium text-white disabled:opacity-50">
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
