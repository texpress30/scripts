"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Loader2, Upload, CheckCircle2, AlertCircle, X, AlertTriangle, Link2, Check, XIcon } from "lucide-react";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type ImportResult = {
  status: string;
  channel_slug: string;
  catalog_type: string;
  summary: {
    fields_added: number;
    fields_updated: number;
    fields_deprecated: number;
    total_fields_in_superset: number;
  };
  s3_path: string | null;
  import_id: string;
  format_detected: string | null;
  warnings: string[];
  fields_parsed: number;
};

type AiSuggestion = {
  new_field_key: string;
  canonical_key: string;
  confidence: string;
  reason: string;
  action: string;
};

type PreviewResult = {
  format_detected: string;
  fields_parsed: number;
  warnings: string[];
  categories: {
    exact_match: { field_key: string; status: string }[];
    ai_suggested_aliases: AiSuggestion[];
    new_fields: { field_key: string; display_name: string; data_type: string }[];
  };
  ai_suggestions_available: boolean;
};

type SubtypeOption = {
  id: string;
  subtype_slug: string;
  subtype_name: string;
  description: string | null;
};

type Props = {
  open: boolean;
  onClose: () => void;
  catalogType: string;
  channelSlug: string | null;
  subtypeSlug?: string | null;
  onImportSuccess: () => void;
};

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const FORMAT_OPTIONS = [
  { value: "auto", label: "Auto-detect (recomandat)" },
  { value: "meta_csv", label: "Meta CSV template" },
  { value: "tiktok_csv", label: "TikTok CSV template" },
  { value: "xml", label: "XML feed template" },
  { value: "custom", label: "Format custom (field_key, display_name)" },
];

const FORMAT_LABELS: Record<string, string> = {
  meta_csv: "Meta CSV template",
  tiktok_csv: "TikTok CSV template",
  xml: "XML feed template",
  custom: "Format custom CSV",
};

