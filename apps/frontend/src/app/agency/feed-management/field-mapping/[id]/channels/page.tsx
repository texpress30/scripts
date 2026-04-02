"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, Plus, CheckCircle2, AlertCircle, Clock, Loader2, Copy, ExternalLink } from "lucide-react";
import { useChannels, useMasterFields } from "@/lib/hooks/useMasterFields";
import { AddChannelModal } from "@/components/feed-management/AddChannelModal";

const CHANNEL_TYPE_LABELS: Record<string, string> = {
  google_shopping: "Google Shopping",
  facebook_product_ads: "Facebook Product Ads",
  meta_catalog: "Meta Catalog",
  tiktok_catalog: "TikTok Catalog",
  custom: "Custom",
};

const STATUS_CONFIG: Record<string, { icon: typeof CheckCircle2; color: string; label: string }> = {
  active: { icon: CheckCircle2, color: "text-emerald-600 dark:text-emerald-400", label: "Active" },
  draft: { icon: Clock, color: "text-slate-400 dark:text-slate-500", label: "Draft" },
  paused: { icon: Clock, color: "text-amber-500 dark:text-amber-400", label: "Paused" },
  error: { icon: AlertCircle, color: "text-red-500 dark:text-red-400", label: "Error" },
};

export default function ChannelsPage() {
  const params = useParams<{ id: string }>();
  const sourceId = params.id;

  const { data: masterData } = useMasterFields(sourceId);
  const { channels, isLoading, createChannel, isCreating } = useChannels(sourceId);
  const [showModal, setShowModal] = useState(false);
  const [copiedId, setCopiedId] = useState<string | null>(null);

  const sourceName = masterData?.source_name ?? "Source";

  function copyFeedUrl(channel: { id: string; feed_url: string | null; public_token: string; feed_format: string }) {
    const url = channel.feed_url ?? `/feeds/${channel.public_token}.${channel.feed_format}`;
    const fullUrl = `${window.location.origin}/api${url}`;
    void navigator.clipboard.writeText(fullUrl);
    setCopiedId(channel.id);
    setTimeout(() => setCopiedId(null), 2000);
  }

  return (
    <>
      <Link
        href={`/agency/feed-management/field-mapping/${sourceId}`}
        className="mb-4 inline-flex items-center gap-1 text-sm text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-300"
      >
        <ArrowLeft className="h-4 w-4" />
        Back to Master Fields
      </Link>

      {/* Header */}
      <div className="mb-6 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-xl font-semibold text-slate-900 dark:text-slate-100">
            Channels &mdash; {sourceName}
          </h1>
          <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
            Create channels to publish your feed to Google, Facebook, and other platforms.
          </p>
        </div>
        <button
          type="button"
          onClick={() => setShowModal(true)}
          className="wm-btn-primary inline-flex items-center gap-2"
        >
          <Plus className="h-4 w-4" />
          Add Channel
        </button>
      </div>

      {/* Loading */}
      {isLoading && (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="h-6 w-6 animate-spin text-slate-400" />
        </div>
      )}

      {/* Empty state */}
      {!isLoading && channels.length === 0 && (
        <div className="wm-card flex flex-col items-center justify-center px-6 py-16 text-center">
          <ExternalLink className="mx-auto mb-3 h-10 w-10 text-slate-300 dark:text-slate-600" />
          <p className="text-sm font-medium text-slate-500 dark:text-slate-400">No channels yet</p>
          <p className="mt-1 text-xs text-slate-400 dark:text-slate-500">
            Create your first channel to start publishing feeds.
          </p>
          <button
            type="button"
            onClick={() => setShowModal(true)}
            className="wm-btn-primary mt-4 inline-flex items-center gap-2 text-sm"
          >
            <Plus className="h-4 w-4" />
            Add Channel
          </button>
        </div>
      )}

      {/* Channels table */}
      {!isLoading && channels.length > 0 && (
        <div className="wm-card overflow-hidden">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-slate-200 bg-slate-50 dark:border-slate-700 dark:bg-slate-800/50">
                <th className="px-4 py-3 font-medium text-slate-600 dark:text-slate-400">Name</th>
                <th className="px-4 py-3 font-medium text-slate-600 dark:text-slate-400">Channel Type</th>
                <th className="px-4 py-3 font-medium text-slate-600 dark:text-slate-400">Products</th>
                <th className="px-4 py-3 font-medium text-slate-600 dark:text-slate-400">Status</th>
                <th className="px-4 py-3 font-medium text-slate-600 dark:text-slate-400">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-200 dark:divide-slate-700">
              {channels.map((ch) => {
                const statusCfg = STATUS_CONFIG[ch.status] ?? STATUS_CONFIG.draft;
                const StatusIcon = statusCfg.icon;
                return (
                  <tr key={ch.id} className="hover:bg-slate-50 dark:hover:bg-slate-800/30">
                    <td className="px-4 py-3 font-medium text-slate-900 dark:text-slate-100">{ch.name}</td>
                    <td className="px-4 py-3 text-slate-600 dark:text-slate-400">
                      {CHANNEL_TYPE_LABELS[ch.channel_type] ?? ch.channel_type}
                    </td>
                    <td className="px-4 py-3 text-slate-600 dark:text-slate-400">{ch.included_products}</td>
                    <td className="px-4 py-3">
                      <span className={`inline-flex items-center gap-1 ${statusCfg.color}`}>
                        <StatusIcon className="h-3.5 w-3.5" />
                        {statusCfg.label}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <Link
                          href={`/agency/feed-management/channels/${ch.id}`}
                          className="rounded px-2 py-1 text-xs font-medium text-indigo-600 hover:bg-indigo-50 dark:text-indigo-400 dark:hover:bg-indigo-900/20"
                        >
                          Edit
                        </Link>
                        <button
                          type="button"
                          onClick={() => copyFeedUrl(ch)}
                          className="rounded px-2 py-1 text-xs font-medium text-slate-500 hover:bg-slate-100 dark:text-slate-400 dark:hover:bg-slate-800"
                          title="Copy feed URL"
                        >
                          {copiedId === ch.id ? (
                            <span className="text-emerald-600 dark:text-emerald-400">Copied!</span>
                          ) : (
                            <Copy className="h-3.5 w-3.5" />
                          )}
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      <AddChannelModal
        open={showModal}
        onClose={() => setShowModal(false)}
        onCreate={createChannel}
        isCreating={isCreating}
      />
    </>
  );
}
