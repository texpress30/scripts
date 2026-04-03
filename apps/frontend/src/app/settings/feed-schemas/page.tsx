"use client";

import { useCallback, useEffect, useState } from "react";
import { Loader2, Plus, Upload, Trash2, Link2, Sparkles } from "lucide-react";

import { AppShell } from "@/components/AppShell";
import { ProtectedPage } from "@/components/ProtectedPage";
import { SchemaImportModal } from "@/components/feed-management/SchemaImportModal";
import { SchemaAnalyzeModal } from "@/components/feed-management/SchemaAnalyzeModal";
import { apiRequest } from "@/lib/api";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type ChannelFieldInfo = {
  channel_slug: string;
  is_required: boolean;
  channel_field_name: string;
  source_description: string | null;
};

type SchemaField = {
  id: string;
  field_key: string;
  display_name: string;
  description: string | null;
  data_type: string;
  allowed_values: string[] | null;
  format_pattern: string | null;
  example_value: string | null;
  is_system: boolean;
  is_required: boolean;
  canonical_group: string | null;
  canonical_status: string | null;
  channels: ChannelFieldInfo[];
};

type FieldsResponse = {
  catalog_type: string;
  total_fields: number;
  required_count: number;
  optional_count: number;
  fields: SchemaField[];
};

type ChannelSummary = {
  channel_slug: string;
  fields_count: number;
  required_count: number;
  optional_count: number;
  last_imported_at: string | null;
};

type ChannelsResponse = {
  catalog_type: string;
  channels: ChannelSummary[];
};

type FieldAlias = {
  id: string;
  catalog_type: string;
  canonical_key: string;
  alias_key: string;
  platform_hint: string | null;
  created_at: string;
};

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const CATALOG_TYPES = [
  { value: "vehicle", label: "Vehicle" },
  { value: "product", label: "Product" },
  { value: "home_listing", label: "Home Listing" },
  { value: "hotel", label: "Hotel" },
  { value: "flight", label: "Flight" },
  { value: "media", label: "Media" },
];

const TYPE_BADGE_COLORS: Record<string, string> = {
  string: "bg-slate-100 text-slate-600 dark:bg-slate-700 dark:text-slate-300",
  number: "bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-400",
  url: "bg-teal-100 text-teal-700 dark:bg-teal-900/40 dark:text-teal-400",
  image_url: "bg-teal-100 text-teal-700 dark:bg-teal-900/40 dark:text-teal-400",
  price: "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-400",
  enum: "bg-purple-100 text-purple-700 dark:bg-purple-900/40 dark:text-purple-400",
  boolean: "bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-400",
  date: "bg-orange-100 text-orange-700 dark:bg-orange-900/40 dark:text-orange-400",
  html: "bg-rose-100 text-rose-700 dark:bg-rose-900/40 dark:text-rose-400",
};

const CHANNEL_COLORS: Record<string, string> = {
  google_vehicle_ads_v3: "bg-blue-100 text-blue-700",
  google_vehicle_listings: "bg-blue-50 text-blue-600",
  google_shopping: "bg-sky-100 text-sky-700",
  facebook_product_ads: "bg-indigo-100 text-indigo-700",
};

function formatChannelSlug(slug: string): string {
  return slug.replace(/_/g, " ").replace(/\bv\d+$/i, "").trim().replace(/\b\w/g, (c) => c.toUpperCase());
}

