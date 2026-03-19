"use client";

import React, { useEffect, useMemo, useState } from "react";

export type PermissionEditorItem = {
  key: string;
  label: string;
  order: number;
  groupKey: string;
  groupLabel: string;
  parentKey: string | null;
  isContainer: boolean;
  disabledReason?: string | null;
};

type PermissionEditorGroup = {
  key: string;
  label: string;
  items: PermissionEditorItem[];
};

type PermissionsEditorProps = {
  scope: "agency" | "subaccount";
  items: PermissionEditorItem[];
  selectedKeys: string[];
  onToggle: (moduleKey: string) => void;
  loading?: boolean;
  loadError?: string | null;
  fieldError?: string | null;
  readOnly?: boolean;
  summaryHint?: string | null;
  getItemDisabled?: (item: PermissionEditorItem) => boolean;
  getItemAriaLabel?: (item: PermissionEditorItem) => string | undefined;
};

function normalizeKey(value: string): string {
  return String(value || "").trim().toLowerCase();
}

export function PermissionsEditor({
  scope,
  items,
  selectedKeys,
  onToggle,
  loading = false,
  loadError,
  fieldError,
  readOnly = false,
  summaryHint,
  getItemDisabled,
  getItemAriaLabel,
}: PermissionsEditorProps) {
  const [search, setSearch] = useState("");
  const [activeGroup, setActiveGroup] = useState<string>("");

  const selectedSet = useMemo(() => new Set(selectedKeys.map(normalizeKey)), [selectedKeys]);

  const groups = useMemo<PermissionEditorGroup[]>(() => {
    const grouped = new Map<string, PermissionEditorGroup>();
    for (const item of items) {
      const groupKey = normalizeKey(item.groupKey) || "main_nav";
      if (!grouped.has(groupKey)) {
        grouped.set(groupKey, {
          key: groupKey,
          label: item.groupLabel || "Main Navigation",
          items: [],
        });
      }
      grouped.get(groupKey)?.items.push(item);
    }
    return Array.from(grouped.values())
      .map((group) => ({ ...group, items: [...group.items].sort((a, b) => a.order - b.order || a.label.localeCompare(b.label)) }))
      .sort((a, b) => a.items[0].order - b.items[0].order || a.label.localeCompare(b.label));
  }, [items]);

  useEffect(() => {
    if (groups.length === 0) {
      setActiveGroup("");
      return;
    }
    if (activeGroup && groups.some((group) => group.key === activeGroup)) return;
    setActiveGroup(groups[0].key);
  }, [groups, activeGroup]);

  const activeGroupData = useMemo(() => groups.find((group) => group.key === activeGroup) ?? groups[0] ?? null, [groups, activeGroup]);

  const query = search.trim().toLowerCase();
  const filteredActiveItems = useMemo(() => {
    if (!activeGroupData) return [] as PermissionEditorItem[];
    if (!query) return activeGroupData.items;
    return activeGroupData.items.filter((item) => {
      const key = normalizeKey(item.key);
      const label = String(item.label || "").toLowerCase();
      const groupLabel = String(item.groupLabel || "").toLowerCase();
      return key.includes(query) || label.includes(query) || groupLabel.includes(query);
    });
  }, [activeGroupData, query]);

  const activeCount = selectedSet.size;
  const totalCount = items.length;
  const scopeLabel = scope === "agency" ? "agency" : "subaccount";

  function renderNode(item: PermissionEditorItem, children: PermissionEditorItem[]) {
    const checked = selectedSet.has(normalizeKey(item.key));
    const disabledByItem = Boolean(getItemDisabled?.(item));
    const disabled = readOnly || disabledByItem;

    return (
      <div key={item.key} className="space-y-1 rounded-md border border-slate-200 bg-white px-3 py-2">
        <label className="flex items-start justify-between gap-3 text-sm text-slate-700">
          <div>
            <p className="font-medium text-slate-900">{item.label}</p>
            {item.isContainer ? <p className="text-[11px] text-slate-500">Container de navigare</p> : null}
            {item.disabledReason ? <p className="text-xs text-slate-500">{item.disabledReason}</p> : null}
          </div>
          <input
            type="checkbox"
            className="mt-0.5 h-4 w-4 rounded border-slate-300 text-indigo-600"
            aria-label={getItemAriaLabel?.(item)}
            checked={checked}
            disabled={disabled}
            onChange={() => onToggle(item.key)}
          />
        </label>
        {children.length > 0 ? (
          <div className="space-y-1 border-l border-slate-200 pl-3">
            {children.map((child) => {
              const childChecked = selectedSet.has(normalizeKey(child.key));
              const childDisabledByItem = Boolean(getItemDisabled?.(child));
              const childDisabled = readOnly || childDisabledByItem;
              return (
                <label key={child.key} className="flex items-start justify-between gap-3 rounded-md border border-slate-100 bg-slate-50/60 px-2 py-1.5 text-sm text-slate-700">
                  <div>
                    <p>{child.label}</p>
                    {child.disabledReason ? <p className="text-xs text-slate-500">{child.disabledReason}</p> : null}
                  </div>
                  <input
                    type="checkbox"
                    className="mt-0.5 h-4 w-4 rounded border-slate-300 text-indigo-600"
                    aria-label={getItemAriaLabel?.(child)}
                    checked={childChecked}
                    disabled={childDisabled}
                    onChange={() => onToggle(child.key)}
                  />
                </label>
              );
            })}
          </div>
        ) : null}
      </div>
    );
  }

  const groupActiveCounts = useMemo(() => {
    const result = new Map<string, number>();
    for (const group of groups) {
      const count = group.items.filter((item) => selectedSet.has(normalizeKey(item.key))).length;
      result.set(group.key, count);
    }
    return result;
  }, [groups, selectedSet]);

  const renderable = useMemo(() => {
    const groupItems = filteredActiveItems;
    const byParent = new Map<string, PermissionEditorItem[]>();
    const topLevel: PermissionEditorItem[] = [];
    const itemKeys = new Set(groupItems.map((item) => item.key));

    for (const item of groupItems) {
      if (item.parentKey && itemKeys.has(item.parentKey)) {
        const siblings = byParent.get(item.parentKey) ?? [];
        siblings.push(item);
        byParent.set(item.parentKey, siblings);
      } else {
        topLevel.push(item);
      }
    }

    topLevel.sort((a, b) => a.order - b.order || a.label.localeCompare(b.label));
    return topLevel.map((item) => {
      const children = (byParent.get(item.key) ?? []).sort((a, b) => a.order - b.order || a.label.localeCompare(b.label));
      return renderNode(item, children);
    });
  }, [filteredActiveItems, getItemAriaLabel, getItemDisabled, onToggle, readOnly, selectedSet]);

  return (
    <section className="space-y-3 rounded-lg border border-slate-200 bg-slate-50 p-3">
      <div>
        <h3 className="text-sm font-semibold text-slate-900">Roluri și Permisiuni</h3>
        <p className="text-xs text-slate-600">{activeCount} / {totalCount} active · scope: {scopeLabel}</p>
        {summaryHint ? <p className="mt-1 text-xs text-slate-600">{summaryHint}</p> : null}
      </div>
      <label className="block text-xs text-slate-600">
        Caută permisiune
        <input
          className="wm-input mt-1"
          placeholder="Caută după label, key sau grup"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
        />
      </label>
      {loading ? <p className="text-xs text-slate-500">Se încarcă modulele...</p> : null}
      {loadError ? <p className="rounded-md border border-red-200 bg-red-50 px-2 py-1 text-xs text-red-700">{loadError}</p> : null}

      {!loading && groups.length > 0 ? (
        <div className="grid gap-3 md:grid-cols-[220px_minmax(0,1fr)]">
          <aside className="space-y-1 rounded-md border border-slate-200 bg-white p-2">
            {groups.map((group) => {
              const isActive = activeGroupData?.key === group.key;
              const count = groupActiveCounts.get(group.key) ?? 0;
              return (
                <button
                  key={group.key}
                  type="button"
                  onClick={() => setActiveGroup(group.key)}
                  className={[
                    "flex w-full items-center justify-between rounded px-2 py-1.5 text-left text-sm",
                    isActive ? "bg-indigo-50 text-indigo-700" : "text-slate-700 hover:bg-slate-50",
                  ].join(" ")}
                >
                  <span>{group.label}</span>
                  <span className="rounded-full bg-slate-100 px-1.5 py-0.5 text-[11px] text-slate-600">{count}</span>
                </button>
              );
            })}
          </aside>

          <div className="space-y-2 rounded-md border border-slate-200 bg-white p-3">
            <header>
              <p className="text-sm font-semibold text-slate-900">{activeGroupData?.label ?? "Permisiuni"}</p>
              <p className="text-xs text-slate-500">Selectează cheile de navigare active pentru acest utilizator.</p>
            </header>
            {query && renderable.length === 0 ? <p className="text-sm text-slate-500">Nicio permisiune nu corespunde căutării.</p> : null}
            {renderable}
          </div>
        </div>
      ) : null}

      {!loading && items.length === 0 ? <p className="text-sm text-slate-500">Nu există module disponibile.</p> : null}
      {fieldError ? <p className="text-xs text-red-600">{fieldError}</p> : null}
    </section>
  );
}
