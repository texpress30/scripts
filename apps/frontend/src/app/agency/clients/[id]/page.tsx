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

type SaveField = "name" | "client_type" | "account_manager";

export default function AgencyClientDetailsPage() {
  const params = useParams<{ id: string }>();
  const displayId = Number(params.id);
  const [data, setData] = useState<ClientDetails | null>(null);
  const [error, setError] = useState("");

  const [editingName, setEditingName] = useState(false);
  const [editingClientType, setEditingClientType] = useState(false);
  const [editingManager, setEditingManager] = useState(false);

  const [nameInput, setNameInput] = useState("");
  const [clientType, setClientType] = useState("lead");
  const [accountManager, setAccountManager] = useState("");

  const [savingField, setSavingField] = useState<SaveField | null>(null);
  const [savedField, setSavedField] = useState<SaveField | null>(null);

  function markSaved(field: SaveField) {
    setSavedField(field);
    window.setTimeout(() => setSavedField((current) => (current === field ? null : current)), 1200);
  }

  async function load() {
    setError("");
    try {
      const payload = await apiRequest<ClientDetails>(`/clients/display/${displayId}`);
      setData(payload);
      setNameInput(payload.client.name);
      setClientType(payload.client.client_type ?? "lead");
      setAccountManager(payload.client.account_manager ?? "");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Nu am putut încărca detaliile clientului.");
    }
  }

  useEffect(() => {
    if (displayId > 0) {
      void load();
    }
  }, [displayId]);

  async function patchProfile(payload: { name?: string; client_type?: string; account_manager?: string }, field: SaveField) {
    setSavingField(field);
    setError("");
    try {
      const response = await apiRequest<ClientDetails>(`/clients/display/${displayId}`, {
        method: "PATCH",
        body: JSON.stringify(payload),
      });
      setData(response);
      setNameInput(response.client.name);
      setClientType(response.client.client_type ?? "lead");
      setAccountManager(response.client.account_manager ?? "");
      markSaved(field);
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
    await patchProfile({ name: trimmed }, "name");
    setEditingName(false);
  }

  async function saveManagerIfChanged() {
    if (!data) return;
    const trimmed = accountManager.trim();
    const current = data.client.account_manager ?? "";
    if (trimmed === current) {
      setEditingManager(false);
      return;
    }
    await patchProfile({ account_manager: trimmed }, "account_manager");
    setEditingManager(false);
  }

  async function selectClientType(value: string) {
    setClientType(value);
    await patchProfile({ client_type: value }, "client_type");
    setEditingClientType(false);
  }

  const title = useMemo(() => (data ? `Client: ${data.client.name}` : `Client #${displayId}`), [data, displayId]);

  return (
    <ProtectedPage>
      <AppShell title={title}>
        <main className="space-y-4 p-6">
          {error ? <p className="text-sm text-red-600">{error}</p> : null}
          {data ? (
            <>
              <section className="wm-card p-4">
                <div className="flex items-center gap-3">
                  <Link href="/agency/clients" className="inline-flex h-8 w-8 items-center justify-center rounded-md border border-slate-200 text-slate-600 hover:bg-slate-50" title="Înapoi la clienți">
                    <ArrowLeft className="h-4 w-4" />
                  </Link>
                  <div>
                    <p className="text-sm text-slate-500">Client #{data.client.display_id ?? displayId}</p>
                    <div className="flex items-center gap-2">
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
                  </div>
                </div>

                <div className="mt-4">
                  <p className="text-xs font-medium text-slate-500">Responsabil cont</p>
                  <div className="mt-1 flex items-center gap-2">
                    {editingManager ? (
                      <input
                        autoFocus
                        value={accountManager}
                        onChange={(e) => setAccountManager(e.target.value)}
                        onBlur={() => void saveManagerIfChanged()}
                        onKeyDown={(e) => {
                          if (e.key === "Enter") {
                            e.preventDefault();
                            void saveManagerIfChanged();
                          }
                          if (e.key === "Escape") {
                            setAccountManager(data.client.account_manager ?? "");
                            setEditingManager(false);
                          }
                        }}
                        className="w-full max-w-md rounded-md border border-slate-300 px-2 py-1 text-sm"
                        placeholder="Nume membru echipă"
                      />
                    ) : (
                      <p className="text-sm text-slate-700">{accountManager || "—"}</p>
                    )}
                    <button
                      type="button"
                      onClick={() => setEditingManager(true)}
                      className="rounded-md p-1 text-slate-500 hover:bg-slate-100"
                      title="Editează responsabil cont"
                      disabled={savingField === "account_manager"}
                    >
                      {savedField === "account_manager" ? <Check className="h-4 w-4 text-emerald-600" /> : <Pencil className="h-4 w-4" />}
                    </button>
                  </div>
                </div>
              </section>

              <section className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
                {data.platforms.map((platform) => (
                  <article key={platform.platform} className="wm-card p-4">
                    <h3 className="text-base font-semibold text-slate-900">{prettyPlatform(platform.platform)}</h3>
                    <p className="mt-1 text-xs text-slate-500">Activ: {platform.enabled ? "Da" : "Nu"}</p>
                    <p className="text-xs text-slate-500">Conturi atașate: {platform.count}</p>
                    <ul className="mt-2 space-y-2">
                      {platform.accounts.map((account) => (
                        <li key={account.id} className="rounded-md border border-slate-100 p-2 text-sm text-slate-700">
                          <div>
                            {account.name} <span className="text-xs text-slate-500">({account.id})</span>
                          </div>
                          <div className="mt-2 flex items-center gap-2 text-xs">
                            <span className="text-slate-500">Tip client:</span>
                            {editingClientType ? (
                              <select
                                value={clientType}
                                onChange={(e) => void selectClientType(e.target.value)}
                                className="rounded border border-slate-300 px-2 py-1 text-xs"
                                disabled={savingField === "client_type"}
                              >
                                <option value="lead">lead</option>
                                <option value="e-commerce">e-commerce</option>
                                <option value="programmatic">programmatic</option>
                              </select>
                            ) : (
                              <span className="font-medium text-slate-700">{clientType}</span>
                            )}
                            <button
                              type="button"
                              onClick={() => setEditingClientType(true)}
                              className="rounded p-1 text-slate-500 hover:bg-slate-100"
                              title="Editează tip client"
                              disabled={savingField === "client_type"}
                            >
                              {savedField === "client_type" ? <Check className="h-3.5 w-3.5 text-emerald-600" /> : <Pencil className="h-3.5 w-3.5" />}
                            </button>
                          </div>
                        </li>
                      ))}
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
