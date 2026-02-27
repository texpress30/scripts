"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import { ArrowLeft, Check, Pencil } from "lucide-react";

import { AppShell } from "@/components/AppShell";
import { ProtectedPage } from "@/components/ProtectedPage";
import { apiRequest } from "@/lib/api";

type Account = { id: string; name: string };
type PlatformInfo = { platform: string; enabled: boolean; count: number; accounts: Account[] };
type ClientDetails = {
  client: {
    id: number;
    display_id?: number;
    name: string;
    owner_email: string;
    client_type?: string;
    account_manager?: string;
  };
  platforms: PlatformInfo[];
};

type SaveField = "name" | "row";
type RowDraft = { clientType: string; accountManager: string };

function prettyPlatform(platform: string): string {
  const map: Record<string, string> = {
    google_ads: "Google Ads",
    meta_ads: "Meta Ads",
    tiktok_ads: "TikTok Ads",
    pinterest_ads: "Pinterest Ads",
    snapchat_ads: "Snapchat Ads",
  };
  return map[platform] ?? platform;
}

function rowKey(platform: string, accountId: string): string {
  return `${platform}:${accountId}`;
}

export default function AgencyClientDetailsPage() {
  const params = useParams<{ id: string }>();
  const displayId = Number(params.id);
  const [data, setData] = useState<ClientDetails | null>(null);
  const [error, setError] = useState("");

  const [editingName, setEditingName] = useState(false);
  const [editingRowId, setEditingRowId] = useState<string | null>(null);

  const [nameInput, setNameInput] = useState("");
  const [rowDrafts, setRowDrafts] = useState<Record<string, RowDraft>>({});

  const [savingField, setSavingField] = useState<SaveField | null>(null);
  const [savedField, setSavedField] = useState<string | null>(null);

  function markSaved(field: string) {
    setSavedField(field);
    window.setTimeout(() => setSavedField((current) => (current === field ? null : current)), 1200);
  }

  function setAllRowDraftsFromPayload(payload: ClientDetails) {
    const next: Record<string, RowDraft> = {};
    for (const platform of payload.platforms) {
      for (const account of platform.accounts) {
        next[rowKey(platform.platform, account.id)] = {
          clientType: payload.client.client_type ?? "lead",
          accountManager: payload.client.account_manager ?? "",
        };
      }
    }
    setRowDrafts(next);
  }

  async function load() {
    setError("");
    try {
      const payload = await apiRequest<ClientDetails>(`/clients/display/${displayId}`);
      setData(payload);
      setNameInput(payload.client.name);
      setAllRowDraftsFromPayload(payload);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Nu am putut încărca detaliile clientului.");
    }
  }

  useEffect(() => {
    if (displayId > 0) {
      void load();
    }
  }, [displayId]);

  async function patchProfile(payload: { name?: string; client_type?: string; account_manager?: string }, field: SaveField, successKey: string) {
    setSavingField(field);
    setError("");
    try {
      const response = await apiRequest<ClientDetails>(`/clients/display/${displayId}`, {
        method: "PATCH",
        body: JSON.stringify(payload),
      });
      setData(response);
      setNameInput(response.client.name);
      setAllRowDraftsFromPayload(response);
      markSaved(successKey);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Nu am putut salva modificarea.");
    } finally {
      setSavingField((current) => (current === field ? null : current));
    }
  }

  async function saveNameIfChanged() {
    if (!data) return;
    const trimmed = nameInput.trim();
    const current = data.client.name;
    if (trimmed === "" || trimmed === current) {
      setNameInput(current);
      setEditingName(false);
      return;
    }
    await patchProfile({ name: trimmed }, "name", "name");
    setEditingName(false);
  }

  async function saveRowIfChanged(key: string, nextDraft?: RowDraft) {
    if (!data) return;
    const draft = nextDraft ?? rowDrafts[key];
    if (!draft) {
      setEditingRowId(null);
      return;
    }

    const normalizedManager = draft.accountManager.trim();
    const currentType = data.client.client_type ?? "lead";
    const currentManager = data.client.account_manager ?? "";
    if (draft.clientType === currentType && normalizedManager === currentManager) {
      setEditingRowId(null);
      return;
    }

    await patchProfile({ client_type: draft.clientType, account_manager: normalizedManager }, "row", key);
    setEditingRowId(null);
  }

  const title = useMemo(() => (data ? `Client: ${data.client.name}` : `Client #${displayId}`), [data, displayId]);

  return (
    <ProtectedPage>
      <AppShell
        title={title}
        headerPrefix={
          <Link
            href="/agency/clients"
            className="inline-flex h-8 w-8 items-center justify-center rounded-md border border-slate-200 text-slate-600 hover:bg-slate-50"
            title="Înapoi la clienți"
          >
            <ArrowLeft className="h-4 w-4" />
          </Link>
        }
      >
        <main className="space-y-4 p-6">
          {error ? <p className="text-sm text-red-600">{error}</p> : null}
          {data ? (
            <>
              <section className="wm-card p-4">
                <p className="text-sm text-slate-500">Client #{data.client.display_id ?? displayId}</p>
                <div className="mt-1 flex items-center gap-2">
                  {editingName ? (
                    <input
                      autoFocus
                      value={nameInput}
                      onChange={(e) => setNameInput(e.target.value)}
                      onBlur={() => void saveNameIfChanged()}
                      onKeyDown={(e) => {
                        if (e.key === "Enter") {
                          e.preventDefault();
                          void saveNameIfChanged();
                        }
                        if (e.key === "Escape") {
                          setNameInput(data.client.name);
                          setEditingName(false);
                        }
                      }}
                      className="rounded-md border border-slate-300 px-2 py-1 text-xl font-semibold text-slate-900"
                    />
                  ) : (
                    <h2 className="text-xl font-semibold text-slate-900">{data.client.name}</h2>
                  )}
                  <button
                    type="button"
                    onClick={() => setEditingName(true)}
                    className="rounded-md p-1 text-slate-500 hover:bg-slate-100"
                    title="Editează nume client"
                    disabled={savingField === "name"}
                  >
                    {savedField === "name" ? <Check className="h-4 w-4 text-emerald-600" /> : <Pencil className="h-4 w-4" />}
                  </button>
                </div>
                <p className="text-sm text-slate-600">Owner: {data.client.owner_email}</p>
              </section>

              <section className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
                {data.platforms.map((platform) => (
                  <article key={platform.platform} className="wm-card p-4">
                    <h3 className="text-base font-semibold text-slate-900">{prettyPlatform(platform.platform)}</h3>
                    <p className="mt-1 text-xs text-slate-500">Activ: {platform.enabled ? "Da" : "Nu"}</p>
                    <p className="text-xs text-slate-500">Conturi atașate: {platform.count}</p>
                    <ul className="mt-2 space-y-2">
                      {platform.accounts.map((account) => {
                        const key = rowKey(platform.platform, account.id);
                        const isEditingRow = editingRowId === key;
                        const draft = rowDrafts[key] ?? {
                          clientType: data.client.client_type ?? "lead",
                          accountManager: data.client.account_manager ?? "",
                        };
                        return (
                          <li key={key} className="rounded-md border border-slate-100 p-2 text-sm text-slate-700">
                            <div className="flex items-start justify-between gap-2">
                              <div>
                                {account.name} <span className="text-xs text-slate-500">({account.id})</span>
                              </div>
                              <button
                                type="button"
                                onClick={() => setEditingRowId((current) => (current === key ? null : key))}
                                className="rounded p-1 text-slate-500 hover:bg-slate-100"
                                title="Editează tip client și responsabil"
                                disabled={savingField === "row"}
                              >
                                {savedField === key ? <Check className="h-3.5 w-3.5 text-emerald-600" /> : <Pencil className="h-3.5 w-3.5" />}
                              </button>
                            </div>

                            <div className="mt-2 grid grid-cols-1 gap-2 text-xs md:grid-cols-2">
                              <div className="flex items-center gap-2">
                                <span className="text-slate-500">Tip client:</span>
                                {isEditingRow ? (
                                  <select
                                    value={draft.clientType}
                                    onChange={(e) => {
                                      const value = e.target.value;
                                      const nextDraft = { ...draft, clientType: value };
                                      setRowDrafts((prev) => ({ ...prev, [key]: nextDraft }));
                                      void saveRowIfChanged(key, nextDraft);
                                    }}
                                    className="rounded border border-slate-300 px-2 py-1 text-xs"
                                    disabled={savingField === "row"}
                                  >
                                    <option value="lead">lead</option>
                                    <option value="e-commerce">e-commerce</option>
                                    <option value="programmatic">programmatic</option>
                                  </select>
                                ) : (
                                  <span className="font-medium text-slate-700">{draft.clientType}</span>
                                )}
                              </div>

                              <div className="flex items-center gap-2">
                                <span className="text-slate-500">Responsabil:</span>
                                {isEditingRow ? (
                                  <input
                                    value={draft.accountManager}
                                    onChange={(e) => setRowDrafts((prev) => ({ ...prev, [key]: { ...draft, accountManager: e.target.value } }))}
                                    onBlur={() => void saveRowIfChanged(key)}
                                    onKeyDown={(e) => {
                                      if (e.key === "Enter") {
                                        e.preventDefault();
                                        void saveRowIfChanged(key);
                                      }
                                      if (e.key === "Escape") {
                                        setEditingRowId(null);
                                      }
                                    }}
                                    className="w-full rounded border border-slate-300 px-2 py-1 text-xs"
                                    placeholder="Nume responsabil"
                                    autoFocus
                                  />
                                ) : (
                                  <span className="font-medium text-slate-700">{draft.accountManager || "—"}</span>
                                )}
                              </div>
                            </div>
                          </li>
                        );
                      })}
                      {platform.accounts.length === 0 ? <li className="text-sm text-slate-400">Fără conturi atașate.</li> : null}
                    </ul>
                  </article>
                ))}
              </section>
            </>
          ) : null}
        </main>
      </AppShell>
    </ProtectedPage>
  );
}
