"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";

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

  async function loadClients() {
    setError("");
    try {
      const result = await apiRequest<ClientsResponse>("/clients");
      setClients(result.items);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Nu pot încărca lista de clienți");
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
        body: JSON.stringify({ name })
      });
      setName("");
      await loadClients();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Nu pot crea clientul");
    }
  }

  return (
    <ProtectedPage>
      <main className="mx-auto min-h-screen max-w-5xl p-6">
        <header className="mb-6 flex items-center justify-between">
          <h1 className="text-2xl font-semibold">Clienți</h1>
          <Link href="/dashboard" className="text-brand-600">
            Înapoi la Dashboard
          </Link>
        </header>

        <form onSubmit={onCreate} className="mb-6 flex gap-3">
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Nume client"
            className="w-full rounded border border-slate-300 px-3 py-2"
            required
          />
          <button className="rounded bg-brand-500 px-4 py-2 font-medium text-white hover:bg-brand-600">Adaugă</button>
        </form>

        {error ? <p className="mb-4 text-red-600">{error}</p> : null}

        <section className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
          <table className="min-w-full text-sm">
            <thead className="bg-slate-100 text-left text-slate-600">
              <tr>
                <th className="px-4 py-3">ID</th>
                <th className="px-4 py-3">Nume</th>
                <th className="px-4 py-3">Owner</th>
              </tr>
            </thead>
            <tbody>
              {clients.map((client) => (
                <tr key={client.id} className="border-t border-slate-100">
                  <td className="px-4 py-3">{client.id}</td>
                  <td className="px-4 py-3">{client.name}</td>
                  <td className="px-4 py-3">{client.owner_email}</td>
                </tr>
              ))}
              {clients.length === 0 ? (
                <tr>
                  <td className="px-4 py-4 text-slate-500" colSpan={3}>
                    Nu există clienți încă.
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </section>
      </main>
    </ProtectedPage>
  );
}
