"use client";

import { useState, useEffect, useMemo } from "react";
import { X, Loader2, Search, ChevronDown, ChevronRight, Check } from "lucide-react";
import {
  CHANNEL_PLATFORMS,
  CHANNEL_DISPLAY_NAMES,
  getPlatformBadgeColor,
  type Platform,
} from "@/lib/data/channel-platforms";

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
  /** Channels that already have schema imported (for the check indicator) */
  channelsWithSchema?: Set<string>;
};

export function AddChannelModal({ open, onClose, onCreate, isCreating, channelsWithSchema }: Props) {
  const [selectedChannel, setSelectedChannel] = useState<string | null>(null);
  const [isCustomMode, setIsCustomMode] = useState(false);
  const [customName, setCustomName] = useState("");
  const [feedFormat, setFeedFormat] = useState("xml");
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [collapsedPlatforms, setCollapsedPlatforms] = useState<Set<string>>(new Set());

  useEffect(() => {
    if (!open) return;
    setSelectedChannel(null);
    setIsCustomMode(false);
    setCustomName("");
    setFeedFormat("xml");
    setError(null);
    setSearchQuery("");
    setCollapsedPlatforms(new Set());
  }, [open]);

  // Filter platforms/channels based on search
  const filteredPlatforms = useMemo(() => {
    if (!searchQuery.trim()) return CHANNEL_PLATFORMS;
    const q = searchQuery.toLowerCase();
    return CHANNEL_PLATFORMS
      .map((p) => ({
        ...p,
        channels: p.channels.filter(
          (ch) =>
            ch.displayName.toLowerCase().includes(q) ||
            ch.slug.toLowerCase().includes(q) ||
            p.displayName.toLowerCase().includes(q),
        ),
      }))
      .filter((p) => p.channels.length > 0);
  }, [searchQuery]);

  function togglePlatform(platform: string) {
    setCollapsedPlatforms((prev) => {
      const next = new Set(prev);
      if (next.has(platform)) next.delete(platform);
      else next.add(platform);
      return next;
    });
  }

  function getSelectedDisplayName(): string {
    if (isCustomMode) return customName.trim();
    if (!selectedChannel) return "";
    return CHANNEL_DISPLAY_NAMES[selectedChannel] ?? selectedChannel;
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);

    if (isCustomMode) {
      if (!customName.trim()) {
        setError("Introdu un nume pentru canalul custom");
        return;
      }
    } else if (!selectedChannel) {
      setError("Selecteaza un canal");
      return;
    }

    const name = getSelectedDisplayName();
    const channelType = isCustomMode ? "custom" : selectedChannel!;

    try {
      await onCreate({ name, channel_type: channelType, feed_format: feedFormat });
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Eroare la crearea canalului");
    }
  }

  if (!open) return null;

  const canSubmit = isCustomMode ? !!customName.trim() : !!selectedChannel;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
      role="dialog"
      aria-modal="true"
    >
      <div className="wm-card flex w-full max-w-lg flex-col max-h-[85vh] overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-slate-200 px-6 py-4 dark:border-slate-700">
          <h2 className="text-lg font-semibold text-slate-900 dark:text-slate-100">
            {isCustomMode ? "Canal Custom" : "Selecteaza un canal"}
          </h2>
          <button type="button" onClick={onClose} className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-300">
            <X className="h-5 w-5" />
          </button>
        </div>

        {isCustomMode ? (
          /* Custom mode form */
          <form onSubmit={(e) => void handleSubmit(e)} className="flex flex-col gap-4 p-6">
            <div>
              <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">
                Nume canal <span className="text-red-500">*</span>
              </label>
              <input
                type="text"
                value={customName}
                onChange={(e) => setCustomName(e.target.value)}
                placeholder="ex: My Custom Feed"
                className="wm-input"
                autoFocus
              />
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">Format feed</label>
              <select value={feedFormat} onChange={(e) => setFeedFormat(e.target.value)} className="wm-input">
                {FEED_FORMATS.map((ff) => <option key={ff.value} value={ff.value}>{ff.label}</option>)}
              </select>
            </div>
            {error && <p className="rounded-lg bg-red-50 p-2 text-xs text-red-600 dark:bg-red-900/20 dark:text-red-400">{error}</p>}
            <div className="flex items-center justify-end gap-3 pt-2">
              <button type="button" onClick={() => setIsCustomMode(false)} className="wm-btn-secondary">Inapoi</button>
              <button type="submit" className="wm-btn-primary" disabled={isCreating || !canSubmit}>
                {isCreating && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                Creeaza Canal
              </button>
            </div>
          </form>
        ) : (
          /* Platform-grouped channel picker */
          <>
            {/* Search */}
            <div className="border-b border-slate-200 px-6 py-3 dark:border-slate-700">
              <div className="relative">
                <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
                <input
                  type="text"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="Cauta canal..."
                  className="wm-input pl-9"
                  autoFocus
                />
              </div>
            </div>

            {/* Channel list */}
            <div className="flex-1 overflow-y-auto px-6 py-3" style={{ maxHeight: "50vh" }}>
              {filteredPlatforms.length === 0 ? (
                <p className="py-6 text-center text-sm text-slate-400">Niciun canal gasit.</p>
              ) : (
                <div className="space-y-1">
                  {filteredPlatforms.map((platform) => {
                    const isCollapsed = collapsedPlatforms.has(platform.platform);
                    return (
                      <div key={platform.platform}>
                        {/* Platform header */}
                        <button
                          type="button"
                          onClick={() => togglePlatform(platform.platform)}
                          className="flex w-full items-center gap-2 rounded-lg px-2 py-2 text-left hover:bg-slate-50 dark:hover:bg-slate-800/50"
                        >
                          {isCollapsed ? (
                            <ChevronRight className="h-3.5 w-3.5 text-slate-400" />
                          ) : (
                            <ChevronDown className="h-3.5 w-3.5 text-slate-400" />
                          )}
                          <span className={`rounded px-1.5 py-0.5 text-[10px] font-semibold ${getPlatformBadgeColor(platform.platform)}`}>
                            {platform.displayName}
                          </span>
                          <span className="text-[10px] text-slate-400">({platform.channels.length})</span>
                        </button>

                        {/* Channels */}
                        {!isCollapsed && (
                          <div className="ml-5 space-y-0.5 pb-2">
                            {platform.channels.map((ch) => {
                              const isSelected = selectedChannel === ch.slug;
                              const hasSchema = channelsWithSchema?.has(ch.slug) ?? false;
                              return (
                                <button
                                  key={ch.slug}
                                  type="button"
                                  onClick={() => setSelectedChannel(ch.slug)}
                                  className={`flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-sm transition ${
                                    isSelected
                                      ? "bg-indigo-50 text-indigo-700 ring-1 ring-indigo-200 dark:bg-indigo-950/30 dark:text-indigo-400 dark:ring-indigo-800"
                                      : "text-slate-700 hover:bg-slate-50 dark:text-slate-300 dark:hover:bg-slate-800/50"
                                  }`}
                                >
                                  <span className={`flex h-4 w-4 shrink-0 items-center justify-center rounded-full border ${
                                    isSelected
                                      ? "border-indigo-500 bg-indigo-500 text-white"
                                      : "border-slate-300 dark:border-slate-600"
                                  }`}>
                                    {isSelected && <Check className="h-3 w-3" />}
                                  </span>
                                  <span className="flex-1">{ch.displayName}</span>
                                  {hasSchema && (
                                    <span className="rounded bg-emerald-100 px-1 py-0.5 text-[9px] font-medium text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400" title="Schema importata">
                                      Schema
                                    </span>
                                  )}
                                </button>
                              );
                            })}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}
            </div>

            {/* Separator + custom */}
            <div className="border-t border-slate-200 px-6 py-3 dark:border-slate-700">
              <div className="flex items-center gap-3 pb-3">
                <div className="h-px flex-1 bg-slate-200 dark:bg-slate-700" />
                <span className="text-xs font-medium text-slate-400">sau</span>
                <div className="h-px flex-1 bg-slate-200 dark:bg-slate-700" />
              </div>
              <button
                type="button"
                onClick={() => { setIsCustomMode(true); setSelectedChannel(null); }}
                className="w-full rounded-lg border border-dashed border-slate-300 px-3 py-2 text-center text-sm text-indigo-600 hover:border-indigo-300 hover:bg-indigo-50/50 dark:border-slate-600 dark:text-indigo-400 dark:hover:border-indigo-700 dark:hover:bg-indigo-900/10"
              >
                Creeaza canal custom
              </button>
            </div>

            {/* Footer */}
            <div className="border-t border-slate-200 px-6 py-4 dark:border-slate-700">
              {error && <p className="mb-3 rounded-lg bg-red-50 p-2 text-xs text-red-600 dark:bg-red-900/20 dark:text-red-400">{error}</p>}
              <div className="flex items-center justify-end gap-3">
                <div className="mr-auto flex items-center gap-2">
                  <label className="text-xs font-medium text-slate-500 dark:text-slate-400">Format</label>
                  <select value={feedFormat} onChange={(e) => setFeedFormat(e.target.value)} className="rounded border border-slate-300 bg-white px-2 py-1 text-xs text-slate-700 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-300">
                    {FEED_FORMATS.map((ff) => <option key={ff.value} value={ff.value}>{ff.label}</option>)}
                  </select>
                </div>
                <button type="button" onClick={onClose} className="wm-btn-secondary">Anuleaza</button>
                <button
                  type="button"
                  onClick={(e) => void handleSubmit(e as unknown as React.FormEvent)}
                  className="wm-btn-primary"
                  disabled={isCreating || !canSubmit}
                >
                  {isCreating && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                  Creeaza Canal
                </button>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
