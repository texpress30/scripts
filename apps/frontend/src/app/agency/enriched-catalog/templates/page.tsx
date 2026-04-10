"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Plus, Loader2 } from "lucide-react";
import { useFeedManagement } from "@/lib/contexts/FeedManagementContext";
import { useCreativeTemplates } from "@/lib/hooks/useCreativeTemplates";
import { TemplateCard } from "@/components/enriched-catalog/TemplateCard";

const SIZE_PRESETS = [
  { label: "Square (1080x1080)", width: 1080, height: 1080 },
  { label: "Landscape (1200x628)", width: 1200, height: 628 },
  { label: "Stories (1080x1920)", width: 1080, height: 1920 },
] as const;

export default function TemplatesPage() {
  const router = useRouter();
  const { selectedId } = useFeedManagement();
  const { templates, isLoading, create, isCreating, duplicate, remove } = useCreativeTemplates(selectedId);
  const [showNewModal, setShowNewModal] = useState(false);
  const [newName, setNewName] = useState("");
  const [selectedPreset, setSelectedPreset] = useState(0);

  const handleCreate = async () => {
    if (!newName.trim()) return;
    const preset = SIZE_PRESETS[selectedPreset];
    const created = await create({
      name: newName.trim(),
      canvas_width: preset.width,
      canvas_height: preset.height,
    });
    setShowNewModal(false);
    setNewName("");
    router.push(`/agency/enriched-catalog/templates/${created.id}/editor`);
  };

  const handleEdit = (id: string) => {
    router.push(`/agency/enriched-catalog/templates/${id}/editor`);
  };

  const handleDuplicate = async (id: string, name: string) => {
    await duplicate({ id, newName: name });
  };

  const handleDelete = async (id: string) => {
    if (confirm("Are you sure you want to delete this template?")) {
      await remove(id);
    }
  };

  if (!selectedId) {
    return (
      <div className="flex h-64 items-center justify-center text-sm text-slate-500 dark:text-slate-400">
        Select a client to manage creative templates.
      </div>
    );
  }

  return (
    <div>
      {/* Header */}
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-slate-900 dark:text-slate-100">Creative Templates</h2>
          <p className="text-sm text-slate-500 dark:text-slate-400">
            Design templates with dynamic product fields for automated creative generation.
          </p>
        </div>
        <button
          onClick={() => setShowNewModal(true)}
          className="wm-btn-primary inline-flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-medium text-white"
        >
          <Plus className="h-4 w-4" /> New Template
        </button>
      </div>

      {/* Template grid */}
      {isLoading ? (
        <div className="flex h-64 items-center justify-center">
          <Loader2 className="h-6 w-6 animate-spin text-slate-400" />
        </div>
      ) : templates.length === 0 ? (
        <div className="flex h-64 flex-col items-center justify-center gap-3 rounded-lg border-2 border-dashed border-slate-200 dark:border-slate-700">
          <p className="text-sm text-slate-500 dark:text-slate-400">No templates yet.</p>
          <button
            onClick={() => setShowNewModal(true)}
            className="wm-btn-primary inline-flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-medium text-white"
          >
            <Plus className="h-4 w-4" /> Create your first template
          </button>
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {templates.map((t) => (
            <TemplateCard
              key={t.id}
              template={t}
              onEdit={handleEdit}
              onDuplicate={handleDuplicate}
              onDelete={handleDelete}
            />
          ))}
        </div>
      )}

      {/* New template modal */}
      {showNewModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="w-full max-w-md rounded-lg bg-white p-6 shadow-xl dark:bg-slate-800">
            <h3 className="mb-4 text-lg font-semibold text-slate-900 dark:text-slate-100">New Template</h3>

            <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">Name</label>
            <input
              type="text"
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              placeholder="e.g. Product Card - Blue"
              className="mcc-input mb-4 w-full rounded-md border px-3 py-2 text-sm"
              autoFocus
              onKeyDown={(e) => e.key === "Enter" && handleCreate()}
            />

            <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">Canvas Size</label>
            <div className="mb-6 flex flex-col gap-2">
              {SIZE_PRESETS.map((preset, idx) => (
                <label
                  key={idx}
                  className={`flex cursor-pointer items-center gap-3 rounded-md border px-3 py-2 text-sm transition ${
                    selectedPreset === idx
                      ? "border-indigo-500 bg-indigo-50 dark:border-indigo-400 dark:bg-indigo-900/20"
                      : "border-slate-200 hover:border-slate-300 dark:border-slate-600 dark:hover:border-slate-500"
                  }`}
                >
                  <input
                    type="radio"
                    name="preset"
                    checked={selectedPreset === idx}
                    onChange={() => setSelectedPreset(idx)}
                    className="accent-indigo-600"
                  />
                  <span className="text-slate-700 dark:text-slate-300">{preset.label}</span>
                </label>
              ))}
            </div>

            <div className="flex justify-end gap-3">
              <button
                onClick={() => { setShowNewModal(false); setNewName(""); }}
                className="rounded-md px-4 py-2 text-sm text-slate-600 hover:bg-slate-100 dark:text-slate-400 dark:hover:bg-slate-700"
              >
                Cancel
              </button>
              <button
                onClick={handleCreate}
                disabled={!newName.trim() || isCreating}
                className="wm-btn-primary inline-flex items-center gap-2 rounded-md px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
              >
                {isCreating && <Loader2 className="h-4 w-4 animate-spin" />}
                Create & Open Editor
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
