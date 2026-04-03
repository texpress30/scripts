"use client";

import { useCallback, useEffect, useState } from "react";
import { Loader2, CheckCircle2, AlertCircle, X, Sparkles } from "lucide-react";
import { apiRequest } from "@/lib/api";

type AiSuggestion = {
  field_id: string;
  field_key: string;
  canonical_group: string;
  confidence: string;
  reason: string;
};

type GroupSummary = {
  canonical_group: string;
  members: string[];
};

type AnalyzeResult = {
  catalog_type: string;
  model_used: string;
  total_fields: number;
  suggestions: AiSuggestion[];
  groups_summary: GroupSummary[];
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
  const [confirmResult, setConfirmResult] = useState<{ updated_count: number } | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (open) {
      setModel(defaultModel);
      setResult(null);
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
      const updates = result.suggestions.map((s) => ({
        field_id: s.field_id,
        canonical_group: s.canonical_group,
        status: "confirmed",
      }));

      const data = await apiRequest<{ updated_count: number }>(
        "/feed-management/schemas/fields/bulk-canonical",
        {
          method: "POST",
          body: JSON.stringify({ updates }),
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
                <p className="font-semibold">Grupari canonice salvate!</p>
                <p>{confirmResult.updated_count} campuri actualizate cu grupari canonice.</p>
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
              Analizate <strong>{result.total_fields}</strong> campuri cu <strong>{MODEL_LABELS[result.model_used] ?? result.model_used}</strong>.
            </p>

            {result.groups_summary.length === 0 ? (
              <div className="rounded-lg border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-700 dark:border-emerald-800 dark:bg-emerald-900/20 dark:text-emerald-400">
                Fiecare camp are propriul canonic. Nu sunt grupari multi-camp detectate.
              </div>
            ) : (
              <div className="space-y-2">
                <p className="text-sm font-medium text-slate-700 dark:text-slate-300">
                  {result.groups_summary.length} grupuri canonice cu mai mult de 1 camp:
                </p>
                {result.groups_summary.map((g) => (
                  <div key={g.canonical_group} className="rounded-lg border border-indigo-200 bg-indigo-50/50 p-3 text-sm dark:border-indigo-800 dark:bg-indigo-900/20">
                    <p className="font-medium text-slate-800 dark:text-slate-200">
                      Canonic: <code className="font-mono text-xs text-indigo-600 dark:text-indigo-400">{g.canonical_group}</code>
                    </p>
                    <p className="mt-1 text-xs text-slate-600 dark:text-slate-400">
                      Campuri: {g.members.map((m) => (
                        <code key={m} className={`mr-1 rounded px-1 py-0.5 font-mono text-[10px] ${
                          m === g.canonical_group ? "bg-indigo-100 text-indigo-700" : "bg-slate-100 text-slate-600"
                        }`}>{m}</code>
                      ))}
                    </p>
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
                  disabled={confirming}
                  className="wm-btn-primary inline-flex items-center gap-2"
                >
                  {confirming ? <Loader2 className="h-4 w-4 animate-spin" /> : <CheckCircle2 className="h-4 w-4" />}
                  Accepta toate sugestiile
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
