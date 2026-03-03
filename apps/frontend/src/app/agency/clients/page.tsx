"use client";

import Link from "next/link";
import { FormEvent, useEffect, useMemo, useState } from "react";
import { Check, Loader2, Pencil } from "lucide-react";

import { AppShell } from "@/components/AppShell";
import { ProtectedPage } from "@/components/ProtectedPage";
import { apiRequest } from "@/lib/api";

type ClientRecord = {
  id: number;
  display_id?: number;
  name: string;
  owner_email: string;
  google_customer_id?: string | null;
};

type ClientsResponse = { items: ClientRecord[] };

const PAGE_SIZE_OPTIONS = [10, 25, 50, 100, 200, 500] as const;

export default function AgencyClientsPage() {
  const [clients, setClients] = useState<ClientRecord[]>([]);
  const [name, setName] = useState("");
  const [search, setSearch] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const [editingClientId, setEditingClientId] = useState<number | null>(null);
  const [editingName, setEditingName] = useState("");
  const [savingClientId, setSavingClientId] = useState<number | null>(null);
  const [savedClientId, setSavedClientId] = useState<number | null>(null);

  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState<number>(10);
  const [selectedClientIds, setSelectedClientIds] = useState<Set<number>>(new Set());

  function markSaved(clientId: number) {
    setSavedClientId(clientId);
    window.setTimeout(() => {
      setSavedClientId((current) => (current === clientId ? null : current));
    }, 1200);
  }

  async function loadClients() {
    try {
      const payload = await apiRequest<ClientsResponse>("/clients");
      setClients(payload.items);
    } catch (err) {
      setClients([]);
      setError(err instanceof Error ? err.message : "Nu am putut încărca clienții");
    }
  }

  useEffect(() => {
    void loadClients();
  }, []);

  async function onCreateClient(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setBusy(true);
    try {
      await apiRequest<ClientRecord>("/clients", {
        method: "POST",
        body: JSON.stringify({ name }),
      });
      setName("");
      await loadClients();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Nu am putut crea clientul");
    } finally {
      setBusy(false);
    }
  }

  async function saveInlineName(client: ClientRecord) {
    const next = editingName.trim();
    if (next === "" || next === client.name) {
      setEditingName(client.name);
      setEditingClientId(null);
      return;
    }

    setSavingClientId(client.id);
    setError("");
    try {
      await apiRequest(`/clients/display/${client.display_id ?? client.id}`, {
        method: "PATCH",
        body: JSON.stringify({ name: next }),
      });
      setClients((prev) => prev.map((item) => (item.id === client.id ? { ...item, name: next } : item)));
      setEditingClientId(null);
      markSaved(client.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Nu am putut salva numele clientului");
    } finally {
      setSavingClientId((current) => (current === client.id ? null : current));
    }
  }

  const filteredClients = useMemo(() => {
    const query = search.trim().toLowerCase();
    if (!query) return clients;
    return clients.filter((client) => client.name.toLowerCase().includes(query));
  }, [clients, search]);

  const totalPages = Math.max(1, Math.ceil(filteredClients.length / pageSize));

  useEffect(() => {
    setPage(1);
    setSelectedClientIds(new Set());
  }, [search, pageSize]);

  useEffect(() => {
    if (page > totalPages) {
      setPage(totalPages);
    }
  }, [page, totalPages]);

  const pagedClients = useMemo(() => {
    const start = (page - 1) * pageSize;
    return filteredClients.slice(start, start + pageSize);
  }, [filteredClients, page, pageSize]);

  const pagedClientIds = useMemo(() => pagedClients.map((client) => client.id), [pagedClients]);
  const allPageSelected = pagedClientIds.length > 0 && pagedClientIds.every((id) => selectedClientIds.has(id));

  function toggleClient(clientId: number, checked: boolean) {
    setSelectedClientIds((current) => {
      const next = new Set(current);
      if (checked) next.add(clientId);
      else next.delete(clientId);
      return next;
    });
  }

  function toggleAllOnPage(checked: boolean) {
    setSelectedClientIds((current) => {
      const next = new Set(current);
      for (const clientId of pagedClientIds) {
        if (checked) next.add(clientId);
        else next.delete(clientId);
      }
      return next;
    });
  }

  return (
    <ProtectedPage>
      <AppShell title="Agency Clients">
        <main className="p-6">
          <form onSubmit={(event) => void onCreateClient(event)} className="mb-4 flex gap-3">
            <input value={name} onChange={(event) => setName(event.target.value)} placeholder="Nume client" className="wm-input" required />
            <button className="wm-btn-primary" disabled={busy}>{busy ? "Se adaugă..." : "Adaugă"}</button>
          </form>

          {error ? <p className="mb-4 text-red-600">{error}</p> : null}

          <section className="mb-3 flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
            <input
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Caută client după nume..."
              className="wm-input md:max-w-md"
            />
            <div className="flex items-center gap-2 text-sm text-slate-600">
              <span>Rânduri/pagină</span>
              <select
                value={pageSize}
                onChange={(event) => setPageSize(Number(event.target.value))}
                className="rounded-md border border-slate-300 bg-white px-2 py-2"
              >
                {PAGE_SIZE_OPTIONS.map((option) => (
                  <option key={option} value={option}>{option}</option>
                ))}
              </select>
            </div>
          </section>

          <section className="wm-card overflow-hidden">
            <table className="min-w-full text-sm">
              <thead className="bg-slate-100 text-left text-slate-600">
                <tr>
                  <th className="px-4 py-3">
                    <input
                      type="checkbox"
                      checked={allPageSelected}
                      onChange={(event) => toggleAllOnPage(event.target.checked)}
                      aria-label="Selectează toți clienții de pe pagină"
                    />
                  </th>
                  <th className="px-4 py-3">ID</th>
                  <th className="px-4 py-3">Nume</th>
                  <th className="px-4 py-3">Owner</th>
                </tr>
              </thead>
              <tbody>
                {pagedClients.map((client) => {
                  const isEditing = editingClientId === client.id;
                  const isSaving = savingClientId === client.id;
                  return (
                    <tr key={client.id} className="border-t border-slate-100">
                      <td className="px-4 py-3">
                        <input
                          type="checkbox"
                          checked={selectedClientIds.has(client.id)}
                          onChange={(event) => toggleClient(client.id, event.target.checked)}
                          aria-label={`Selectează client ${client.name}`}
                        />
                      </td>
                      <td className="px-4 py-3">{client.display_id ?? client.id}</td>
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-2">
                          {isEditing ? (
                            <input
                              autoFocus
                              value={editingName}
                              onChange={(event) => setEditingName(event.target.value)}
                              onBlur={() => void saveInlineName(client)}
                              onKeyDown={(event) => {
                                if (event.key === "Enter") {
                                  event.preventDefault();
                                  void saveInlineName(client);
                                }
                                if (event.key === "Escape") {
                                  setEditingName(client.name);
                                  setEditingClientId(null);
                                }
                              }}
                              className="rounded border border-slate-300 px-2 py-1"
                            />
                          ) : (
                            <Link href={`/agency/clients/${client.display_id ?? client.id}`} className="text-indigo-700 hover:underline">
                              {client.name}
                            </Link>
                          )}
                          <button
                            type="button"
                            onClick={() => {
                              setEditingClientId(client.id);
                              setEditingName(client.name);
                            }}
                            className="rounded p-1 text-slate-500 hover:bg-slate-100"
                            disabled={isSaving}
                            title="Editează nume client"
                          >
                            {isSaving ? <Loader2 className="h-4 w-4 animate-spin" /> : savedClientId === client.id ? <Check className="h-4 w-4 text-emerald-600" /> : <Pencil className="h-4 w-4" />}
                          </button>
                        </div>
                      </td>
                      <td className="px-4 py-3">{client.owner_email}</td>
                    </tr>
                  );
                })}
                {pagedClients.length === 0 ? (
                  <tr>
                    <td className="px-4 py-4 text-slate-500" colSpan={4}>
                      Nu există clienți pentru filtrul curent.
                    </td>
                  </tr>
                ) : null}
              </tbody>
            </table>
          </section>

          <section className="mt-3 flex items-center justify-between text-sm text-slate-600">
            <p>
              {filteredClients.length === 0
                ? "Afișare 0 din 0"
                : `Afișare ${(page - 1) * pageSize + 1}-${Math.min(page * pageSize, filteredClients.length)} din ${filteredClients.length}`}
            </p>
            <div className="flex items-center gap-2">
              <button
                type="button"
                className="rounded border border-slate-300 px-3 py-1 disabled:opacity-50"
                disabled={page <= 1}
                onClick={() => setPage((current) => Math.max(1, current - 1))}
              >
                Anterior
              </button>
              <span>
                Pagina {page} / {totalPages}
              </span>
              <button
                type="button"
                className="rounded border border-slate-300 px-3 py-1 disabled:opacity-50"
                disabled={page >= totalPages}
                onClick={() => setPage((current) => Math.min(totalPages, current + 1))}
              >
                Următor
              </button>
            </div>
          </section>
        </main>
      </AppShell>
    </ProtectedPage>
  );
}
