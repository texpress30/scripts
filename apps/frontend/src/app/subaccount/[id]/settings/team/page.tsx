"use client";

import React, { useMemo, useState } from "react";
import { Ban, Copy, Pencil, Search, Trash2, UserCircle2 } from "lucide-react";
import { useParams } from "next/navigation";

import { AppShell } from "@/components/AppShell";
import { ProtectedPage } from "@/components/ProtectedPage";

type TipUtilizator = "ACCOUNT-USER" | "AGENCY-USER" | "ACCOUNT-ADMIN";

type Utilizator = {
  id: string;
  prenume: string;
  nume: string;
  email: string;
  telefon: string;
  tip: TipUtilizator;
  avatar?: string;
};

const ITEMS_PER_PAGE = 5;

const UTILIZATORI: Utilizator[] = [
  { id: "pJsmlDACYqmO0DqYWbk0", prenume: "Andrei", nume: "Pop", email: "andrei.pop@acme.ro", telefon: "+40 721 111 222", tip: "ACCOUNT-USER" },
  { id: "X9ksl22mQm7Vb9aK1uQn", prenume: "Ioana", nume: "Dobre", email: "ioana.dobre@acme.ro", telefon: "+40 722 333 444", tip: "AGENCY-USER" },
  { id: "t91Ks0QazP2nL8mN56cx", prenume: "Mihai", nume: "Sava", email: "mihai.sava@acme.ro", telefon: "+40 723 555 666", tip: "ACCOUNT-ADMIN" },
  { id: "b3QnL8Kz2P91mTs0Yaxw", prenume: "Elena", nume: "Radu", email: "elena.radu@acme.ro", telefon: "+40 724 777 888", tip: "ACCOUNT-USER" },
  { id: "v6Kp0Za2Y8nLt3Qm1Xcw", prenume: "Roxana", nume: "Stoica", email: "roxana.stoica@acme.ro", telefon: "+40 725 999 000", tip: "AGENCY-USER" },
  { id: "Jm4QnL8sP2aZ0kX7cV1t", prenume: "Paul", nume: "Marin", email: "paul.marin@acme.ro", telefon: "+40 726 101 202", tip: "ACCOUNT-USER" },
];

function initiale(prenume: string, nume: string): string {
  const a = prenume.trim().charAt(0).toUpperCase();
  const b = nume.trim().charAt(0).toUpperCase();
  return `${a || "?"}${b || "?"}`;
}

function badgeTip(tip: TipUtilizator): string {
  switch (tip) {
    case "ACCOUNT-ADMIN":
      return "bg-indigo-100 text-indigo-700";
    case "AGENCY-USER":
      return "bg-emerald-100 text-emerald-700";
    default:
      return "bg-slate-100 text-slate-700";
  }
}

