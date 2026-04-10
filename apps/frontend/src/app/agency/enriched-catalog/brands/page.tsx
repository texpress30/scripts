"use client";

import { useState } from "react";
import { Plus, Loader2, Trash2, Pencil, Star, X } from "lucide-react";
import { useFeedManagement } from "@/lib/contexts/FeedManagementContext";
import { useBrandPresets, type BrandPreset, type CreateBrandPresetPayload } from "@/lib/hooks/useBrandPresets";

const DEFAULT_COLORS = ["#000000", "#FFFFFF", "#6366f1", "#ef4444", "#22c55e", "#f59e0b"];
const DEFAULT_FONTS = ["Arial", "Helvetica", "Georgia", "Verdana", "Times New Roman"];

export default function BrandsPage() {
  const { selectedId } = useFeedManagement();
  const { presets, isLoading, create, isCreating, update, remove } = useBrandPresets(selectedId);
  const [showEditor, setShowEditor] = useState(false);
  const [editingPreset, setEditingPreset] = useState<BrandPreset | null>(null);

  // Form state
  const [name, setName] = useState("");
  const [colors, setColors] = useState<string[]>(["#000000", "#FFFFFF", "#6366f1"]);
  const [fonts, setFonts] = useState<string[]>(["Arial"]);
  const [logoUrl, setLogoUrl] = useState("");
  const [isDefault, setIsDefault] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const resetForm = () => {
    setName("");
    setColors(["#000000", "#FFFFFF", "#6366f1"]);
    setFonts(["Arial"]);
    setLogoUrl("");
    setIsDefault(false);
    setEditingPreset(null);
    setError(null);
  };

  const openCreate = () => {
    resetForm();
    setShowEditor(true);
  };

  const openEdit = (preset: BrandPreset) => {
    setEditingPreset(preset);
    setName(preset.name);
    setColors([...preset.colors]);
    setFonts([...preset.fonts]);
    setLogoUrl(preset.logo_url || "");
    setIsDefault(preset.is_default);
    setShowEditor(true);
  };

  const handleSave = async () => {
    if (!name.trim()) return;
    setError(null);
    try {
      if (editingPreset) {
        await update({
          id: editingPreset.id,
          payload: { name: name.trim(), colors, fonts, logo_url: logoUrl || undefined, is_default: isDefault },
        });
      } else {
        await create({ name: name.trim(), colors, fonts, logo_url: logoUrl || undefined, is_default: isDefault });
      }
      setShowEditor(false);
      resetForm();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save brand preset.");
    }
  };

  const handleDelete = async (id: string) => {
    if (confirm("Delete this brand preset?")) {
      await remove(id);
    }
  };

  const addColor = () => setColors([...colors, "#cccccc"]);
  const removeColor = (idx: number) => setColors(colors.filter((_, i) => i !== idx));
  const updateColor = (idx: number, value: string) => {
    const next = [...colors];
    next[idx] = value;
    setColors(next);
  };

  const addFont = () => setFonts([...fonts, ""]);
  const removeFont = (idx: number) => setFonts(fonts.filter((_, i) => i !== idx));
  const updateFont = (idx: number, value: string) => {
    const next = [...fonts];
    next[idx] = value;
    setFonts(next);
  };

  if (!selectedId) {
    return (
      <div className="flex h-64 items-center justify-center text-sm text-slate-500 dark:text-slate-400">
        Select a client to manage brand presets.
      </div>
    );
  }

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-slate-900 dark:text-slate-100">Brand Presets</h2>
          <p className="text-sm text-slate-500 dark:text-slate-400">
            Save your brand colors, fonts, and logo for quick application to templates.
          </p>
        </div>
        <button
          onClick={openCreate}
          className="wm-btn-primary inline-flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-medium text-white"
        >
          <Plus className="h-4 w-4" /> New Brand Preset
        </button>
      </div>

      {isLoading ? (
        <div className="flex h-64 items-center justify-center">
          <Loader2 className="h-6 w-6 animate-spin text-slate-400" />
        </div>
      ) : presets.length === 0 && !showEditor ? (
        <div className="flex h-64 flex-col items-center justify-center gap-3 rounded-lg border-2 border-dashed border-slate-200 dark:border-slate-700">
          <p className="text-sm text-slate-500 dark:text-slate-400">No brand presets yet.</p>
          <button
            onClick={openCreate}
            className="wm-btn-primary inline-flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-medium text-white"
          >
            <Plus className="h-4 w-4" /> Create your first brand
          </button>
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {presets.map((preset) => (
            <div
              key={preset.id}
              className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-700 dark:bg-slate-800"
            >
              <div className="mb-3 flex items-start justify-between">
                <div className="flex items-center gap-2">
                  <h3 className="text-sm font-medium text-slate-900 dark:text-slate-100">{preset.name}</h3>
                  {preset.is_default && (
                    <Star className="h-3.5 w-3.5 fill-amber-400 text-amber-400" />
                  )}
                </div>
                <div className="flex gap-1">
                  <button onClick={() => openEdit(preset)} className="rounded p-1 text-slate-400 hover:text-slate-600">
                    <Pencil className="h-3.5 w-3.5" />
                  </button>
                  <button onClick={() => handleDelete(preset.id)} className="rounded p-1 text-slate-400 hover:text-red-500">
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                </div>
              </div>

              {/* Color swatches */}
              <div className="mb-3 flex flex-wrap gap-1.5">
                {preset.colors.map((color, idx) => (
                  <div
                    key={idx}
                    className="h-7 w-7 rounded-md border border-slate-200 dark:border-slate-600"
                    style={{ backgroundColor: color }}
                    title={color}
                  />
                ))}
              </div>

              {/* Fonts */}
              {preset.fonts.length > 0 && (
                <div className="flex flex-wrap gap-1">
                  {preset.fonts.map((font, idx) => (
                    <span key={idx} className="rounded bg-slate-100 px-1.5 py-0.5 text-xs text-slate-600 dark:bg-slate-700 dark:text-slate-400">
                      {font}
                    </span>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Editor modal */}
      {showEditor && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="w-full max-w-lg rounded-lg bg-white p-6 shadow-xl dark:bg-slate-800">
            <h3 className="mb-4 text-lg font-semibold text-slate-900 dark:text-slate-100">
              {editingPreset ? "Edit Brand Preset" : "New Brand Preset"}
            </h3>

            <div className="space-y-4">
              {/* Name */}
              <div>
                <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">Name</label>
                <input
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="e.g. My Brand"
                  className="mcc-input w-full rounded-md border px-3 py-2 text-sm"
                  autoFocus
                />
              </div>

              {/* Colors */}
              <div>
                <div className="mb-1 flex items-center justify-between">
                  <label className="text-sm font-medium text-slate-700 dark:text-slate-300">Brand Colors</label>
                  <button onClick={addColor} className="flex items-center gap-1 text-xs text-indigo-600 hover:text-indigo-700">
                    <Plus className="h-3 w-3" /> Add
                  </button>
                </div>
                <div className="flex flex-wrap gap-2">
                  {colors.map((color, idx) => (
                    <div key={idx} className="flex items-center gap-1">
                      <input
                        type="color"
                        value={color}
                        onChange={(e) => updateColor(idx, e.target.value)}
                        className="h-8 w-10 cursor-pointer rounded border"
                      />
                      <button onClick={() => removeColor(idx)} className="rounded p-0.5 text-slate-400 hover:text-red-500">
                        <X className="h-3 w-3" />
                      </button>
                    </div>
                  ))}
                </div>
              </div>

              {/* Fonts */}
              <div>
                <div className="mb-1 flex items-center justify-between">
                  <label className="text-sm font-medium text-slate-700 dark:text-slate-300">Fonts</label>
                  <button onClick={addFont} className="flex items-center gap-1 text-xs text-indigo-600 hover:text-indigo-700">
                    <Plus className="h-3 w-3" /> Add
                  </button>
                </div>
                <div className="space-y-2">
                  {fonts.map((font, idx) => (
                    <div key={idx} className="flex items-center gap-2">
                      <select
                        value={font}
                        onChange={(e) => updateFont(idx, e.target.value)}
                        className="mcc-input flex-1 rounded border px-2 py-1.5 text-sm"
                      >
                        <option value="">Select font...</option>
                        {DEFAULT_FONTS.map((f) => (
                          <option key={f} value={f}>{f}</option>
                        ))}
                      </select>
                      <button onClick={() => removeFont(idx)} className="rounded p-0.5 text-slate-400 hover:text-red-500">
                        <X className="h-3 w-3" />
                      </button>
                    </div>
                  ))}
                </div>
              </div>

              {/* Logo URL */}
              <div>
                <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">Logo URL</label>
                <input
                  type="url"
                  value={logoUrl}
                  onChange={(e) => setLogoUrl(e.target.value)}
                  placeholder="https://example.com/logo.png"
                  className="mcc-input w-full rounded-md border px-3 py-2 text-sm"
                />
              </div>

              {/* Default */}
              <label className="flex items-center gap-2 text-sm text-slate-700 dark:text-slate-300">
                <input
                  type="checkbox"
                  checked={isDefault}
                  onChange={(e) => setIsDefault(e.target.checked)}
                  className="accent-indigo-600"
                />
                Set as default brand
              </label>

              {error && (
                <div className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700 dark:bg-red-900/20 dark:text-red-400">
                  {error}
                </div>
              )}
            </div>

            <div className="mt-6 flex justify-end gap-3">
              <button
                onClick={() => { setShowEditor(false); resetForm(); }}
                className="rounded-md px-4 py-2 text-sm text-slate-600 hover:bg-slate-100 dark:text-slate-400 dark:hover:bg-slate-700"
              >
                Cancel
              </button>
              <button
                onClick={handleSave}
                disabled={!name.trim() || isCreating}
                className="wm-btn-primary inline-flex items-center gap-2 rounded-md px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
              >
                {isCreating && <Loader2 className="h-4 w-4 animate-spin" />}
                {editingPreset ? "Update" : "Create"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
