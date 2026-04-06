"use client";

import { useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import {
  ArrowLeft,
  Loader2,
  RefreshCw,
  Copy,
  CheckCircle2,
  AlertCircle,
  Clock,
  Pause,
  Play,
  Trash2,
} from "lucide-react";
import { useChannel, useChannelPreview, useSourceFields } from "@/lib/hooks/useMasterFields";
import { ChannelFieldsSection } from "@/components/feed-management/ChannelFieldsSection";
import { CHANNEL_DISPLAY_NAMES, CHANNEL_PLATFORM_MAP, getPlatformBadgeColor } from "@/lib/data/channel-platforms";

const CHANNEL_SUBTYPE_LABELS: Record<string, string> = {
  google_vehicle_ads_v3: "Vehicle Listings",
  google_vehicle_listings: "Vehicle Listings",
  facebook_product_ads: "Vehicle Offers",
  tiktok_automotive_inventory: "Vehicle Listings",
};

const STATUS_CONFIG: Record<string, { icon: typeof CheckCircle2; bg: string; text: string; label: string }> = {
  active: { icon: CheckCircle2, bg: "bg-emerald-100 dark:bg-emerald-900/30", text: "text-emerald-700 dark:text-emerald-400", label: "Active" },
  draft: { icon: Clock, bg: "bg-slate-100 dark:bg-slate-800", text: "text-slate-600 dark:text-slate-400", label: "Draft" },
  paused: { icon: Pause, bg: "bg-amber-100 dark:bg-amber-900/30", text: "text-amber-700 dark:text-amber-400", label: "Paused" },
  error: { icon: AlertCircle, bg: "bg-red-100 dark:bg-red-900/30", text: "text-red-700 dark:text-red-400", label: "Error" },
};

export default function ChannelDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const channelId = params.id;

  const {
    channel,
    isLoading,
    error,
    updateChannel,
    isUpdating,
    deleteChannel,
    isDeleting,
    generateFeed,
    isGenerating,
  } = useChannel(channelId);

  const { preview, isLoading: previewLoading, refresh: refreshPreview } = useChannelPreview(channelId);
  const { fields: sourceFieldsList } = useSourceFields(channel?.feed_source_id ?? null);
  const [copied, setCopied] = useState(false);
  const [generateMsg, setGenerateMsg] = useState<string | null>(null);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-16">
        <Loader2 className="h-6 w-6 animate-spin text-slate-400" />
      </div>
    );
  }

  if (error || !channel) {
    return (
      <div className="py-8">
        <Link
          href="/agency/feed-management/field-mapping"
          className="mb-4 inline-flex items-center gap-1 text-sm text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-300"
        >
          <ArrowLeft className="h-4 w-4" />
          Back
        </Link>
        <p className="text-red-600">{error ?? "Channel not found."}</p>
      </div>
    );
  }

  const statusCfg = STATUS_CONFIG[channel.status] ?? STATUS_CONFIG.draft;
  const StatusIcon = statusCfg.icon;
  const feedUrl = channel.feed_url
    ? `${window.location.origin}/api${channel.feed_url}`
    : `${window.location.origin}/api/feeds/${channel.public_token}.${channel.feed_format}`;

  function handleCopy() {
    void navigator.clipboard.writeText(feedUrl);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  async function handleGenerate() {
    setGenerateMsg(null);
    try {
      await generateFeed();
      setGenerateMsg("Feed generation started. Refresh the page in a few seconds.");
    } catch (err) {
      setGenerateMsg(err instanceof Error ? err.message : "Failed to start generation");
    }
  }

  async function handleTogglePause() {
    if (!channel) return;
    const newStatus = channel.status === "paused" ? "active" : "paused";
    await updateChannel({ status: newStatus } as never);
  }

  async function handleDelete() {
    if (!channel) return;
    if (!confirm("Are you sure you want to delete this channel?")) return;
    await deleteChannel();
    router.push(`/agency/feed-management/field-mapping/${channel.feed_source_id}/channels`);
  }

  return (
    <>
      <Link
        href="/agency/feed-management/channels"
        className="mb-4 inline-flex items-center gap-1 text-sm text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-300"
      >
        <ArrowLeft className="h-4 w-4" />
        Back to Channels
      </Link>

      {/* Header */}
      <div className="mb-6">
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h1 className="text-xl font-semibold text-slate-900 dark:text-slate-100">{channel.name}</h1>
            <div className="mt-1 flex items-center gap-2">
              {(() => {
                const platformInfo = CHANNEL_PLATFORM_MAP[channel.channel_type];
                return platformInfo ? (
                  <span className={`rounded px-2 py-0.5 text-[10px] font-semibold ${getPlatformBadgeColor(platformInfo.platform)}`}>
                    {platformInfo.platformDisplayName}
                  </span>
                ) : null;
              })()}
              <span className="rounded bg-indigo-100 px-2 py-0.5 text-xs font-medium text-indigo-700 dark:bg-indigo-900/40 dark:text-indigo-400">
                {CHANNEL_DISPLAY_NAMES[channel.channel_type] ?? channel.channel_type}
              </span>
              {CHANNEL_SUBTYPE_LABELS[channel.channel_type] && (
                <span className="rounded bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-600 dark:bg-slate-700 dark:text-slate-400">
                  {CHANNEL_SUBTYPE_LABELS[channel.channel_type]}
                </span>
              )}
              <span className={`inline-flex items-center gap-1 rounded px-2 py-0.5 text-xs font-medium ${statusCfg.bg} ${statusCfg.text}`}>
                <StatusIcon className="h-3 w-3" />
                {statusCfg.label}
              </span>
              <span className="text-xs text-slate-400">
                {channel.included_products} products &middot; {channel.feed_format.toUpperCase()}
              </span>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => void handleGenerate()}
              disabled={isGenerating}
              className="wm-btn-primary inline-flex items-center gap-2"
            >
              {isGenerating ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
              Generate Feed
            </button>
            <button
              type="button"
              onClick={() => void handleTogglePause()}
              disabled={isUpdating}
              className="wm-btn-secondary inline-flex items-center gap-2"
            >
              {channel.status === "paused" ? <Play className="h-4 w-4" /> : <Pause className="h-4 w-4" />}
              {channel.status === "paused" ? "Resume" : "Pause"}
            </button>
            <button
              type="button"
              onClick={() => void handleDelete()}
              disabled={isDeleting}
              className="inline-flex items-center gap-1 rounded px-3 py-2 text-sm text-red-600 hover:bg-red-50 dark:text-red-400 dark:hover:bg-red-900/20"
            >
              <Trash2 className="h-4 w-4" />
            </button>
          </div>
        </div>
      </div>

      {/* Quick links */}
      <div className="mb-4 flex gap-2">
        <Link
          href={`/agency/feed-management/channels/${channelId}/products`}
          className="wm-btn-secondary inline-flex items-center gap-1.5 text-xs"
        >
          Channel Products
        </Link>
      </div>

      {generateMsg && (
        <div className="mb-4 rounded-lg bg-indigo-50 p-3 text-sm text-indigo-700 dark:bg-indigo-900/20 dark:text-indigo-400">
          {generateMsg}
        </div>
      )}

      {channel.error_message && (
        <div className="mb-4 rounded-lg bg-red-50 p-3 text-sm text-red-700 dark:bg-red-900/20 dark:text-red-400">
          {channel.error_message}
        </div>
      )}

      {/* Feed URL & Format */}
      <div className="wm-card mb-6 p-4">
        <h2 className="mb-2 text-sm font-semibold text-slate-700 dark:text-slate-300">Feed URL</h2>
        <div className="flex items-center gap-2">
          <code className="flex-1 overflow-hidden text-ellipsis rounded bg-slate-100 px-3 py-2 font-mono text-xs text-slate-700 dark:bg-slate-800 dark:text-slate-300">
            {feedUrl}
          </code>
          <button
            type="button"
            onClick={handleCopy}
            className="wm-btn-secondary inline-flex items-center gap-1.5"
          >
            {copied ? (
              <>
                <CheckCircle2 className="h-4 w-4 text-emerald-600" />
                Copied
              </>
            ) : (
              <>
                <Copy className="h-4 w-4" />
                Copy
              </>
            )}
          </button>
        </div>
        <div className="mt-3 flex items-center gap-3">
          <label className="text-xs font-medium text-slate-500 dark:text-slate-400">Format</label>
          <select
            value={channel.feed_format}
            onChange={async (e) => {
              await updateChannel({ feed_format: e.target.value } as never);
            }}
            disabled={isUpdating}
            className="rounded border border-slate-300 bg-white px-2 py-1 text-xs text-slate-700 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-300"
          >
            <option value="xml">XML</option>
            <option value="csv">CSV</option>
            <option value="tsv">TSV</option>
            <option value="json">JSON</option>
          </select>
          <span className="text-[10px] text-slate-400">
            Changing format requires re-generating the feed.
          </span>
        </div>
        {channel.last_generated_at && (
          <p className="mt-2 text-xs text-slate-400">
            Last generated: {new Date(channel.last_generated_at).toLocaleString()}
          </p>
        )}
      </div>

      {/* Channel Fields */}
      <div className="mb-6">
        <ChannelFieldsSection channelId={channelId} sourceFields={sourceFieldsList} />
      </div>

      {/* Preview */}
      <div className="wm-card p-4">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-sm font-semibold text-slate-700 dark:text-slate-300">
            Preview (first {preview.length} products)
          </h2>
          <button
            type="button"
            onClick={() => void refreshPreview()}
            disabled={previewLoading}
            className="inline-flex items-center gap-1 text-xs text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-300"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${previewLoading ? "animate-spin" : ""}`} />
            Refresh
          </button>
        </div>

        {previewLoading && (
          <div className="flex items-center justify-center py-8">
            <Loader2 className="h-5 w-5 animate-spin text-slate-400" />
          </div>
        )}

        {!previewLoading && preview.length === 0 && (
          <p className="py-4 text-center text-sm text-slate-400">
            No products to preview. Make sure master fields are mapped and products are synced.
          </p>
        )}

        {!previewLoading && preview.length > 0 && (
          <div className="space-y-3">
            {preview.map((item, idx) => (
              <div key={idx} className="grid grid-cols-1 gap-3 rounded-lg border border-slate-200 p-3 dark:border-slate-700 lg:grid-cols-2">
                <div>
                  <span className="mb-1 block text-[10px] font-semibold uppercase tracking-wider text-slate-400">
                    Original
                  </span>
                  <pre className="max-h-32 overflow-auto rounded bg-slate-50 p-2 font-mono text-[11px] text-slate-600 dark:bg-slate-800 dark:text-slate-400">
                    {JSON.stringify(item.original, null, 2).slice(0, 500)}
                  </pre>
                </div>
                <div>
                  <span className="mb-1 block text-[10px] font-semibold uppercase tracking-wider text-indigo-500">
                    Transformed
                  </span>
                  <pre className="max-h-32 overflow-auto rounded bg-indigo-50 p-2 font-mono text-[11px] text-indigo-700 dark:bg-indigo-900/20 dark:text-indigo-400">
                    {JSON.stringify(item.transformed, null, 2).slice(0, 500)}
                  </pre>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </>
  );
}