export default function SubAccountTeamPage() {
  const params = useParams<{ id: string }>();

  const [rol, setRol] = useState<string>("");
  const [query, setQuery] = useState("");
  const [pagina, setPagina] = useState(1);
  const [toast, setToast] = useState("");

  const filtrati = useMemo(() => {
    const q = query.trim().toLowerCase();
    return UTILIZATORI.filter((u) => {
      if (rol && u.tip !== rol) return false;
      if (!q) return true;
      const fullName = `${u.prenume} ${u.nume}`.toLowerCase();
      return fullName.includes(q) || u.email.toLowerCase().includes(q) || u.telefon.toLowerCase().includes(q) || u.id.toLowerCase().includes(q);
    });
  }, [rol, query]);

  const totalPagini = Math.max(1, Math.ceil(filtrati.length / ITEMS_PER_PAGE));
  const paginaCurenta = Math.min(pagina, totalPagini);
  const start = (paginaCurenta - 1) * ITEMS_PER_PAGE;
  const rows = filtrati.slice(start, start + ITEMS_PER_PAGE);

  function copieazaId(id: string) {
    if (typeof navigator !== "undefined" && navigator.clipboard?.writeText) {
      void navigator.clipboard.writeText(id);
    }
    setToast("ID Copiat");
    window.setTimeout(() => setToast(""), 1800);
  }

  return (
    <ProtectedPage>
      <AppShell title={`Sub-account #${params.id} — Echipa Mea`}>
        <main className="p-6">
          {toast ? <div className="mb-3 rounded-md border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-700">{toast}</div> : null}

          <section className="wm-card rounded-lg p-4 shadow-sm">
            <header className="mb-4 flex flex-wrap items-center justify-between gap-3">
              <h1 className="text-xl font-semibold text-slate-900">Echipa Mea</h1>
              <button type="button" className="wm-btn-primary">+ Adaugă Utilizator</button>
            </header>

            <div className="mb-4 grid grid-cols-1 gap-3 lg:grid-cols-[220px_1fr]">
              <select
                className="wm-input"
                value={rol}
                onChange={(e) => {
                  setRol(e.target.value);
                  setPagina(1);
                }}
              >
                <option value="">Rol Utilizator</option>
                <option value="ACCOUNT-USER">ACCOUNT-USER</option>
                <option value="AGENCY-USER">AGENCY-USER</option>
                <option value="ACCOUNT-ADMIN">ACCOUNT-ADMIN</option>
              </select>

              <label className="relative">
                <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
                <input
                  className="wm-input pl-9"
                  placeholder="Nume, email, telefon, id-uri"
                  value={query}
                  onChange={(e) => {
                    setQuery(e.target.value);
                    setPagina(1);
                  }}
                />
              </label>
            </div>

            <div className="overflow-auto rounded-md border border-slate-200">
              <table className="min-w-full text-sm">
                <thead className="bg-slate-50 text-left text-slate-600">
                  <tr>
                    <th className="px-4 py-3 font-semibold">Nume</th>
                    <th className="px-4 py-3 font-semibold">Email</th>
                    <th className="px-4 py-3 font-semibold">Telefon</th>
                    <th className="px-4 py-3 font-semibold">Tip Utilizator</th>
                    <th className="px-4 py-3 font-semibold text-right">Acțiuni</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.length <= 0 ? (
                    <tr>
                      <td colSpan={5} className="px-4 py-8 text-center text-slate-500">Nu există utilizatori pentru filtrele selectate.</td>
                    </tr>
                  ) : (
                    rows.map((u) => (
                      <tr key={u.id} className="border-t border-slate-100 hover:bg-slate-50/70">
                        <td className="px-4 py-3">
                          <div className="flex items-center gap-3">
                            {u.avatar ? (
                              <img src={u.avatar} alt={`${u.prenume} ${u.nume}`} className="h-9 w-9 rounded-full object-cover" />
                            ) : (
                              <div className="flex h-9 w-9 items-center justify-center rounded-full bg-slate-100 text-xs font-semibold text-slate-700">{initiale(u.prenume, u.nume)}</div>
                            )}
                            <span className="font-medium text-slate-800">{u.prenume} {u.nume}</span>
                          </div>
                        </td>
                        <td className="px-4 py-3">
                          <p className="text-slate-800">{u.email}</p>
                          <button type="button" className="mt-1 inline-flex items-center gap-1 text-xs text-slate-500 hover:text-slate-700" onClick={() => copieazaId(u.id)}>
                            {u.id}
                            <Copy className="h-3.5 w-3.5" />
                          </button>
                        </td>
                        <td className="px-4 py-3 text-slate-700">{u.telefon}</td>
                        <td className="px-4 py-3">
                          <span className={`inline-flex rounded-full px-2 py-1 text-xs font-semibold ${badgeTip(u.tip)}`}>{u.tip}</span>
                        </td>
                        <td className="px-4 py-3">
                          <div className="flex items-center justify-end gap-2">
                            <button type="button" className="rounded p-1.5 text-slate-500 hover:bg-slate-100 hover:text-slate-700" title="Editează utilizator">
                              <Pencil className="h-4 w-4" />
                            </button>
                            <button type="button" className="rounded p-1.5 text-slate-500 hover:bg-slate-100 hover:text-rose-600" title="Șterge utilizator">
                              <Trash2 className="h-4 w-4" />
                            </button>
                            <button type="button" className="rounded p-1.5 text-slate-500 hover:bg-slate-100 hover:text-amber-600" title="Dezactivează utilizator">
                              <Ban className="h-4 w-4" />
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>

            <footer className="mt-4 flex items-center justify-between">
              <p className="text-sm text-slate-600">Pagina {paginaCurenta}</p>
              <div className="flex items-center gap-2">
                <button type="button" className="wm-btn-secondary" disabled={paginaCurenta <= 1} onClick={() => setPagina((p) => Math.max(1, p - 1))}>Anterior</button>
                <span className="inline-flex h-9 min-w-9 items-center justify-center rounded-md bg-blue-600 px-3 text-sm font-semibold text-white">{paginaCurenta}</span>
                <button type="button" className="wm-btn-secondary" disabled={paginaCurenta >= totalPagini} onClick={() => setPagina((p) => Math.min(totalPagini, p + 1))}>Următor</button>
              </div>
            </footer>
          </section>
        </main>
      </AppShell>
    </ProtectedPage>
  );
}
