"use client";

import { useState } from "react";
import { X, Loader2 } from "lucide-react";

const CHANNEL_TYPES = [
  { value: "google_shopping", label: "Google Shopping" },
  { value: "facebook_product_ads", label: "Facebook Product Ads" },
  { value: "meta_catalog", label: "Meta Catalog" },
  { value: "tiktok_catalog", label: "TikTok Catalog" },
  { value: "custom", label: "Custom" },
];

const FEED_FORMATS = [
  { value: "xml", label: "XML" },
  { value: "csv", label: "CSV" },
  { value: "tsv", label: "TSV" },
  { value: "json", label: "JSON" },
];

type Props = {
  open: boolean;
  onClose: () => void;
  onCreate: (data: { name: string; channel_type: string; feed_format: string }) => Promise<unknown>;
  isCreating: boolean;
};

export function AddChannelModal({ open, onClose, onCreate, isCreating }: Props) {
  const [name, setName] = useState("");
  const [channelType, setChannelType] = useState("google_shopping");
  const [feedFormat, setFeedFormat] = useState("xml");
  const [error, setError] = useState<string | null>(null);

  if (!open) return null;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (!name.trim()) {
      setError("Channel name is required");
      return;
    }
    try {
      await onCreate({ name: name.trim(), channel_type: channelType, feed_format: feedFormat });
      setName("");
      setChannelType("google_shopping");
      setFeedFormat("xml");
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create channel");
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="wm-card w-full max-w-md p-6">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-slate-900 dark:text-slate-100">Add Channel</h2>
          <button type="button" onClick={onClose} className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-300">
            <X className="h-5 w-5" />
          </button>
        </div>

        <form onSubmit={(e) => void handleSubmit(e)} className="space-y-4">
          <div>
            <label htmlFor="ch-name" className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">
              Channel Name
            </label>
            <input
              id="ch-name"
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Google Shopping - Main"
              className="wm-input"
              autoFocus
            />
          </div>

          <div>
            <label htmlFor="ch-type" className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">
              Channel Type
            </label>
            <select id="ch-type" value={channelType} onChange={(e) => setChannelType(e.target.value)} className="wm-input">
              {CHANNEL_TYPES.map((ct) => (
                <option key={ct.value} value={ct.value}>{ct.label}</option>
              ))}
            </select>
          </div>

          <div>
            <label htmlFor="ch-format" className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">
              Feed Format
            </label>
            <select id="ch-format" value={feedFormat} onChange={(e) => setFeedFormat(e.target.value)} className="wm-input">
              {FEED_FORMATS.map((ff) => (
                <option key={ff.value} value={ff.value}>{ff.label}</option>
              ))}
            </select>
          </div>

          {error && (
            <p className="rounded-lg bg-red-50 p-2 text-xs text-red-600 dark:bg-red-900/20 dark:text-red-400">{error}</p>
          )}

          <div className="flex items-center justify-end gap-3 pt-2">
            <button type="button" onClick={onClose} className="wm-btn-secondary">
              Cancel
            </button>
            <button type="submit" className="wm-btn-primary" disabled={isCreating}>
              {isCreating && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Create Channel
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
