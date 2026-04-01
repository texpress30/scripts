"use client";

import { useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, RefreshCw, Copy, Trash2, Loader2 } from "lucide-react";
import { useCreativeTemplate, useCreativeTemplates } from "@/lib/hooks/useCreativeTemplates";
import type { CanvasElement, PreviewTemplateResponse } from "@/lib/types/creative-studio";

function formatDate(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString();
}

function extractBindings(elements: CanvasElement[]): string[] {
  const bindings = new Set<string>();
  for (const el of elements) {
    if (el.dynamic_binding) bindings.add(el.dynamic_binding);
  }
  return Array.from(bindings);
}

export default function TemplateDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const { template, isLoading, error } = useCreativeTemplate(params.id);
  const { deleteTemplate, duplicateTemplate, previewTemplate, isDeleting } = useCreativeTemplates();
  const [previewData, setPreviewData] = useState<Record<string, string>>({});
  const [previewResult, setPreviewResult] = useState<PreviewTemplateResponse | null>(null);
  const [previewing, setPreviewing] = useState(false);

  async function handleDelete() {
    if (!window.confirm("Sigur vrei sa stergi acest template?")) return;
    await deleteTemplate(params.id);
    router.push("/agency/creative-studio/templates");
  }

  async function handleDuplicate() {
    const newName = `${template?.name ?? "Template"} (copy)`;
    const dup = await duplicateTemplate(params.id, newName);
    router.push(`/agency/creative-studio/templates/${dup.id}`);
  }

  async function handlePreview() {
    setPreviewing(true);
    try {
      const result = await previewTemplate(params.id, { product_data: previewData });
      setPreviewResult(result);
    } catch {
      setPreviewResult(null);
    } finally {
      setPreviewing(false);
    }
  }

  if (isLoading) {
    return (<div className="flex items-center justify-center py-16"><Loader2 className="h-6 w-6 animate-spin text-slate-400" /></div>);
  }

  if (error || !template) {
    return (
      <div className="py-8">
        <Link href="/agency/creative-studio/templates" className="mb-4 inline-flex items-center gap-1 text-sm text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-300">
          <ArrowLeft className="h-4 w-4" /> Inapoi la templates
        </Link>
        <p className="text-red-600">{error ?? "Template-ul nu a fost gasit."}</p>
      </div>
    );
  }

  const bindings = extractBindings(template.elements);

  return (
    <>
      <Link href="/agency/creative-studio/templates" className="mb-4 inline-flex items-center gap-1 text-sm text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-300">
        <ArrowLeft className="h-4 w-4" /> Inapoi la templates
      </Link>

      {/* Header */}
      <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <h1 className="text-xl font-semibold text-slate-900 dark:text-slate-100">{template.name}</h1>
        <div className="flex items-center gap-2">
          <button type="button" onClick={() => void handleDuplicate()} className="wm-btn-secondary gap-2">
            <Copy className="h-4 w-4" /> Duplicate
          </button>
          <button type="button" onClick={() => void handleDelete()} disabled={isDeleting} className="inline-flex items-center gap-2 rounded-lg border border-red-200 bg-white px-4 py-2 text-sm font-medium text-red-600 transition hover:bg-red-50 dark:border-red-800 dark:bg-slate-900 dark:text-red-400 dark:hover:bg-red-900/20">
            {isDeleting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Trash2 className="h-4 w-4" />} Delete
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* Main content */}
        <div className="space-y-6 lg:col-span-2">
          {/* Canvas Preview */}
          <section className="wm-card p-6">
            <h2 className="mb-4 text-base font-semibold text-slate-900 dark:text-slate-100">Canvas Preview</h2>
            <div className="flex justify-center">
              <div
                className="rounded-lg border border-slate-200 dark:border-slate-700"
                style={{
                  width: Math.min(template.canvas_width, 500),
                  aspectRatio: `${template.canvas_width}/${template.canvas_height}`,
                  maxHeight: 500,
                  backgroundColor: template.background_color,
                }}
              />
            </div>
          </section>

          {/* Elements */}
          <section className="wm-card overflow-hidden">
            <div className="border-b border-slate-200 px-6 py-4 dark:border-slate-700">
              <h2 className="text-base font-semibold text-slate-900 dark:text-slate-100">Elements ({template.elements.length})</h2>
            </div>
            {template.elements.length === 0 ? (
              <div className="py-8 text-center text-sm text-slate-500 dark:text-slate-400">Nu exista elemente in acest template.</div>
            ) : (
              <div className="overflow-x-auto">
                <table className="min-w-full text-sm">
                  <thead className="bg-slate-100 text-left text-slate-600 dark:bg-slate-800 dark:text-slate-400">
                    <tr>
                      <th className="px-4 py-3">Type</th>
                      <th className="px-4 py-3">Position</th>
                      <th className="px-4 py-3">Size</th>
                      <th className="px-4 py-3">Binding</th>
                      <th className="px-4 py-3">Content</th>
                    </tr>
                  </thead>
                  <tbody>
                    {template.elements.map((el, idx) => (
                      <tr key={idx} className="border-t border-slate-100 dark:border-slate-800">
                        <td className="px-4 py-3">
                          <span className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${elementTypeStyle(el.type)}`}>{el.type}</span>
                        </td>
                        <td className="px-4 py-3 text-slate-600 dark:text-slate-400">{el.position_x}, {el.position_y}</td>
                        <td className="px-4 py-3 text-slate-600 dark:text-slate-400">{el.width}&times;{el.height}</td>
                        <td className="px-4 py-3">
                          {el.dynamic_binding ? (
                            <code className="rounded bg-indigo-50 px-1.5 py-0.5 text-xs text-indigo-700 dark:bg-indigo-900/30 dark:text-indigo-400">{el.dynamic_binding}</code>
                          ) : <span className="text-slate-400">&mdash;</span>}
                        </td>
                        <td className="px-4 py-3 text-slate-600 dark:text-slate-400">{el.content ? (el.content.length > 30 ? `${el.content.slice(0, 30)}...` : el.content) : "&mdash;"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>

          {/* Test Preview */}
          {bindings.length > 0 ? (
            <section className="wm-card p-6">
              <h2 className="mb-4 text-base font-semibold text-slate-900 dark:text-slate-100">Test Preview</h2>
              <p className="mb-3 text-sm text-slate-500 dark:text-slate-400">Introduce valori pentru campurile dinamice si genereaza un preview.</p>
              <div className="space-y-3">
                {bindings.map((binding) => {
                  const fieldName = binding.replace(/\{\{|\}\}/g, "");
                  return (
                    <div key={binding}>
                      <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">
                        <code className="rounded bg-slate-100 px-1 py-0.5 text-xs dark:bg-slate-800">{binding}</code>
                      </label>
                      <input
                        value={previewData[fieldName] ?? ""}
                        onChange={(e) => setPreviewData((prev) => ({ ...prev, [fieldName]: e.target.value }))}
                        placeholder={`Enter ${fieldName}...`}
                        className="wm-input"
                      />
                    </div>
                  );
                })}
              </div>
              <button type="button" onClick={() => void handlePreview()} disabled={previewing} className="wm-btn-primary mt-4 gap-2">
                {previewing ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
                Generate Preview
              </button>
              {previewResult ? (
                <pre className="mt-4 max-h-64 overflow-auto rounded-lg bg-slate-100 p-4 text-xs text-slate-700 dark:bg-slate-800 dark:text-slate-300">
                  {JSON.stringify(previewResult, null, 2)}
                </pre>
              ) : null}
            </section>
          ) : null}
        </div>

        {/* Sidebar */}
        <aside className="space-y-6">
          <section className="wm-card p-6">
            <h2 className="mb-4 text-base font-semibold text-slate-900 dark:text-slate-100">Metadata</h2>
            <dl className="space-y-3">
              <MetaRow label="Canvas Size">{template.canvas_width} &times; {template.canvas_height}px</MetaRow>
              <MetaRow label="Background">
                <span className="flex items-center gap-2">
                  <span className="inline-block h-4 w-4 rounded border border-slate-200 dark:border-slate-700" style={{ backgroundColor: template.background_color }} />
                  {template.background_color}
                </span>
              </MetaRow>
              <MetaRow label="Elements">{template.elements.length}</MetaRow>
              <MetaRow label="Dynamic Bindings">{bindings.length}</MetaRow>
              <MetaRow label="Created">{formatDate(template.created_at)}</MetaRow>
              <MetaRow label="Updated">{formatDate(template.updated_at)}</MetaRow>
            </dl>
          </section>

          {bindings.length > 0 ? (
            <section className="wm-card p-6">
              <h2 className="mb-3 text-base font-semibold text-slate-900 dark:text-slate-100">Dynamic Fields Used</h2>
              <div className="flex flex-wrap gap-2">
                {bindings.map((b) => (
                  <code key={b} className="rounded-full bg-indigo-50 px-2.5 py-1 text-xs font-medium text-indigo-700 dark:bg-indigo-900/30 dark:text-indigo-400">{b}</code>
                ))}
              </div>
            </section>
          ) : null}
        </aside>
      </div>
    </>
  );
}

function MetaRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <dt className="text-xs font-medium text-slate-500 dark:text-slate-400">{label}</dt>
      <dd className="mt-0.5 text-sm text-slate-700 dark:text-slate-300">{children}</dd>
    </div>
  );
}

function elementTypeStyle(type: string): string {
  switch (type) {
    case "text": return "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400";
    case "image": return "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400";
    case "shape": return "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400";
    case "dynamic_field": return "bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-400";
    default: return "bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-400";
  }
}
