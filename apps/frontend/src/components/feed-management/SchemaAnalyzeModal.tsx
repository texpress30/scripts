"use client";

import { useCallback, useEffect, useState } from "react";
import { Loader2, CheckCircle2, AlertCircle, X, Check, XIcon, Sparkles } from "lucide-react";
import { apiRequest } from "@/lib/api";

type AiGroup = {
  canonical_key: string;
  duplicates: string[];
  confidence: string;
  reason: string;
  action: string;
};

type AnalyzeResult = {
  catalog_type: string;
  model_used: string;
  total_fields_analyzed: number;
  existing_aliases_skipped: number;
  suggestions: AiGroup[];
  ai_available: boolean;
};

type Props = {
  open: boolean;
  onClose: () => void;
  catalogType: string;
  onSuccess: () => void;
  modelsAvailable: string[];
  defaultModel: string;
};

const MODEL_LABELS: Record<string, string> = {
  "claude-sonnet-4-20250514": "Claude Sonnet 4 (recomandat)",
  "claude-haiku-4-5-20251001": "Claude Haiku 4.5 (rapid)",
  "claude-opus-4-6": "Claude Opus 4 (cel mai precis)",
};

export function SchemaAnalyzeModal({
  open,
  onClose,
  catalogType,
  onSuccess,
  modelsAvailable,
  defaultModel,
}: Props) {
  const [model, setModel] = useState(defaultModel);
  const [analyzing, setAnalyzing] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [result, setResult] = useState<AnalyzeResult | null>(null);
  const [accepted, setAccepted] = useState<Record<string, boolean>>({});
  const [confirmResult, setConfirmResult] = useState<{ aliases_created: number; fields_merged: number } | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (open) {
      setModel(defaultModel);
      setResult(null);
      setAccepted({});
      setConfirmResult(null);
      setError("");
      setAnalyzing(false);
      setConfirming(false);
    }
  }, [open, defaultModel]);

  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => { if (e.key === "Escape") handleClose(); };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [open]);

  const handleClose = useCallback(() => {
    if (confirmResult) onSuccess();
    onClose();
  }, [confirmResult, onSuccess, onClose]);

  async function handleAnalyze() {
    setAnalyzing(true);
    setError("");
    setResult(null);
    try {
      const fd = new FormData();
      fd.append("catalog_type", catalogType);
      fd.append("model", model);

      const token = typeof window !== "undefined" ? localStorage.getItem("mcc_token") : null;
      const resp = await fetch("/api/feed-management/schemas/analyze", {
        method: "POST",
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        body: fd,
      });
      if (!resp.ok) {
        const body = await resp.json().catch(() => null);
        throw new Error(body?.detail ?? `Eroare HTTP ${resp.status}`);
      }
      const data: AnalyzeResult = await resp.json();
      setResult(data);
      const defaults: Record<string, boolean> = {};
      for (const s of data.suggestions) {
        defaults[s.canonical_key] = s.confidence === "high";
      }
      setAccepted(defaults);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Eroare la analiza AI.");
    } finally {
      setAnalyzing(false);
    }
  }

  async function handleConfirm() {
    if (!result) return;
    setConfirming(true);
    setError("");
    try {
      const groups = result.suggestions
        .filter((s) => accepted[s.canonical_key])
        .map((s) => ({
          canonical_key: s.canonical_key,
          aliases: s.duplicates.filter((d) => d !== s.canonical_key),
        }));

      const data = await apiRequest<{ aliases_created: number; fields_merged: number }>(
        "/feed-management/schemas/analyze/confirm",
        {
          method: "POST",
          body: JSON.stringify({ catalog_type: catalogType, confirmed_groups: groups }),
        },
      );
      setConfirmResult(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Eroare la confirmare.");
    } finally {
      setConfirming(false);
    }
  }

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
      onClick={(e) => { if (e.target === e.currentTarget) handleClose(); }}
      role="dialog"
      aria-modal="true"
    >
      <div className="wm-card w-full max-w-2xl max-h-[85vh] overflow-y-auto p-6">
        <div className="mb-5 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-slate-900 dark:text-slate-100">
            <Sparkles className="mr-1.5 inline h-5 w-5 text-indigo-500" />
            Analiza AI — {catalogType.replace("_", " ").replace(/\b\w/g, (c) => c.toUpperCase())}
          </h2>
          <button type="button" onClick={handleClose} className="text-slate-400 hover:text-slate-600">
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Confirm result */}
        {confirmResult ? (
          <div className="space-y-4">
            <div className="flex items-start gap-3 rounded-lg border border-emerald-200 bg-emerald-50 p-4 dark:border-emerald-800 dark:bg-emerald-900/20">
              <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0 text-emerald-600" />
              <div className="text-sm text-emerald-700 dark:text-emerald-400">
                <p className="font-semibold">Merge reusit!</p>
                <p>{confirmResult.aliases_created} alias-uri create, {confirmResult.fields_merged} campuri unificate.</p>
              </div>
            </div>
            <div className="flex justify-end">
              <button type="button" onClick={handleClose} className="wm-btn-primary">Inchide</button>
            </div>
          </div>
        ) : result ? (
          /* Analysis results */
          <div className="space-y-4">
            <p className="text-sm text-slate-500 dark:text-slate-400">
              Analizate <strong>{result.total_fields_analyzed}</strong> campuri cu <strong>{MODEL_LABELS[result.model_used] ?? result.model_used}</strong>.
              {result.existing_aliases_skipped > 0 && ` ${result.existing_aliases_skipped} alias-uri existente ignorate.`}
            </p>

            {result.suggestions.length === 0 ? (
              <div className="rounded-lg border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-700 dark:border-emerald-800 dark:bg-emerald-900/20 dark:text-emerald-400">
                Nu am gasit campuri duplicate. Superset-ul pare curat.
              </div>
            ) : (
              <div className="space-y-2">
                <p className="text-sm font-medium text-slate-700 dark:text-slate-300">
                  {result.suggestions.length} grupuri duplicate gasite:
                </p>
                {result.suggestions.map((s) => (
                  <div
                    key={s.canonical_key}
                    className={`rounded-lg border p-3 text-sm ${
                      accepted[s.canonical_key]
                        ? "border-emerald-200 bg-emerald-50 dark:border-emerald-800 dark:bg-emerald-900/20"
                        : "border-slate-200 bg-white dark:border-slate-700 dark:bg-slate-900"
                    }`}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="min-w-0 flex-1">
                        <p className="font-medium text-slate-800 dark:text-slate-200">
                          Canonic: <code className="font-mono text-xs text-indigo-600 dark:text-indigo-400">{s.canonical_key}</code>
                          <span className={`ml-2 rounded px-1 py-0.5 text-[10px] font-medium ${
                            s.confidence === "high"
                              ? "bg-emerald-100 text-emerald-700"
                              : "bg-amber-100 text-amber-700"
                          }`}>{s.confidence}</span>
                        </p>
                        <p className="mt-0.5 text-xs text-slate-500 dark:text-slate-400">{s.reason}</p>
                        <p className="mt-1 text-xs text-slate-600 dark:text-slate-400">
                          Campuri: {s.duplicates.map((d) => (
                            <code key={d} className={`mr-1 rounded px-1 py-0.5 font-mono text-[10px] ${
                              d === s.canonical_key ? "bg-indigo-100 text-indigo-700" : "bg-slate-100 text-slate-600"
                            }`}>{d}</code>
                          ))}
                        </p>
                      </div>
                      <div className="flex shrink-0 gap-1">
                        <button
                          type="button"
                          onClick={() => setAccepted((p) => ({ ...p, [s.canonical_key]: true }))}
                          className={`rounded p-1 ${accepted[s.canonical_key] ? "bg-emerald-500 text-white" : "text-slate-400 hover:text-emerald-500"}`}
                        >
                          <Check className="h-4 w-4" />
                        </button>
                        <button
                          type="button"
                          onClick={() => setAccepted((p) => ({ ...p, [s.canonical_key]: false }))}
                          className={`rounded p-1 ${!accepted[s.canonical_key] ? "bg-red-500 text-white" : "text-slate-400 hover:text-red-500"}`}
                        >
                          <XIcon className="h-4 w-4" />
                        </button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}

            {error && (
              <div className="flex items-start gap-2 rounded-lg border border-red-200 bg-red-50 p-3">
                <AlertCircle className="mt-0.5 h-4 w-4 shrink-0 text-red-500" />
                <p className="text-sm text-red-700">{error}</p>
              </div>
            )}

            <div className="flex justify-end gap-2 pt-2">
              <button type="button" onClick={handleClose} className="wm-btn-secondary">Anuleaza</button>
              {result.suggestions.length > 0 && (
                <button
                  type="button"
                  onClick={() => void handleConfirm()}
                  disabled={confirming || !Object.values(accepted).some(Boolean)}
                  className="wm-btn-primary inline-flex items-center gap-2"
                >
                  {confirming ? <Loader2 className="h-4 w-4 animate-spin" /> : <CheckCircle2 className="h-4 w-4" />}
                  Confirma merge-urile
                </button>
              )}
            </div>
          </div>
        ) : (
          /* Pre-analysis form */
          <div className="space-y-4">
            <div>
              <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">Model AI</label>
              <select value={model} onChange={(e) => setModel(e.target.value)} className="wm-input h-9 w-full">
                {modelsAvailable.map((m) => (
                  <option key={m} value={m}>{MODEL_LABELS[m] ?? m}</option>
                ))}
              </select>
              <p className="mt-1 text-xs text-slate-400">Sonnet ofera cel mai bun echilibru intre calitate si cost.</p>
            </div>

            {error && (
              <div className="flex items-start gap-2 rounded-lg border border-red-200 bg-red-50 p-3">
                <AlertCircle className="mt-0.5 h-4 w-4 shrink-0 text-red-500" />
                <p className="text-sm text-red-700">{error}</p>
              </div>
            )}

            <div className="flex justify-end gap-2 pt-2">
              <button type="button" onClick={handleClose} className="wm-btn-secondary">Anuleaza</button>
              <button
                type="button"
                onClick={() => void handleAnalyze()}
                disabled={analyzing}
                className="wm-btn-primary inline-flex items-center gap-2"
              >
                {analyzing ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Se analizeaza...
                  </>
                ) : (
                  <>
                    <Sparkles className="h-4 w-4" />
                    Lanseaza Analiza
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
