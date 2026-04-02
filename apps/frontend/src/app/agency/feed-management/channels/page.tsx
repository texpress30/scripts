"use client";

import { useState } from "react";
import Link from "next/link";
import { Loader2, Plus, Rss, CheckCircle2, AlertCircle, Clock, Pause, Copy, ExternalLink } from "lucide-react";
import { useFeedSources } from "@/lib/hooks/useFeedSources";
import { useFeedManagement } from "@/lib/contexts/FeedManagementContext";
import { useChannels, type FeedChannel } from "@/lib/hooks/useMasterFields";
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
  paused: { icon: Pause, color: "text-amber-500 dark:text-amber-400", label: "Paused" },
  error: { icon: AlertCircle, color: "text-red-500 dark:text-red-400", label: "Error" },
};

function SourceChannelsSection({ sourceId, sourceName }: { sourceId: string; sourceName: string }) {
  const { channels, isLoading, createChannel, isCreating } = useChannels(sourceId);
  const [showModal, setShowModal] = useState(false);
  const [copiedId, setCopiedId] = useState<string | null>(null);

  function copyFeedUrl(ch: FeedChannel) {
    const url = ch.feed_url ?? `/feeds/${ch.public_token}.${ch.feed_format}`;
    const fullUrl = `${window.location.origin}/api${url}`;
    void navigator.clipboard.writeText(fullUrl);
    setCopiedId(ch.id);
    setTimeout(() => setCopiedId(null), 2000);
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-6">
        <Loader2 className="h-5 w-5 animate-spin text-slate-400" />
      </div>
    );
  }

  return (
    <section className="wm-card overflow-hidden">
      <div className="flex items-center justify-between border-b border-slate-200 px-5 py-3 dark:border-slate-700">
        <h3 className="text-sm font-semibold text-slate-900 dark:text-slate-100">{sourceName}</h3>
        <button type="button" onClick={() => setShowModal(true)} className="inline-flex items-center gap-1.5 rounded px-2.5 py-1.5 text-xs font-medium text-indigo-600 hover:bg-indigo-50 dark:text-indigo-400 dark:hover:bg-indigo-900/20">
          <Plus className="h-3.5 w-3.5" />
          Add Channel
        </button>
      </div>

      {channels.length === 0 ? (
        <div className="px-5 py-6 text-center">
          <p className="text-sm text-slate-400 dark:text-slate-500">No channels yet for this source.</p>
        </div>
      ) : (
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="border-b border-slate-200 bg-slate-50 dark:border-slate-700 dark:bg-slate-800/50">
              <th className="px-4 py-2.5 font-medium text-slate-600 dark:text-slate-400">Name</th>
              <th className="px-4 py-2.5 font-medium text-slate-600 dark:text-slate-400">Type</th>
              <th className="px-4 py-2.5 font-medium text-slate-600 dark:text-slate-400">Products</th>
              <th className="px-4 py-2.5 font-medium text-slate-600 dark:text-slate-400">Status</th>
              <th className="px-4 py-2.5 font-medium text-slate-600 dark:text-slate-400">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-200 dark:divide-slate-700">
            {channels.map((ch) => {
              const statusCfg = STATUS_CONFIG[ch.status] ?? STATUS_CONFIG.draft;
              const StatusIcon = statusCfg.icon;
              return (
                <tr key={ch.id} className="hover:bg-slate-50 dark:hover:bg-slate-800/30">
                  <td className="px-4 py-2.5 font-medium text-slate-900 dark:text-slate-100">{ch.name}</td>
                  <td className="px-4 py-2.5 text-slate-600 dark:text-slate-400">{CHANNEL_TYPE_LABELS[ch.channel_type] ?? ch.channel_type}</td>
                  <td className="px-4 py-2.5 text-slate-600 dark:text-slate-400">{ch.included_products}</td>
                  <td className="px-4 py-2.5">
                    <span className={`inline-flex items-center gap-1 ${statusCfg.color}`}>
                      <StatusIcon className="h-3.5 w-3.5" />
                      {statusCfg.label}
                    </span>
                  </td>
                  <td className="px-4 py-2.5">
                    <div className="flex items-center gap-2">
                      <Link href={`/agency/feed-management/channels/${ch.id}`} className="rounded px-2 py-1 text-xs font-medium text-indigo-600 hover:bg-indigo-50 dark:text-indigo-400 dark:hover:bg-indigo-900/20">
                        Edit
                      </Link>
                      <button type="button" onClick={() => copyFeedUrl(ch)} className="rounded px-2 py-1 text-xs font-medium text-slate-500 hover:bg-slate-100 dark:text-slate-400 dark:hover:bg-slate-800" title="Copy feed URL">
                        {copiedId === ch.id ? <span className="text-emerald-600 dark:text-emerald-400">Copied!</span> : <Copy className="h-3.5 w-3.5" />}
                      </button>
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}

      <AddChannelModal open={showModal} onClose={() => setShowModal(false)} onCreate={createChannel} isCreating={isCreating} />
    </section>
  );
}

export default function ChannelsPage() {
  const { selectedId, isLoading: clientsLoading } = useFeedManagement();
  const { sources, isLoading: sourcesLoading } = useFeedSources(selectedId);

  const loading = clientsLoading || sourcesLoading;

  return (
    <>
      <div className="mb-6">
        <h2 className="text-lg font-semibold text-slate-900 dark:text-slate-100">Channels</h2>
        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
          Manage publishing channels for Google, Facebook, and other platforms.
        </p>
      </div>

      {!selectedId && !clientsLoading ? (
        <div className="wm-card flex flex-col items-center justify-center px-6 py-16 text-center">
          <p className="text-sm text-slate-500 dark:text-slate-400">
            Selecteaza un client pentru a vizualiza canalele.
          </p>
        </div>
      ) : loading ? (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="h-6 w-6 animate-spin text-slate-400" />
        </div>
      ) : sources.length === 0 ? (
        <div className="wm-card flex flex-col items-center justify-center px-6 py-16 text-center">
          <Rss className="mx-auto mb-3 h-10 w-10 text-slate-300 dark:text-slate-600" />
          <p className="text-sm font-medium text-slate-500 dark:text-slate-400">
            Nicio sursa configurata pentru acest client.
          </p>
          <p className="mt-1 text-xs text-slate-400 dark:text-slate-500">
            Adauga o sursa din tab-ul Sources si configureaza mappings inainte de a crea canale.
          </p>
        </div>
      ) : (
        <div className="space-y-6">
          {sources.map((source) => (
            <SourceChannelsSection key={source.id} sourceId={source.id} sourceName={source.name} />
          ))}
        </div>
      )}
    </>
  );
}
