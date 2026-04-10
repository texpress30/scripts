"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Plus, Loader2 } from "lucide-react";
import { useFeedManagement } from "@/lib/contexts/FeedManagementContext";
import { useCreativeTemplates, groupTemplatesByFormat } from "@/lib/hooks/useCreativeTemplates";
import { TemplateGroupCard } from "@/components/enriched-catalog/TemplateCard";

const SIZE_PRESETS = [
  { key: "square", label: "Square", suffix: "1080x1080", width: 1080, height: 1080 },
  { key: "landscape", label: "Landscape", suffix: "1200x628", width: 1200, height: 628 },
  { key: "stories", label: "Stories", suffix: "1080x1920", width: 1080, height: 1920 },
] as const;

export default function TemplatesPage() {
  const router = useRouter();
  const { selectedId } = useFeedManagement();
  const { templates, isLoading, create, isCreating, duplicate, remove } = useCreativeTemplates(selectedId);
  const [showNewModal, setShowNewModal] = useState(false);
  const [newName, setNewName] = useState("");
  const [selectedSizes, setSelectedSizes] = useState<Set<number>>(new Set([0, 1, 2]));
  const [createError, setCreateError] = useState<string | null>(null);

  const groups = groupTemplatesByFormat(templates);

  const toggleSize = (idx: number) => {
    setSelectedSizes((prev) => {
      const next = new Set(prev);
      if (next.has(idx)) {
        if (next.size > 1) next.delete(idx);
      } else {
        next.add(idx);
      }
      return next;
    });
  };

  const handleCreate = async () => {
    if (!newName.trim() || selectedSizes.size === 0) return;
    setCreateError(null);

    const sizes = [...selectedSizes].sort();
    const formatGroupId = crypto.randomUUID();
    try {
      let firstId: string | null = null;
      for (const idx of sizes) {
        const preset = SIZE_PRESETS[idx];
        const suffix = sizes.length > 1 ? ` - ${preset.label}` : "";
        const created = await create({
          name: `${newName.trim()}${suffix}`,
          canvas_width: preset.width,
          canvas_height: preset.height,
          format_group_id: sizes.length > 1 ? formatGroupId : undefined,
          format_label: sizes.length > 1 ? preset.label : undefined,
        });
        if (!firstId) firstId = created.id;
      }
      setShowNewModal(false);
      setNewName("");
      setSelectedSizes(new Set([0, 1, 2]));
      if (firstId) {
        router.push(`/agency/enriched-catalog/templates/${firstId}/editor`);
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to create template. Please try again.";
      setCreateError(message);
    }
  };

  const handleEdit = (id: string) => {
    router.push(`/agency/enriched-catalog/templates/${id}/editor`);
  };

  const handleDuplicate = async (id: string, name: string) => {
    try {
      await duplicate({ id, newName: name });
    } catch (err) {
      console.error("Failed to duplicate template:", err);
    }
  };

  const handleDelete = async (id: string) => {
    if (confirm("Are you sure you want to delete this template?")) {
      try {
        await remove(id);
      } catch (err) {
        console.error("Failed to delete template:", err);
      }
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

      {/* Template grid — grouped by format */}
      {isLoading ? (
        <div className="flex h-64 items-center justify-center">
          <Loader2 className="h-6 w-6 animate-spin text-slate-400" />
        </div>
      ) : groups.length === 0 ? (
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
          {groups.map((g) => (
            <TemplateGroupCard
              key={g.groupId}
              groupName={g.groupName}
              templates={g.templates}
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

            <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">
              Formats
              <span className="ml-1 text-xs font-normal text-slate-400">(select one or more)</span>
            </label>
            <div className="mb-4 flex flex-col gap-2">
              {SIZE_PRESETS.map((preset, idx) => (
                <label
                  key={idx}
                  className={`flex cursor-pointer items-center gap-3 rounded-md border px-3 py-2 text-sm transition ${
                    selectedSizes.has(idx)
                      ? "border-indigo-500 bg-indigo-50 dark:border-indigo-400 dark:bg-indigo-900/20"
                      : "border-slate-200 hover:border-slate-300 dark:border-slate-600 dark:hover:border-slate-500"
                  }`}
                >
                  <input
                    type="checkbox"
                    checked={selectedSizes.has(idx)}
                    onChange={() => toggleSize(idx)}
                    className="accent-indigo-600"
                  />
                  <span className="flex-1 text-slate-700 dark:text-slate-300">{preset.label}</span>
                  <span className="text-xs text-slate-400">{preset.suffix}</span>
                </label>
              ))}
            </div>

            {selectedSizes.size > 1 && (
              <p className="mb-4 rounded-md bg-indigo-50 px-3 py-2 text-xs text-indigo-700 dark:bg-indigo-900/20 dark:text-indigo-400">
                {selectedSizes.size} formats will be created as a linked group. Edit one design, switch between formats in the editor.
              </p>
            )}

            {createError && (
              <div className="mb-4 rounded-md bg-red-50 px-3 py-2 text-sm text-red-700 dark:bg-red-900/20 dark:text-red-400">
                {createError}
              </div>
            )}

            <div className="flex justify-end gap-3">
              <button
                onClick={() => { setShowNewModal(false); setNewName(""); setCreateError(null); }}
                className="rounded-md px-4 py-2 text-sm text-slate-600 hover:bg-slate-100 dark:text-slate-400 dark:hover:bg-slate-700"
              >
                Cancel
              </button>
              <button
                onClick={handleCreate}
                disabled={!newName.trim() || selectedSizes.size === 0 || isCreating}
                className="wm-btn-primary inline-flex items-center gap-2 rounded-md px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
              >
                {isCreating && <Loader2 className="h-4 w-4 animate-spin" />}
                {selectedSizes.size > 1
                  ? `Create ${selectedSizes.size} Formats`
                  : "Create & Open Editor"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