function timeAgo(dateStr: string | null): string {
  if (!dateStr) return "—";
  const d = new Date(dateStr);
  const now = new Date();
  const diffMs = now.getTime() - d.getTime();
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));
  if (diffDays < 1) return "Azi";
  if (diffDays === 1) return "Ieri";
  if (diffDays < 30) return `Acum ${diffDays} zile`;
  return d.toLocaleDateString("ro-RO");
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function FeedSchemasPage() {
  const [catalogType, setCatalogType] = useState("vehicle");
  const [fields, setFields] = useState<SchemaField[]>([]);
  const [channels, setChannels] = useState<ChannelSummary[]>([]);
  const [totalFields, setTotalFields] = useState(0);
  const [requiredCount, setRequiredCount] = useState(0);
  const [optionalCount, setOptionalCount] = useState(0);
  const [loadingFields, setLoadingFields] = useState(true);
  const [loadingChannels, setLoadingChannels] = useState(true);
  const [error, setError] = useState("");
  const [importModalOpen, setImportModalOpen] = useState(false);
  const [importChannelSlug, setImportChannelSlug] = useState<string | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);
  const [aliases, setAliases] = useState<FieldAlias[]>([]);
  const [loadingAliases, setLoadingAliases] = useState(true);
  const [newAliasCanonical, setNewAliasCanonical] = useState("");
  const [newAliasKey, setNewAliasKey] = useState("");
  const [newAliasPlatform, setNewAliasPlatform] = useState("");
  const [addingAlias, setAddingAlias] = useState(false);
  const [analyzeOpen, setAnalyzeOpen] = useState(false);
  const [aiEnabled, setAiEnabled] = useState(false);
  const [aiModel, setAiModel] = useState("claude-sonnet-4-20250514");
  const [aiModels, setAiModels] = useState<string[]>(["claude-sonnet-4-20250514"]);

  const handleOpenImport = useCallback((slug: string | null) => {
    setImportChannelSlug(slug);
    setImportModalOpen(true);
  }, []);

  const handleImportSuccess = useCallback(() => {
    setRefreshKey((k) => k + 1);
  }, []);

  // Fetch fields
  useEffect(() => {
    let ignore = false;
    async function load() {
      setLoadingFields(true);
      setError("");
      try {
        const res = await apiRequest<FieldsResponse>(
          `/feed-management/schemas/fields?catalog_type=${catalogType}`,
        );
        if (ignore) return;
        setFields(res.fields);
        setTotalFields(res.total_fields);
        setRequiredCount(res.required_count);
        setOptionalCount(res.optional_count);
      } catch (err) {
        if (ignore) return;
        setFields([]);
        setTotalFields(0);
        setRequiredCount(0);
        setOptionalCount(0);
        setError(err instanceof Error ? err.message : "Nu am putut incarca campurile.");
      } finally {
        if (!ignore) setLoadingFields(false);
      }
    }
    void load();
    return () => { ignore = true; };
  }, [catalogType, refreshKey]);

  // Fetch channels
  useEffect(() => {
    let ignore = false;
    async function load() {
      setLoadingChannels(true);
      try {
        const res = await apiRequest<ChannelsResponse>(
          `/feed-management/schemas/channels?catalog_type=${catalogType}`,
        );
        if (ignore) return;
        setChannels(res.channels);
      } catch {
        if (ignore) return;
        setChannels([]);
      } finally {
        if (!ignore) setLoadingChannels(false);
      }
    }
    void load();
    return () => { ignore = true; };
  }, [catalogType, refreshKey]);

  // Fetch AI status
  useEffect(() => {
    let ignore = false;
    async function load() {
      try {
        const res = await apiRequest<{ enabled: boolean; model: string; models_available: string[] }>(
          "/feed-management/schemas/ai-status",
        );
        if (ignore) return;
        setAiEnabled(res.enabled);
        setAiModel(res.model);
        setAiModels(res.models_available);
      } catch {
        if (ignore) return;
      }
    }
    void load();
    return () => { ignore = true; };
  }, []);

  // Fetch aliases
  useEffect(() => {
    let ignore = false;
    async function load() {
      setLoadingAliases(true);
      try {
        const res = await apiRequest<{ catalog_type: string; aliases: FieldAlias[] }>(
          `/feed-management/schemas/aliases?catalog_type=${catalogType}`,
        );
        if (ignore) return;
        setAliases(res.aliases);
      } catch {
        if (ignore) return;
        setAliases([]);
      } finally {
        if (!ignore) setLoadingAliases(false);
      }
    }
    void load();
    return () => { ignore = true; };
  }, [catalogType, refreshKey]);

  async function handleAddAlias() {
    if (!newAliasCanonical || !newAliasKey) return;
    setAddingAlias(true);
    try {
      await apiRequest("/feed-management/schemas/aliases", {
        method: "POST",
        body: JSON.stringify({
          catalog_type: catalogType,
          canonical_key: newAliasCanonical,
          alias_key: newAliasKey,
          platform_hint: newAliasPlatform || null,
        }),
      });
      setNewAliasCanonical("");
      setNewAliasKey("");
      setNewAliasPlatform("");
      setRefreshKey((k) => k + 1);
    } catch (err) {
      alert(err instanceof Error ? err.message : "Eroare la adaugare alias");
    } finally {
      setAddingAlias(false);
    }
  }

  async function handleDeleteAlias(id: string) {
    try {
      await apiRequest(`/feed-management/schemas/aliases/${id}`, { method: "DELETE" });
      setRefreshKey((k) => k + 1);
    } catch (err) {
      alert(err instanceof Error ? err.message : "Eroare la stergere alias");
    }
  }

  const catalogLabel = CATALOG_TYPES.find((c) => c.value === catalogType)?.label ?? catalogType;

  // Build alias lookup: canonical_key → list of alias_keys
  const aliasLookup = new Map<string, string[]>();
  for (const a of aliases) {
    const list = aliasLookup.get(a.canonical_key) ?? [];
    list.push(a.alias_key + (a.platform_hint ? ` (${a.platform_hint})` : ""));
    aliasLookup.set(a.canonical_key, list);
  }

  return (
    <ProtectedPage>
      <AppShell title="Feed Schemas">
        <main className="space-y-6 p-6">
          {/* Header */}
          <div>
            <h1 className="text-2xl font-semibold text-slate-900 dark:text-slate-100">Feed Schemas</h1>
            <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
              Gestioneaza specificatiile de campuri pentru fiecare canal de publicare.
            </p>
          </div>

          {/* Catalog type selector + global import button */}
          <div className="flex items-center gap-3">
            <label className="text-sm font-medium text-slate-700 dark:text-slate-300">Catalog Type:</label>
            <select
              value={catalogType}
              onChange={(e) => setCatalogType(e.target.value)}
              className="wm-input h-9 w-auto"
            >
              {CATALOG_TYPES.map((ct) => (
                <option key={ct.value} value={ct.value}>{ct.label}</option>
              ))}
            </select>
            <button
              type="button"
              onClick={() => handleOpenImport(null)}
              className="wm-btn-primary inline-flex items-center gap-1.5 text-sm"
            >
              <Plus className="h-4 w-4" />
              Import Canal Nou
            </button>
            <button
              type="button"
              onClick={() => setAnalyzeOpen(true)}
              disabled={!aiEnabled || totalFields === 0}
              className="wm-btn-secondary inline-flex items-center gap-1.5 text-sm"
              title={!aiEnabled ? "AI indisponibil — seteaza ANTHROPIC_API_KEY" : ""}
            >
              <Sparkles className="h-4 w-4" />
              Analizeaza cu AI
            </button>
            <span className={`text-xs ${aiEnabled ? "text-emerald-500" : "text-slate-400"}`}>
              {aiEnabled ? `AI activ` : "AI indisponibil"}
            </span>
          </div>

          {error && (
            <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700 dark:border-red-800 dark:bg-red-900/20 dark:text-red-400">
              {error}
            </div>
          )}

          {/* Summary card */}
          <div className="wm-card flex items-center gap-4 p-4 shadow-sm">
            <div>
              <h2 className="text-base font-semibold text-slate-900 dark:text-slate-100">
                {catalogLabel}
              </h2>
              {loadingFields ? (
                <p className="mt-0.5 text-sm text-slate-400">Se incarca...</p>
              ) : (
                <p className="mt-0.5 text-sm text-slate-500 dark:text-slate-400">
                  {totalFields} campuri ({requiredCount} obligatorii, {optionalCount} optionale)
                </p>
              )}
            </div>
          </div>

          {/* Channels table */}
          <section className="wm-card shadow-sm">
            <header className="border-b border-slate-100 p-4 dark:border-slate-700">
              <h2 className="text-base font-semibold text-slate-900 dark:text-slate-100">Canale</h2>
              <p className="mt-0.5 text-sm text-slate-500 dark:text-slate-400">
                Canalele care au specificatii de campuri definite pentru {catalogLabel}.
              </p>
            </header>
            <div className="overflow-x-auto">
              <table className="min-w-full text-sm">
                <thead className="bg-slate-50 text-left text-slate-600 dark:bg-slate-800/50 dark:text-slate-400">
                  <tr>
                    <th className="px-4 py-2.5">Canal</th>
                    <th className="px-4 py-2.5 text-center">Campuri</th>
                    <th className="px-4 py-2.5 text-center">Obligatorii</th>
                    <th className="px-4 py-2.5 text-center">Optionale</th>
                    <th className="px-4 py-2.5">Ultimul Import</th>
                    <th className="px-4 py-2.5">Actiuni</th>
                  </tr>
                </thead>
                <tbody>
                  {loadingChannels ? (
                    <tr>
                      <td colSpan={6} className="px-4 py-8 text-center text-slate-400">
                        <Loader2 className="mx-auto h-5 w-5 animate-spin" />
                      </td>
                    </tr>
                  ) : channels.length === 0 ? (
                    <tr>
                      <td colSpan={6} className="px-4 py-8 text-center text-slate-500 dark:text-slate-400">
                        Nu exista scheme de canale importate. Importa un CSV pentru a incepe.
                      </td>
                    </tr>
                  ) : (
                    channels.map((ch) => (
                      <tr key={ch.channel_slug} className="border-t border-slate-100 dark:border-slate-700">
                        <td className="px-4 py-2.5 font-medium text-slate-900 dark:text-slate-100">
                          {formatChannelSlug(ch.channel_slug)}
                          <span className="ml-2 font-mono text-[10px] text-slate-400">{ch.channel_slug}</span>
                        </td>
                        <td className="px-4 py-2.5 text-center text-slate-700 dark:text-slate-300">{ch.fields_count}</td>
                        <td className="px-4 py-2.5 text-center">
                          <span className="rounded bg-red-100 px-1.5 py-0.5 text-xs font-medium text-red-700 dark:bg-red-900/40 dark:text-red-400">
                            {ch.required_count}
                          </span>
                        </td>
                        <td className="px-4 py-2.5 text-center text-slate-500 dark:text-slate-400">{ch.optional_count}</td>
                        <td className="px-4 py-2.5 text-slate-500 dark:text-slate-400">{timeAgo(ch.last_imported_at)}</td>
                        <td className="px-4 py-2.5">
                          <button
                            type="button"
                            onClick={() => handleOpenImport(ch.channel_slug)}
                            className="wm-btn-secondary inline-flex items-center gap-1 text-xs"
                          >
                            <Upload className="h-3 w-3" />
                            {ch.last_imported_at ? "Re-import" : "Import CSV"}
                          </button>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </section>

          {/* All fields table */}
          <section className="wm-card shadow-sm">
            <header className="border-b border-slate-100 p-4 dark:border-slate-700">
              <h2 className="text-base font-semibold text-slate-900 dark:text-slate-100">
                Toate Campurile — {catalogLabel}
              </h2>
              <p className="mt-0.5 text-sm text-slate-500 dark:text-slate-400">
                Superset-ul de campuri disponibile din schema registry.
              </p>
            </header>
            <div className="overflow-x-auto">
              <table className="min-w-full text-sm">
                <thead className="bg-slate-50 text-left text-slate-600 dark:bg-slate-800/50 dark:text-slate-400">
                  <tr>
                    <th className="px-4 py-2.5">Field Key</th>
                    <th className="px-4 py-2.5">Canonic</th>
                    <th className="px-4 py-2.5">Nume</th>
                    <th className="px-4 py-2.5">Tip</th>
                    <th className="px-4 py-2.5 text-center">Status</th>
                    <th className="px-4 py-2.5">Canale</th>
                  </tr>
                </thead>
                <tbody>
                  {loadingFields ? (
                    <tr>
                      <td colSpan={6} className="px-4 py-8 text-center text-slate-400">
                        <Loader2 className="mx-auto h-5 w-5 animate-spin" />
                      </td>
                    </tr>
                  ) : fields.length === 0 ? (
                    <tr>
                      <td colSpan={6} className="px-4 py-8 text-center text-slate-500 dark:text-slate-400">
                        Nu exista campuri definite pentru {catalogLabel}.
                      </td>
                    </tr>
                  ) : (
                    fields.map((f) => (
                      <tr key={f.field_key} className="border-t border-slate-100 dark:border-slate-700">
                        <td className="px-4 py-2.5">
                          <code className="font-mono text-xs text-slate-800 dark:text-slate-200">{f.field_key}</code>
                          {f.is_system && (
                            <span className="ml-1.5 text-amber-500" title="System field">&#9733;</span>
                          )}
                          {aliasLookup.has(f.field_key) && (
                            <span
                              className="ml-1.5 cursor-help text-indigo-400"
                              title={`Aliases: ${aliasLookup.get(f.field_key)!.join(", ")}`}
                            >
                              <Link2 className="inline h-3 w-3" />
                            </span>
                          )}
                        </td>
                        <td className={`px-4 py-2.5 ${f.canonical_status === "suggested" ? "bg-amber-50 dark:bg-amber-900/10" : ""}`}>
                          {f.canonical_group && f.canonical_group !== f.field_key ? (
                            <span className="text-xs text-indigo-600 dark:text-indigo-400">
                              → <code className="font-mono">{f.canonical_group}</code>
                            </span>
                          ) : f.canonical_group ? (
                            <code className="font-mono text-xs font-semibold text-slate-700 dark:text-slate-300">{f.canonical_group}</code>
                          ) : (
                            <span className="text-xs text-slate-400">—</span>
                          )}
                        </td>
                        <td className="px-4 py-2.5 text-slate-700 dark:text-slate-300">{f.display_name}</td>
                        <td className="px-4 py-2.5">
                          <span className={`inline-block rounded px-1.5 py-0.5 text-[11px] font-medium ${TYPE_BADGE_COLORS[f.data_type] ?? TYPE_BADGE_COLORS.string}`}>
                            {f.data_type}
                          </span>
                        </td>
                        <td className="px-4 py-2.5 text-center">
                          {f.is_required ? (
                            <span className="rounded bg-red-100 px-1.5 py-0.5 text-[11px] font-semibold text-red-700 dark:bg-red-900/40 dark:text-red-400">
                              Obligatoriu
                            </span>
                          ) : (
                            <span className="rounded bg-slate-100 px-1.5 py-0.5 text-[11px] font-medium text-slate-500 dark:bg-slate-700 dark:text-slate-400">
                              Optional
                            </span>
                          )}
                        </td>
                        <td className="px-4 py-2.5">
                          <div className="flex flex-wrap gap-1">
                            {f.channels.map((ch) => (
                              <span
                                key={ch.channel_slug}
                                className={`inline-block rounded px-1.5 py-0.5 text-[10px] font-medium ${CHANNEL_COLORS[ch.channel_slug] ?? "bg-slate-100 text-slate-600 dark:bg-slate-700 dark:text-slate-400"}`}
                                title={`${ch.channel_slug} — ${ch.is_required ? "obligatoriu" : "optional"}`}
                              >
                                {formatChannelSlug(ch.channel_slug)}
                              </span>
                            ))}
                          </div>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </section>
          {/* Aliases section removed — canonical grouping is now inline in the fields table */}
          {false && <section className="wm-card shadow-sm">
            <header className="border-b border-slate-100 p-4 dark:border-slate-700">
              <div className="flex items-center gap-2">
                <Link2 className="h-4 w-4 text-slate-400" />
                <h2 className="text-base font-semibold text-slate-900 dark:text-slate-100">
                  Alias-uri Campuri — {catalogLabel}
                </h2>
              </div>
              <p className="mt-0.5 text-sm text-slate-500 dark:text-slate-400">
                Unifica campuri care au nume diferite pe platforme diferite (ex: vehicle_offer_id = vehicle_id).
              </p>
            </header>

            <div className="overflow-x-auto">
              <table className="min-w-full text-sm">
                <thead className="bg-slate-50 text-left text-slate-600 dark:bg-slate-800/50 dark:text-slate-400">
                  <tr>
                    <th className="px-4 py-2.5">Camp Canonic</th>
                    <th className="px-4 py-2.5">Alias</th>
                    <th className="px-4 py-2.5">Platforma</th>
                    <th className="px-4 py-2.5 w-16"></th>
                  </tr>
                </thead>
                <tbody>
                  {loadingAliases ? (
                    <tr>
                      <td colSpan={4} className="px-4 py-6 text-center text-slate-400">
                        <Loader2 className="mx-auto h-5 w-5 animate-spin" />
                      </td>
                    </tr>
                  ) : aliases.length === 0 ? (
                    <tr>
                      <td colSpan={4} className="px-4 py-6 text-center text-slate-500 dark:text-slate-400">
                        Nu exista alias-uri pentru {catalogLabel}.
                      </td>
                    </tr>
                  ) : (
                    aliases.map((a) => (
                      <tr key={a.id} className="border-t border-slate-100 dark:border-slate-700">
                        <td className="px-4 py-2">
                          <code className="font-mono text-xs text-slate-800 dark:text-slate-200">{a.canonical_key}</code>
                        </td>
                        <td className="px-4 py-2">
                          <code className="font-mono text-xs text-indigo-600 dark:text-indigo-400">{a.alias_key}</code>
                        </td>
                        <td className="px-4 py-2 text-slate-500 dark:text-slate-400">{a.platform_hint ?? "—"}</td>
                        <td className="px-4 py-2">
                          <button
                            type="button"
                            onClick={() => void handleDeleteAlias(a.id)}
                            className="text-slate-400 hover:text-red-500"
                            title="Sterge alias"
                          >
                            <Trash2 className="h-3.5 w-3.5" />
                          </button>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>

            {/* Add alias form */}
            <div className="flex flex-wrap items-end gap-2 border-t border-slate-100 p-4 dark:border-slate-700">
              <div>
                <label className="mb-1 block text-xs font-medium text-slate-600 dark:text-slate-400">Camp Canonic</label>
                <select
                  value={newAliasCanonical}
                  onChange={(e) => setNewAliasCanonical(e.target.value)}
                  className="wm-input h-8 w-44 text-xs"
                >
                  <option value="">— Selecteaza —</option>
                  {fields.map((f) => (
                    <option key={f.field_key} value={f.field_key}>{f.field_key}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="mb-1 block text-xs font-medium text-slate-600 dark:text-slate-400">Alias Key</label>
                <input
                  type="text"
                  value={newAliasKey}
                  onChange={(e) => setNewAliasKey(e.target.value)}
                  placeholder="ex: vehicle_offer_id"
                  className="wm-input h-8 w-44 text-xs"
                />
              </div>
              <div>
                <label className="mb-1 block text-xs font-medium text-slate-600 dark:text-slate-400">Platforma</label>
                <input
                  type="text"
                  value={newAliasPlatform}
                  onChange={(e) => setNewAliasPlatform(e.target.value)}
                  placeholder="meta, tiktok..."
                  className="wm-input h-8 w-32 text-xs"
                />
              </div>
              <button
                type="button"
                onClick={() => void handleAddAlias()}
                disabled={!newAliasCanonical || !newAliasKey || addingAlias}
                className="wm-btn-secondary inline-flex h-8 items-center gap-1 text-xs"
              >
                {addingAlias ? <Loader2 className="h-3 w-3 animate-spin" /> : <Plus className="h-3 w-3" />}
                Adauga
              </button>
            </div>
          </section>}

          {/* Analyze modal */}
          <SchemaAnalyzeModal
            open={analyzeOpen}
            onClose={() => setAnalyzeOpen(false)}
            catalogType={catalogType}
            onSuccess={handleImportSuccess}
            modelsAvailable={aiModels}
            defaultModel={aiModel}
          />

          {/* Import modal */}
          <SchemaImportModal
            open={importModalOpen}
            onClose={() => setImportModalOpen(false)}
            catalogType={catalogType}
            channelSlug={importChannelSlug}
            onImportSuccess={handleImportSuccess}
          />
        </main>
      </AppShell>
    </ProtectedPage>
  );
}
