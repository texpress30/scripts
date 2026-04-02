"use client";

import { useState, useEffect } from "react";
import { X, Loader2 } from "lucide-react";
import {
  COUNTRIES,
  getChannelsForCountry,
  getCountryISOCode,
} from "@/lib/data/channel-config";

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
  const [selectedCountry, setSelectedCountry] = useState("");
  const [selectedChannel, setSelectedChannel] = useState("");
  const [isCustomMode, setIsCustomMode] = useState(false);
  const [customName, setCustomName] = useState("");
  const [feedFormat, setFeedFormat] = useState("xml");
  const [error, setError] = useState<string | null>(null);

  // Reset channel when country changes
  useEffect(() => {
    setSelectedChannel("");
    setIsCustomMode(false);
    setCustomName("");
  }, [selectedCountry]);

  // Reset all state when modal opens
  useEffect(() => {
    if (!open) return;
    setSelectedCountry("");
    setSelectedChannel("");
    setIsCustomMode(false);
    setCustomName("");
    setFeedFormat("xml");
    setError(null);
  }, [open]);

  if (!open) return null;

  const channels = selectedCountry ? getChannelsForCountry(selectedCountry) : null;

  function getChannelName(): string {
    if (isCustomMode) return customName.trim();
    if (!selectedChannel || !channels) return "";
    const all = [...channels.popular, ...channels.other];
    const ch = all.find((c) => c.id === selectedChannel);
    return ch?.name ?? selectedChannel;
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);

    if (!selectedCountry) {
      setError("Please select a country");
      return;
    }

    if (isCustomMode) {
      if (!customName.trim()) {
        setError("Please enter a custom channel name");
        return;
      }
    } else {
      if (!selectedChannel) {
        setError("Please select a channel");
        return;
      }
    }

    const name = getChannelName();
    const channelType = isCustomMode ? "custom" : selectedChannel;

    try {
      await onCreate({ name, channel_type: channelType, feed_format: feedFormat });
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create channel");
    }
  }

  const canSubmit = isCustomMode
    ? !!selectedCountry && !!customName.trim()
    : !!selectedCountry && !!selectedChannel;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="wm-card w-full max-w-md p-6">
        <div className="mb-5 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-slate-900 dark:text-slate-100">Add Channel</h2>
          <button type="button" onClick={onClose} className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-300">
            <X className="h-5 w-5" />
          </button>
        </div>

        <form onSubmit={(e) => void handleSubmit(e)} className="space-y-4">
          {/* Country dropdown */}
          <div>
            <label htmlFor="ch-country" className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">
              Country <span className="text-red-500">*</span>
            </label>
            <select
              id="ch-country"
              value={selectedCountry}
              onChange={(e) => setSelectedCountry(e.target.value)}
              className="wm-input"
            >
              <option value="">Select a country</option>
              {COUNTRIES.map((c) => (
                <option key={c.id} value={c.id}>{c.name}</option>
              ))}
            </select>
          </div>

          {/* Channel dropdown OR custom mode */}
          {!isCustomMode ? (
            <div>
              <label htmlFor="ch-channel" className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">
                Channel <span className="text-red-500">*</span>
              </label>
              <select
                id="ch-channel"
                value={selectedChannel}
                onChange={(e) => setSelectedChannel(e.target.value)}
                disabled={!selectedCountry}
                className="wm-input disabled:cursor-not-allowed disabled:opacity-50"
              >
                <option value="">Select a channel</option>
                {channels && (
                  <>
                    <optgroup label="Most Popular Channels">
                      {channels.popular.map((ch) => (
                        <option key={ch.id} value={ch.id}>{ch.name}</option>
                      ))}
                    </optgroup>
                    <optgroup label="Other Channels">
                      {channels.other.map((ch) => (
                        <option key={ch.id} value={ch.id}>{ch.name}</option>
                      ))}
                    </optgroup>
                  </>
                )}
              </select>
            </div>
          ) : (
            <>
              <div>
                <label htmlFor="ch-custom-name" className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">
                  Custom Channel Name <span className="text-red-500">*</span>
                </label>
                <input
                  id="ch-custom-name"
                  type="text"
                  value={customName}
                  onChange={(e) => setCustomName(e.target.value)}
                  placeholder="e.g. My Custom Feed"
                  className="wm-input"
                  autoFocus
                />
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
            </>
          )}

          {/* OR separator + custom channel link */}
          {!isCustomMode && selectedCountry && (
            <div className="flex items-center gap-3">
              <div className="h-px flex-1 bg-slate-200 dark:bg-slate-700" />
              <span className="text-xs font-medium text-slate-400">OR</span>
              <div className="h-px flex-1 bg-slate-200 dark:bg-slate-700" />
            </div>
          )}
          {!isCustomMode && selectedCountry && (
            <div className="text-center">
              <button
                type="button"
                onClick={() => { setIsCustomMode(true); setSelectedChannel(""); }}
                className="text-sm text-indigo-600 hover:text-indigo-700 dark:text-indigo-400 dark:hover:text-indigo-300"
              >
                create a custom channel
              </button>
            </div>
          )}

          {error && (
            <p className="rounded-lg bg-red-50 p-2 text-xs text-red-600 dark:bg-red-900/20 dark:text-red-400">{error}</p>
          )}

          <div className="flex items-center justify-end gap-3 pt-2">
            <button
              type="button"
              onClick={isCustomMode ? () => setIsCustomMode(false) : onClose}
              className="wm-btn-secondary"
            >
              {isCustomMode ? "Back" : "Cancel"}
            </button>
            <button
              type="submit"
              className="wm-btn-primary"
              disabled={isCreating || !canSubmit}
            >
              {isCreating && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Create Channel
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