type Step = "form" | "confirm" | "result";

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function SchemaImportModal({
  open,
  onClose,
  catalogType,
  channelSlug,
  subtypeSlug: initialSubtypeSlug,
  onImportSuccess,
}: Props) {
  const [slug, setSlug] = useState(channelSlug ?? "");
  const [file, setFile] = useState<File | null>(null);
  const [templateFormat, setTemplateFormat] = useState("auto");
  const [selectedSubtype, setSelectedSubtype] = useState(initialSubtypeSlug ?? "");
  const [subtypeOptions, setSubtypeOptions] = useState<SubtypeOption[]>([]);
  const [loadingSubtypes, setLoadingSubtypes] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const [loading, setLoading] = useState(false);
  const [loadingMessage, setLoadingMessage] = useState("");
  const [result, setResult] = useState<ImportResult | null>(null);
  const [preview, setPreview] = useState<PreviewResult | null>(null);
  const [acceptedAliases, setAcceptedAliases] = useState<Record<string, boolean>>({});
  const [error, setError] = useState("");
  const [step, setStep] = useState<Step>("form");
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (open) {
      setSlug(channelSlug ?? "");
      setFile(null);
      setTemplateFormat("auto");
      setSelectedSubtype(initialSubtypeSlug ?? "");
      setResult(null);
      setPreview(null);
      setAcceptedAliases({});
      setError("");
      setLoading(false);
      setStep("form");
      setDragOver(false);

      // Fetch subtypes for this catalog type
      setLoadingSubtypes(true);
      const token = typeof window !== "undefined" ? localStorage.getItem("mcc_token") : null;
      fetch(`/api/feed-management/schemas/subtypes?catalog_type=${catalogType}`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      })
        .then((r) => r.ok ? r.json() : null)
        .then((data) => {
          if (data?.subtypes) setSubtypeOptions(data.subtypes);
          else setSubtypeOptions([]);
        })
        .catch(() => setSubtypeOptions([]))
        .finally(() => setLoadingSubtypes(false));
    }
  }, [open, channelSlug, catalogType, initialSubtypeSlug]);

  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => { if (e.key === "Escape") handleClose(); };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [open]);

  const handleClose = useCallback(() => {
    if (result) onImportSuccess();
    onClose();
  }, [result, onImportSuccess, onClose]);

  function handleDrop(e: React.DragEvent) {
    e.preventDefault(); setDragOver(false);
    const dropped = e.dataTransfer.files[0];
    if (dropped) setFile(dropped);
  }

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    setFile(e.target.files?.[0] ?? null);
  }

  function buildFormData() {
    const fd = new FormData();
    fd.append("channel_slug", slug.trim());
    fd.append("catalog_type", catalogType);
    fd.append("template_format", templateFormat);
    fd.append("file", file!);
    if (selectedSubtype) fd.append("subtype_slug", selectedSubtype);
    return fd;
  }

  function getToken() {
    return typeof window !== "undefined" ? localStorage.getItem("mcc_token") : null;
  }

  async function handleStartImport() {
    if (!file || !slug.trim()) return;
    setLoading(true);
    setError("");
    setLoadingMessage("Se analizeaza template-ul...");

    try {
      // Try preview first (AI suggestions)
      const token = getToken();
      const resp = await fetch("/api/feed-management/schemas/import/preview", {
        method: "POST",
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        body: buildFormData(),
      });

      if (!resp.ok) {
        // Preview failed — fall back to direct import
        await doDirectImport();
        return;
      }

      const data: PreviewResult = await resp.json();
      setPreview(data);

      // If AI has suggestions, show confirmation step
      if (data.ai_suggestions_available && data.categories.ai_suggested_aliases.length > 0) {
        const defaults: Record<string, boolean> = {};
        for (const s of data.categories.ai_suggested_aliases) {
          defaults[s.new_field_key] = s.confidence === "high";
        }
        setAcceptedAliases(defaults);
        setStep("confirm");
      } else {
        // No AI suggestions — import directly
        await doDirectImport();
      }
    } catch (err) {
      // Preview call failed — import directly
      await doDirectImport();
    } finally {
      setLoading(false);
    }
  }

  async function doDirectImport(confirmedAliases?: { new_field_key: string; canonical_key: string }[]) {
    setLoading(true);
    setError("");
    setLoadingMessage("Se importa...");

    try {
      const fd = buildFormData();
      if (confirmedAliases && confirmedAliases.length > 0) {
        fd.append("confirmed_aliases", JSON.stringify(confirmedAliases));
      }

      const token = getToken();
      const resp = await fetch("/api/feed-management/schemas/import", {
        method: "POST",
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        body: fd,
      });

      if (!resp.ok) {
        const body = await resp.json().catch(() => null);
        throw new Error(body?.detail ?? `Eroare HTTP ${resp.status}`);
      }

      const data: ImportResult = await resp.json();
      setResult(data);
      setStep("result");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Eroare la import.");
    } finally {
      setLoading(false);
    }
  }

  async function handleConfirmAndImport() {
    const confirmed = preview?.categories.ai_suggested_aliases
      .filter((s) => acceptedAliases[s.new_field_key])
      .map((s) => ({ new_field_key: s.new_field_key, canonical_key: s.canonical_key }))
      ?? [];
    await doDirectImport(confirmed);
  }

  async function handleSkipAndImport() {
    await doDirectImport();
  }

  if (!open) return null;

  const isChannelLocked = !!channelSlug;
  const canSubmit = !!file && slug.trim().length > 0 && !loading;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
      onClick={(e) => { if (e.target === e.currentTarget) handleClose(); }}
      role="dialog"
      aria-modal="true"
    >
      <div className="wm-card w-full max-w-2xl max-h-[85vh] overflow-y-auto p-6">
        {/* Header */}
        <div className="mb-5 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-slate-900 dark:text-slate-100">
            Import feed schema
          </h2>
          <button type="button" onClick={handleClose} className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-300">
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* STEP: RESULT */}
        {step === "result" && result ? (
          <div className="space-y-4">
            <div className="flex items-start gap-3 rounded-lg border border-emerald-200 bg-emerald-50 p-4 dark:border-emerald-800 dark:bg-emerald-900/20">
              <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0 text-emerald-600 dark:text-emerald-400" />
              <div className="text-sm">
                <p className="font-semibold text-emerald-800 dark:text-emerald-300">Import reusit!</p>
                <ul className="mt-2 space-y-1 text-emerald-700 dark:text-emerald-400">
                  {result.format_detected && <li>Format: <strong>{FORMAT_LABELS[result.format_detected] ?? result.format_detected}</strong></li>}
                  <li>Campuri parsate: <strong>{result.fields_parsed}</strong></li>
                  <li>Noi: <strong>{result.summary.fields_added}</strong> | Actualizate: <strong>{result.summary.fields_updated}</strong> | Depreciate: <strong>{result.summary.fields_deprecated}</strong></li>
                  <li>Total superset: <strong>{result.summary.total_fields_in_superset}</strong></li>
                </ul>
              </div>
            </div>
            {result.warnings.length > 0 && (
              <div className="flex items-start gap-2 rounded-lg border border-amber-200 bg-amber-50 p-3 dark:border-amber-800 dark:bg-amber-900/20">
                <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-amber-500" />
                <div className="text-sm text-amber-700 dark:text-amber-400">
                  {result.warnings.map((w, i) => <p key={i}>{w}</p>)}
                </div>
              </div>
            )}
            <div className="flex justify-end">
              <button type="button" onClick={handleClose} className="wm-btn-primary">Inchide</button>
            </div>
          </div>
        ) : step === "confirm" && preview ? (
          /* STEP: CONFIRM AI SUGGESTIONS */
          <div className="space-y-4">
            <p className="text-sm text-slate-600 dark:text-slate-400">
              Template analizat: <strong>{preview.fields_parsed} campuri</strong> ({FORMAT_LABELS[preview.format_detected] ?? preview.format_detected})
            </p>

            {/* Exact matches (collapsed) */}
            <div className="rounded-lg border border-slate-200 bg-slate-50 p-3 dark:border-slate-700 dark:bg-slate-800/50">
              <p className="text-sm text-slate-600 dark:text-slate-400">
                <CheckCircle2 className="mr-1 inline h-4 w-4 text-emerald-500" />
                <strong>{preview.categories.exact_match.length}</strong> campuri recunoscute automat (deja in superset)
              </p>
            </div>

            {/* AI suggestions (expanded, interactive) */}
            {preview.categories.ai_suggested_aliases.length > 0 && (
              <div className="rounded-lg border border-indigo-200 bg-indigo-50/50 p-3 dark:border-indigo-800 dark:bg-indigo-900/20">
                <div className="mb-3 flex items-center gap-2">
                  <Link2 className="h-4 w-4 text-indigo-500" />
                  <p className="text-sm font-semibold text-indigo-800 dark:text-indigo-300">
                    Sugestii AI — {preview.categories.ai_suggested_aliases.length} alias-uri detectate
                  </p>
                </div>
                <div className="space-y-2">
                  {preview.categories.ai_suggested_aliases.map((s) => (
                    <div
                      key={s.new_field_key}
                      className={`flex items-center gap-3 rounded-lg border p-2.5 text-sm ${
                        acceptedAliases[s.new_field_key]
                          ? "border-emerald-200 bg-emerald-50 dark:border-emerald-800 dark:bg-emerald-900/20"
                          : "border-slate-200 bg-white dark:border-slate-700 dark:bg-slate-900"
                      }`}
                    >
                      <div className="min-w-0 flex-1">
                        <p className="font-medium text-slate-800 dark:text-slate-200">
                          <code className="font-mono text-xs">{s.new_field_key}</code>
                          <span className="mx-1.5 text-slate-400">→</span>
                          <code className="font-mono text-xs text-indigo-600 dark:text-indigo-400">{s.canonical_key}</code>
                          <span className={`ml-2 rounded px-1 py-0.5 text-[10px] font-medium ${
                            s.confidence === "high"
                              ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-400"
                              : "bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-400"
                          }`}>
                            {s.confidence}
                          </span>
                        </p>
                        <p className="mt-0.5 text-xs text-slate-500 dark:text-slate-400">{s.reason}</p>
                      </div>
                      <div className="flex shrink-0 gap-1">
                        <button
                          type="button"
                          onClick={() => setAcceptedAliases((p) => ({ ...p, [s.new_field_key]: true }))}
                          className={`rounded p-1 ${acceptedAliases[s.new_field_key] ? "bg-emerald-500 text-white" : "text-slate-400 hover:text-emerald-500"}`}
                          title="Accepta"
                        >
                          <Check className="h-4 w-4" />
                        </button>
                        <button
                          type="button"
                          onClick={() => setAcceptedAliases((p) => ({ ...p, [s.new_field_key]: false }))}
                          className={`rounded p-1 ${!acceptedAliases[s.new_field_key] ? "bg-red-500 text-white" : "text-slate-400 hover:text-red-500"}`}
                          title="Respinge"
                        >
                          <XIcon className="h-4 w-4" />
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* New fields (collapsed) */}
            {preview.categories.new_fields.length > 0 && (
              <div className="rounded-lg border border-slate-200 bg-slate-50 p-3 dark:border-slate-700 dark:bg-slate-800/50">
                <p className="text-sm text-slate-600 dark:text-slate-400">
                  <span className="mr-1 text-indigo-500">+</span>
                  <strong>{preview.categories.new_fields.length}</strong> campuri noi vor fi adaugate in superset
                </p>
              </div>
            )}

            {error && (
              <div className="flex items-start gap-2 rounded-lg border border-red-200 bg-red-50 p-3 dark:border-red-800 dark:bg-red-900/20">
                <AlertCircle className="mt-0.5 h-4 w-4 shrink-0 text-red-500" />
                <p className="text-sm text-red-700 dark:text-red-400">{error}</p>
              </div>
            )}

            <div className="flex justify-end gap-2 pt-2">
              <button type="button" onClick={() => void handleSkipAndImport()} disabled={loading} className="wm-btn-secondary text-xs">
                Importa fara sugestii
              </button>
              <button
                type="button"
                onClick={() => void handleConfirmAndImport()}
                disabled={loading}
                className="wm-btn-primary inline-flex items-center gap-2"
              >
                {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <CheckCircle2 className="h-4 w-4" />}
                Confirma si Importa
              </button>
            </div>
          </div>
        ) : (
          /* STEP: FORM */
          <div className="space-y-4">
            <div>
              <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">Channel slug</label>
              {isChannelLocked ? (
                <input type="text" value={slug} readOnly className="wm-input bg-slate-50 dark:bg-slate-800" />
              ) : (
                <input type="text" value={slug} onChange={(e) => setSlug(e.target.value)} placeholder="ex: tiktok_auto_inventory" className="wm-input" />
              )}
            </div>

            <div>
              <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">Catalog type</label>
              <input type="text" value={catalogType} readOnly className="wm-input bg-slate-50 dark:bg-slate-800" />
            </div>

            {subtypeOptions.length > 0 && (
              <div>
                <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">Sub-type</label>
                <select
                  value={selectedSubtype}
                  onChange={(e) => setSelectedSubtype(e.target.value)}
                  className="wm-input h-9 w-full"
                  disabled={loadingSubtypes}
                >
                  <option value="">— Fara sub-type (generic) —</option>
                  {subtypeOptions.map((st) => (
                    <option key={st.subtype_slug} value={st.subtype_slug}>{st.subtype_name}</option>
                  ))}
                </select>
                <p className="mt-1 text-[11px] text-slate-400 dark:text-slate-500">
                  Sub-type-ul determina ce varianta a catalogului se foloseste. Ex: Vehicle Listings = inventar cu VIN, Vehicle Offers = cu finantare.
                </p>
              </div>
            )}

            <div>
              <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">Fisier CSV sau XML</label>
              <div
                className={`flex cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed px-6 py-8 transition-colors ${
                  dragOver
                    ? "border-indigo-400 bg-indigo-50 dark:border-indigo-600 dark:bg-indigo-900/20"
                    : "border-slate-300 bg-slate-50 hover:border-slate-400 dark:border-slate-600 dark:bg-slate-800 dark:hover:border-slate-500"
                }`}
                onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
                onDragLeave={() => setDragOver(false)}
                onDrop={handleDrop}
                onClick={() => fileInputRef.current?.click()}
              >
                <Upload className="mb-2 h-6 w-6 text-slate-400" />
                {file ? (
                  <p className="text-sm font-medium text-slate-700 dark:text-slate-300">
                    {file.name} <span className="text-slate-400">({(file.size / 1024).toFixed(1)} KB)</span>
                  </p>
                ) : (
                  <p className="text-sm text-slate-500 dark:text-slate-400">Trage CSV sau XML aici sau click pentru selectare</p>
                )}
                <input ref={fileInputRef} type="file" accept=".csv,.xml" className="hidden" onChange={handleFileChange} />
              </div>
            </div>

            <div>
              <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">Format</label>
              <select value={templateFormat} onChange={(e) => setTemplateFormat(e.target.value)} className="wm-input h-9 w-full">
                {FORMAT_OPTIONS.map((opt) => <option key={opt.value} value={opt.value}>{opt.label}</option>)}
              </select>
            </div>

            <p className="text-xs text-slate-400 dark:text-slate-500">
              Suporta: Meta CSV, TikTok CSV, XML feed, sau format custom. AI va sugera alias-uri automat daca e disponibil.
            </p>

            {error && (
              <div className="flex items-start gap-2 rounded-lg border border-red-200 bg-red-50 p-3 dark:border-red-800 dark:bg-red-900/20">
                <AlertCircle className="mt-0.5 h-4 w-4 shrink-0 text-red-500" />
                <p className="text-sm text-red-700 dark:text-red-400">{error}</p>
              </div>
            )}

            <div className="flex justify-end gap-2 pt-2">
              <button type="button" onClick={handleClose} className="wm-btn-secondary">Anuleaza</button>
              <button
                type="button"
                onClick={() => void handleStartImport()}
                disabled={!canSubmit}
                className="wm-btn-primary inline-flex items-center gap-2"
              >
                {loading ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    {loadingMessage}
                  </>
                ) : (
                  <>
                    <Upload className="h-4 w-4" />
                    Importa
                  </>
                )}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
