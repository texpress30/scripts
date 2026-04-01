"use client";

import Link from "next/link";
import { Plus, Loader2 } from "lucide-react";
import { useCreativeTemplates } from "@/lib/hooks/useCreativeTemplates";
import { TemplateCard } from "@/components/creative-studio/TemplateCard";

export default function TemplatesPage() {
  const { templates, isLoading, error, deleteTemplate, duplicateTemplate } = useCreativeTemplates();

  function handleDelete(id: string) {
    if (!window.confirm("Sigur vrei să ștergi acest template?")) return;
    void deleteTemplate(id);
  }

  function handleDuplicate(id: string) {
    const original = templates.find((t) => t.id === id);
    const newName = `${original?.name ?? "Template"} (copy)`;
    void duplicateTemplate(id, newName);
  }

  return (
    <>
      <div className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-xl font-semibold text-slate-900 dark:text-slate-100">Creative Templates</h1>
          <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
            Creează și gestionează template-uri pentru anunțurile dinamice.
          </p>
        </div>
        <Link href="/agency/creative-studio/templates/new" className="wm-btn-primary gap-2">
          <Plus className="h-4 w-4" />
          Create Template
        </Link>
      </div>

      {error ? <p className="mb-4 text-red-600">{error}</p> : null}

      {isLoading ? (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="h-6 w-6 animate-spin text-slate-400" />
        </div>
      ) : templates.length === 0 ? (
        <div className="wm-card flex flex-col items-center justify-center px-6 py-16 text-center">
          <div className="mb-3 rounded-full bg-slate-100 p-4 dark:bg-slate-800">
            <Plus className="h-8 w-8 text-slate-400" />
          </div>
          <h2 className="text-lg font-medium text-slate-700 dark:text-slate-300">Nu ai template-uri</h2>
          <p className="mb-4 mt-1 max-w-sm text-sm text-slate-500 dark:text-slate-400">
            Creează primul template pentru a genera anunțuri dinamice din catalogul de produse.
          </p>
          <Link href="/agency/creative-studio/templates/new" className="wm-btn-primary gap-2">
            <Plus className="h-4 w-4" />
            Create Template
          </Link>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {templates.map((template) => (
            <TemplateCard key={template.id} template={template} onDuplicate={handleDuplicate} onDelete={handleDelete} />
          ))}
        </div>
      )}
    </>
  );
}
