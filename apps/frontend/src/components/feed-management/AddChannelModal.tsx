"use client";

import { useState, useEffect } from "react";
import { X, Loader2, ChevronDown, Search } from "lucide-react";
import {
  COUNTRIES,
  getChannelsForCountry,
  getCountryISOCode,
  type Channel,
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
  const [customName, setCustomName] = useState("");
  const [feedFormat, setFeedFormat] = useState("xml");
  const [countrySearch, setCountrySearch] = useState("");
  const [error, setError] = useState<string | null>(null);

  // Reset channel when country changes
  useEffect(() => {
    setSelectedChannel("");
    setCustomName("");
  }, [selectedCountry]);

  // Reset all state when modal closes/opens
  useEffect(() => {
    if (!open) return;
    setSelectedCountry("");
    setSelectedChannel("");
    setCustomName("");
    setFeedFormat("xml");
    setCountrySearch("");
    setError(null);
  }, [open]);

  if (!open) return null;

  const channels = selectedCountry ? getChannelsForCountry(selectedCountry) : null;
  const isCustom = selectedChannel === "custom";
  const isoCode = selectedCountry ? getCountryISOCode(selectedCountry) : "";

  // Build the auto-generated channel name
  function getAutoName(): string {
    if (isCustom) return customName;
    if (!selectedChannel || !channels) return "";
    const all = [...channels.popular, ...channels.other];
    const ch = all.find((c) => c.id === selectedChannel);
    if (!ch) return "";
    return isoCode ? `${ch.name} (${isoCode})` : ch.name;
  }

  const filteredCountries = countrySearch
    ? COUNTRIES.filter((c) => c.name.toLowerCase().includes(countrySearch.toLowerCase()))
    : COUNTRIES;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);

    if (!selectedCountry) {
      setError("Please select a country");
      return;
    }
    if (!selectedChannel) {
      setError("Please select a channel");
      return;
    }
    if (isCustom && !customName.trim()) {
      setError("Please enter a custom channel name");
      return;
    }

    const name = getAutoName();
    try {
      await onCreate({ name, channel_type: selectedChannel, feed_format: feedFormat });
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create channel");
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="wm-card w-full max-w-lg p-6">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-slate-900 dark:text-slate-100">Add Channel</h2>
          <button type="button" onClick={onClose} className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-300">
            <X className="h-5 w-5" />
          </button>
        </div>

        <form onSubmit={(e) => void handleSubmit(e)} className="space-y-4">
          {/* Step 1: Country */}
          <div>
            <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">
              Country
            </label>
            <div className="relative">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
              <input
                type="text"
                value={
                  selectedCountry && !countrySearch
                    ? COUNTRIES.find((c) => c.id === selectedCountry)?.name ?? ""
                    : countrySearch
                }
                onChange={(e) => {
                  setCountrySearch(e.target.value);
                  if (selectedCountry) setSelectedCountry("");
                }}
                onFocus={() => {
                  if (selectedCountry) {
                    setCountrySearch(COUNTRIES.find((c) => c.id === selectedCountry)?.name ?? "");
                    setSelectedCountry("");
                  }
                }}
                placeholder="Search country..."
                className="wm-input pl-9"
                autoFocus
              />
            </div>
            {!selectedCountry && countrySearch && (
              <div className="mt-1 max-h-40 overflow-y-auto rounded-lg border border-slate-200 bg-white dark:border-slate-700 dark:bg-slate-900">
                {filteredCountries.length === 0 ? (
                  <p className="px-3 py-2 text-xs text-slate-400">No countries found</p>
                ) : (
                  filteredCountries.map((country) => (
                    <button
                      key={country.id}
                      type="button"
                      onClick={() => {
                        setSelectedCountry(country.id);
                        setCountrySearch("");
                      }}
                      className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm hover:bg-slate-50 dark:hover:bg-slate-800"
                    >
                      <span className="font-mono text-[10px] text-slate-400">{getCountryISOCode(country.id)}</span>
                      <span className="text-slate-900 dark:text-slate-100">{country.name}</span>
                    </button>
                  ))
                )}
              </div>
            )}
          </div>

          {/* Step 2: Channel selection (only after country is selected) */}
          {selectedCountry && channels && (
            <div>
              <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">
                Channel
              </label>

              {/* Popular */}
              <p className="mb-1.5 text-[11px] font-semibold uppercase tracking-wider text-slate-400">
                Most Popular
              </p>
              <div className="mb-3 grid grid-cols-2 gap-1.5">
                {channels.popular.map((ch) => (
                  <button
                    key={ch.id}
                    type="button"
                    onClick={() => setSelectedChannel(ch.id)}
                    className={`rounded-lg border px-3 py-2 text-left text-sm transition ${
                      selectedChannel === ch.id
                        ? "border-indigo-500 bg-indigo-50 text-indigo-700 dark:border-indigo-400 dark:bg-indigo-900/30 dark:text-indigo-400"
                        : "border-slate-200 text-slate-700 hover:border-slate-300 dark:border-slate-700 dark:text-slate-300 dark:hover:border-slate-600"
                    }`}
                  >
                    {ch.name}
                  </button>
                ))}
              </div>

              {/* Other */}
              <p className="mb-1.5 text-[11px] font-semibold uppercase tracking-wider text-slate-400">
                Other Channels
              </p>
              <div className="grid grid-cols-2 gap-1.5">
                {channels.other.map((ch) => (
                  <button
                    key={ch.id}
                    type="button"
                    onClick={() => setSelectedChannel(ch.id)}
                    className={`rounded-lg border px-3 py-2 text-left text-sm transition ${
                      selectedChannel === ch.id
                        ? "border-indigo-500 bg-indigo-50 text-indigo-700 dark:border-indigo-400 dark:bg-indigo-900/30 dark:text-indigo-400"
                        : "border-slate-200 text-slate-700 hover:border-slate-300 dark:border-slate-700 dark:text-slate-300 dark:hover:border-slate-600"
                    }`}
                  >
                    {ch.name}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Step 3: Custom channel name (only for "custom") */}
          {isCustom && (
            <div>
              <label htmlFor="ch-custom-name" className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">
                Custom Channel Name
              </label>
              <input
                id="ch-custom-name"
                type="text"
                value={customName}
                onChange={(e) => setCustomName(e.target.value)}
                placeholder="e.g. My Custom Feed"
                className="wm-input"
              />
            </div>
          )}

          {/* Feed format (shown after channel selection) */}
          {selectedChannel && (
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
          )}

          {/* Preview name */}
          {selectedChannel && !isCustom && (
            <div className="rounded-lg bg-slate-50 px-3 py-2 dark:bg-slate-800">
              <span className="text-[11px] font-medium text-slate-400">Channel name: </span>
              <span className="text-sm font-medium text-slate-900 dark:text-slate-100">{getAutoName()}</span>
            </div>
          )}

          {error && (
            <p className="rounded-lg bg-red-50 p-2 text-xs text-red-600 dark:bg-red-900/20 dark:text-red-400">{error}</p>
          )}

          <div className="flex items-center justify-end gap-3 pt-2">
            <button type="button" onClick={onClose} className="wm-btn-secondary">
              Cancel
            </button>
            <button
              type="submit"
              className="wm-btn-primary"
              disabled={isCreating || !selectedCountry || !selectedChannel}
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
