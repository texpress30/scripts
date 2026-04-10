"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowLeft, Loader2 } from "lucide-react";
import { useFeedManagement } from "@/lib/contexts/FeedManagementContext";
import { useOutputFeeds } from "@/lib/hooks/useOutputFeeds";
import { FeedSourcePicker } from "@/components/enriched-catalog/FeedSourcePicker";

const FORMAT_OPTIONS = [
  { value: "xml", label: "XML (Google Shopping RSS)" },
  { value: "json", label: "JSON" },
  { value: "csv", label: "CSV" },
  { value: "google_shopping_xml", label: "Google Shopping XML" },
  { value: "meta_csv", label: "Meta Catalog CSV" },
] as const;

export default function NewOutputFeedPage() {
  const router = useRouter();
  const { selectedId } = useFeedManagement();
  const { create, isCreating } = useOutputFeeds(selectedId);

  const [name, setName] = useState("");
  const [feedSourceId, setFeedSourceId] = useState("");
  const [feedFormat, setFeedFormat] = useState("xml");

  const handleCreate = async () => {
    if (!name.trim()) return;
    try {
      const feed = await create({
        name: name.trim(),
        feed_source_id: feedSourceId || undefined,
        feed_format: feedFormat,
      });
      router.push(`/agency/enriched-catalog/output-feeds/${feed.id}`);
    } catch (err) {
      console.error("Failed to create output feed:", err);
      alert("Failed to create output feed.");
    }
  };

  if (!selectedId) {
    return (
      <div className="flex h-64 items-center justify-center text-sm text-slate-500 dark:text-slate-400">
        Select a client first.
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-lg">
      <button
        onClick={() => router.push("/agency/enriched-catalog/output-feeds")}
        className="mb-4 flex items-center gap-1 text-sm text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-300"
      >
        <ArrowLeft className="h-4 w-4" /> Back to Output Feeds
      </button>

      <h2 className="mb-6 text-lg font-semibold text-slate-900 dark:text-slate-100">New Output Feed</h2>

      <div className="space-y-5 rounded-lg border border-slate-200 bg-white p-6 dark:border-slate-700 dark:bg-slate-800">
        {/* Name */}
        <div>
          <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">Feed Name</label>
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="e.g. Facebook Product Feed"
            className="mcc-input w-full rounded-md border px-3 py-2 text-sm"
            autoFocus
          />
        </div>

        {/* Feed Source */}
        <div>
          <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">Feed Source</label>
          <FeedSourcePicker value={feedSourceId} onChange={setFeedSourceId} />
          <p className="mt-1 text-xs text-slate-400">
            Select the product feed to use for generating creatives.
          </p>
        </div>

        {/* Format */}
        <div>
          <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">Output Format</label>
          <select
            value={feedFormat}
            onChange={(e) => setFeedFormat(e.target.value)}
            className="mcc-input w-full rounded-md border px-3 py-2 text-sm"
          >
            {FORMAT_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>{opt.label}</option>
            ))}
          </select>
        </div>

        <div className="flex justify-end gap-3 pt-2">
          <button
            onClick={() => router.push("/agency/enriched-catalog/output-feeds")}
            className="rounded-md px-4 py-2 text-sm text-slate-600 hover:bg-slate-100 dark:text-slate-400 dark:hover:bg-slate-700"
          >
            Cancel
          </button>
          <button
            onClick={handleCreate}
            disabled={!name.trim() || isCreating}
            className="wm-btn-primary inline-flex items-center gap-2 rounded-md px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
          >
            {isCreating && <Loader2 className="h-4 w-4 animate-spin" />}
            Create Output Feed
          </button>
        </div>
      </div>
    </div>
  );
}
