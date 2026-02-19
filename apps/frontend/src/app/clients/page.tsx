"use client";

import { FormEvent, useEffect, useState } from "react";
import { Plus, UserPlus, Search } from "lucide-react";
import { AppShell } from "@/components/AppShell";
import { ProtectedPage } from "@/components/ProtectedPage";
import { apiRequest } from "@/lib/api";

type ClientItem = {
  id: number;
  name: string;
  owner_email: string;
};

type ClientsResponse = { items: ClientItem[] };

export default function ClientsPage() {
  const [clients, setClients] = useState<ClientItem[]>([]);
  const [name, setName] = useState("");
  const [error, setError] = useState("");
  const [searchQuery, setSearchQuery] = useState("");

  async function loadClients() {
    setError("");
    try {
      const result = await apiRequest<ClientsResponse>("/clients");
      setClients(result.items);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Nu pot incarca lista de clienti");
    }
  }

  useEffect(() => {
    void loadClients();
  }, []);

  async function onCreate(e: FormEvent) {
    e.preventDefault();
    setError("");
    try {
      await apiRequest<ClientItem>("/clients", {
        method: "POST",
        body: JSON.stringify({ name }),
      });
      setName("");
      await loadClients();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Nu pot crea clientul");
    }
  }

  const filteredClients = clients.filter((c) =>
    c.name.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <ProtectedPage>
      <AppShell title="Clienti">
        <div className="mb-6">
          <p className="text-sm text-muted-foreground">
            Gestioneaza portofoliul de clienti si adauga clienti noi.
          </p>
        </div>

        {/* Add client form */}
        <form onSubmit={onCreate} className="mb-6 flex gap-3">
          <div className="relative flex-1">
            <UserPlus className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Nume client nou"
              className="mcc-input pl-10"
              required
            />
          </div>
          <button className="mcc-btn-primary gap-2">
            <Plus className="h-4 w-4" />
            Adauga
          </button>
        </form>

        {error && (
          <div className="mb-4 rounded-lg border border-destructive/20 bg-destructive/5 p-4">
            <p className="text-sm text-destructive">{error}</p>
          </div>
        )}

        {/* Search bar */}
        <div className="mb-4 relative">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <input
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Cauta clienti..."
            className="mcc-input pl-10"
          />
        </div>

        {/* Clients table */}
        <div className="mcc-card overflow-hidden">
          <table className="min-w-full text-sm">
            <thead>
              <tr className="border-b border-border bg-muted/50">
                <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                  ID
                </th>
                <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                  Nume
                </th>
                <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                  Owner
                </th>
              </tr>
            </thead>
            <tbody>
              {filteredClients.map((client) => (
                <tr
                  key={client.id}
                  className="border-b border-border transition-colors hover:bg-muted/30"
                >
                  <td className="px-4 py-3 font-mono text-xs text-muted-foreground">
                    #{client.id}
                  </td>
                  <td className="px-4 py-3 font-medium text-foreground">{client.name}</td>
                  <td className="px-4 py-3 text-muted-foreground">{client.owner_email}</td>
                </tr>
              ))}
              {filteredClients.length === 0 && (
                <tr>
                  <td className="px-4 py-8 text-center text-muted-foreground" colSpan={3}>
                    {searchQuery
                      ? "Niciun client gasit pentru cautarea ta."
                      : "Nu exista clienti inca."}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </AppShell>
    </ProtectedPage>
  );
}
