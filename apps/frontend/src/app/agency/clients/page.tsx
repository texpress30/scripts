"use client";

import { FormEvent, useEffect, useState } from "react";

import { AppShell } from "@/components/AppShell";
import { ProtectedPage } from "@/components/ProtectedPage";
import { apiRequest } from "@/lib/api";

type ClientRecord = {
  id: number;
  name: string;
  owner_email: string;
  google_customer_id?: string | null;
};

type ClientsResponse = { items: ClientRecord[] };

export default function AgencyClientsPage() {
  const [clients, setClients] = useState<ClientRecord[]>([]);
  const [name, setName] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);


  async function loadClients() {
    const payload = await apiRequest<ClientsResponse>("/clients");
    setClients(payload.items);
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


  return (
    <ProtectedPage>
      <AppShell title="Agency Clients">
        <main className="p-6">
          <form onSubmit={(event) => void onCreateClient(event)} className="mb-4 flex gap-3">
            <input
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder="Nume client"
              className="wm-input"
              required
            />
            <button className="wm-btn-primary" disabled={busy}>{busy ? "Se adaugă..." : "Adaugă"}</button>
          </form>

          {error ? <p className="mb-4 text-red-600">{error}</p> : null}

          <section className="wm-card overflow-hidden">
            <table className="min-w-full text-sm">
              <thead className="bg-slate-100 text-left text-slate-600">
                <tr>
                  <th className="px-4 py-3">ID</th>
                  <th className="px-4 py-3">Nume</th>
                  <th className="px-4 py-3">Google Account</th>
                  <th className="px-4 py-3">Owner</th>
                </tr>
              </thead>
              <tbody>
                {clients.map((client) => (
                  <tr key={client.id} className="border-t border-slate-100">
                    <td className="px-4 py-3">{client.id}</td>
                    <td className="px-4 py-3">{client.name}</td>
                    <td className="px-4 py-3">{client.google_customer_id ?? "-"}</td>
                    <td className="px-4 py-3">{client.owner_email}</td>
                  </tr>
                ))}
                {clients.length === 0 ? (
                  <tr>
                    <td className="px-4 py-4 text-slate-500" colSpan={4}>
                      Nu există clienți încă.
                    </td>
                  </tr>
                ) : null}
              </tbody>
            </table>
          </section>

        </main>
      </AppShell>
    </ProtectedPage>
  );
}
