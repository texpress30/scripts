"use client";

import React, { FormEvent, useMemo, useState } from "react";
import { Ban, ChevronDown, Copy, Pencil, Plus, Search, Trash2 } from "lucide-react";
import { useParams } from "next/navigation";

import { AppShell } from "@/components/AppShell";
import { ProtectedPage } from "@/components/ProtectedPage";

type TeamUserType = "ACCOUNT-USER" | "AGENCY-USER" | "ACCOUNT-ADMIN";

type TeamUser = {
  id: string;
  prenume: string;
  nume: string;
  email: string;
  telefon: string;
  tip: TeamUserType;
  deactivated?: boolean;
};

type TeamUserForm = {
  prenume: string;
  nume: string;
  email: string;
  telefon: string;
  extensie: string;
  parola: string;
};

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const PER_PAGE = 5;

const INITIAL_USERS: TeamUser[] = [
  { id: "USR-1001", prenume: "Ana", nume: "Ionescu", email: "ana.ionescu@acme.ro", telefon: "+40 721 000 111", tip: "ACCOUNT-ADMIN" },
  { id: "USR-1002", prenume: "Mihai", nume: "Pop", email: "mihai.pop@acme.ro", telefon: "+40 722 010 210", tip: "ACCOUNT-USER" },
  { id: "USR-1003", prenume: "Raluca", nume: "Dobre", email: "raluca.dobre@acme.ro", telefon: "+40 723 987 654", tip: "AGENCY-USER" },
  { id: "USR-1004", prenume: "Vlad", nume: "Enache", email: "vlad.enache@acme.ro", telefon: "+40 724 220 330", tip: "ACCOUNT-USER" },
  { id: "USR-1005", prenume: "Ioana", nume: "Tudor", email: "ioana.tudor@acme.ro", telefon: "+40 725 456 789", tip: "AGENCY-USER" },
  { id: "USR-1006", prenume: "George", nume: "Munteanu", email: "george.munteanu@acme.ro", telefon: "+40 726 123 555", tip: "ACCOUNT-USER" },
];

function initialsFor(user: TeamUser) {
  return `${user.prenume.charAt(0)}${user.nume.charAt(0)}`.toUpperCase();
}

function roleBadgeClass(role: TeamUserType) {
  if (role === "ACCOUNT-ADMIN") return "bg-indigo-100 text-indigo-700";
  if (role === "AGENCY-USER") return "bg-teal-100 text-teal-700";
  return "bg-slate-100 text-slate-700";
}

function defaultForm(user?: TeamUser): TeamUserForm {
  return {
    prenume: user?.prenume ?? "",
    nume: user?.nume ?? "",
    email: user?.email ?? "",
    telefon: user?.telefon ?? "",
    extensie: "",
    parola: "",
  };
}

export default function SubAccountTeamPage() {
  const params = useParams<{ id: string }>();
  const [users, setUsers] = useState<TeamUser[]>(INITIAL_USERS);
  const [activeRole, setActiveRole] = useState<string>("all");
  const [query, setQuery] = useState("");
  const [page, setPage] = useState(1);
  const [toast, setToast] = useState<string | null>(null);
  const [viewMode, setViewMode] = useState<"list" | "form">("list");
  const [editingUserId, setEditingUserId] = useState<string | null>(null);

  const [form, setForm] = useState<TeamUserForm>(defaultForm());
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [showAdvanced, setShowAdvanced] = useState(false);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return users.filter((u) => {
      const roleMatch = activeRole === "all" || u.tip === activeRole;
      const text = `${u.prenume} ${u.nume} ${u.email} ${u.telefon} ${u.id}`.toLowerCase();
      const searchMatch = q === "" || text.includes(q);
      return roleMatch && searchMatch;
    });
  }, [users, activeRole, query]);

  const pages = Math.max(1, Math.ceil(filtered.length / PER_PAGE));
  const visibleRows = filtered.slice((page - 1) * PER_PAGE, page * PER_PAGE);

  function showToast(message: string) {
    setToast(message);
    window.setTimeout(() => setToast(null), 1800);
  }

  function openCreateForm() {
    setEditingUserId(null);
    setForm(defaultForm());
    setErrors({});
    setShowAdvanced(false);
    setViewMode("form");
  }

  function openEditForm(user: TeamUser) {
    setEditingUserId(user.id);
    setForm(defaultForm(user));
    setErrors({});
    setShowAdvanced(false);
    setViewMode("form");
  }

  function closeForm() {
    setViewMode("list");
    setErrors({});
    setShowAdvanced(false);
  }

  function validate(): Record<string, string> {
    const next: Record<string, string> = {};
    if (form.prenume.trim() === "") next.prenume = "Prenumele este obligatoriu.";
    if (form.nume.trim() === "") next.nume = "Numele este obligatoriu.";
    if (form.email.trim() === "") next.email = "Email-ul este obligatoriu.";
    else if (!EMAIL_RE.test(form.email.trim())) next.email = "Introdu o adresă de email validă.";
    if (form.extensie.trim() !== "" && !/^\d+$/.test(form.extensie.trim())) next.extensie = "Extensia trebuie să fie numerică.";
    return next;
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const nextErrors = validate();
    setErrors(nextErrors);
    if (Object.keys(nextErrors).length > 0) return;

    if (editingUserId) {
      setUsers((prev) =>
        prev.map((user) =>
          user.id === editingUserId
            ? {
                ...user,
                prenume: form.prenume.trim(),
                nume: form.nume.trim(),
                email: form.email.trim(),
                telefon: form.telefon.trim(),
              }
            : user
        )
      );
      showToast("Utilizator actualizat.");
    } else {
      const nextId = `USR-${1000 + users.length + 1}`;
      setUsers((prev) => [
        {
          id: nextId,
          prenume: form.prenume.trim(),
          nume: form.nume.trim(),
          email: form.email.trim(),
          telefon: form.telefon.trim() || "-",
          tip: "ACCOUNT-USER",
        },
        ...prev,
      ]);
      setPage(1);
      showToast("Utilizator adăugat.");
    }

    closeForm();
  }

  function onDelete(userId: string) {
    setUsers((prev) => prev.filter((u) => u.id !== userId));
    showToast("Utilizator șters.");
  }

  function onToggleDeactivate(userId: string) {
    setUsers((prev) => prev.map((u) => (u.id === userId ? { ...u, deactivated: !u.deactivated } : u)));
    showToast("Status utilizator actualizat.");
  }

  return (
    <ProtectedPage>
      <AppShell title={`Sub-account #${params.id} — Echipa Mea`}>
        <main className="p-6">
          {toast ? (
            <div role="status" className="fixed right-6 top-6 z-30 rounded-md bg-slate-900 px-3 py-2 text-sm text-white shadow-md">
              {toast}
            </div>
          ) : null}

          <section className="wm-card rounded-lg p-5 shadow-sm">
            {viewMode === "list" ? (
              <>
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <h1 className="text-xl font-semibold text-slate-900">Echipa Mea</h1>
                  <button type="button" className="wm-btn-primary inline-flex items-center gap-1" onClick={openCreateForm}>
                    <Plus className="h-4 w-4" />
                    Adaugă Utilizator
                  </button>
                </div>

                <div className="mt-4 grid grid-cols-1 gap-3 lg:grid-cols-[220px_1fr]">
                  <label className="text-sm text-slate-700">
                    <span className="sr-only">Rol Utilizator</span>
                    <select className="wm-input" value={activeRole} onChange={(e) => { setActiveRole(e.target.value); setPage(1); }}>
                      <option value="all">Rol Utilizator</option>
                      <option value="ACCOUNT-USER">ACCOUNT-USER</option>
                      <option value="AGENCY-USER">AGENCY-USER</option>
                      <option value="ACCOUNT-ADMIN">ACCOUNT-ADMIN</option>
                    </select>
                  </label>

                  <label className="relative text-sm text-slate-700">
                    <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
                    <span className="sr-only">Căutare utilizatori</span>
                    <input
                      className="wm-input pl-10"
                      placeholder="Nume, email, telefon, id-uri"
                      value={query}
                      onChange={(e) => { setQuery(e.target.value); setPage(1); }}
                    />
                  </label>
                </div>

                <div className="mt-5 overflow-x-auto rounded-lg border border-slate-200">
                  <table className="min-w-full divide-y divide-slate-200 bg-white">
                    <thead className="bg-slate-50 text-left text-xs font-semibold uppercase tracking-wide text-slate-600">
                      <tr>
                        <th className="px-4 py-3">Nume</th>
                        <th className="px-4 py-3">Email</th>
                        <th className="px-4 py-3">Telefon</th>
                        <th className="px-4 py-3">Tip Utilizator</th>
                        <th className="px-4 py-3 text-right">Acțiuni</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100 text-sm text-slate-800">
                      {visibleRows.map((user) => (
                        <tr key={user.id} className={user.deactivated ? "bg-slate-50 opacity-70" : ""}>
                          <td className="px-4 py-3">
                            <div className="flex items-center gap-3">
                              <div className="flex h-9 w-9 items-center justify-center rounded-full bg-indigo-100 text-xs font-semibold text-indigo-700">
                                {initialsFor(user)}
                              </div>
                              <span>{`${user.prenume} ${user.nume}`}</span>
                            </div>
                          </td>
                          <td className="px-4 py-3 align-top">
                            <div>{user.email}</div>
                            <button
                              type="button"
                              className="mt-1 inline-flex items-center gap-1 text-xs text-slate-500 hover:text-slate-700"
                              onClick={() => showToast("ID Copiat")}
                            >
                              <Copy className="h-3.5 w-3.5" /> Copiere ID: {user.id}
                            </button>
                          </td>
                          <td className="px-4 py-3">{user.telefon}</td>
                          <td className="px-4 py-3">
                            <span className={["inline-flex rounded-full px-2 py-1 text-xs font-medium", roleBadgeClass(user.tip)].join(" ")}>{user.tip}</span>
                          </td>
                          <td className="px-4 py-3">
                            <div className="flex items-center justify-end gap-1">
                              <button type="button" aria-label={`Editează ${user.prenume} ${user.nume}`} className="rounded p-1.5 text-slate-600 hover:bg-slate-100" onClick={() => openEditForm(user)}>
                                <Pencil className="h-4 w-4" />
                              </button>
                              <button type="button" aria-label={`Șterge ${user.prenume} ${user.nume}`} className="rounded p-1.5 text-slate-600 hover:bg-slate-100" onClick={() => onDelete(user.id)}>
                                <Trash2 className="h-4 w-4" />
                              </button>
                              <button type="button" aria-label={`Dezactivează ${user.prenume} ${user.nume}`} className="rounded p-1.5 text-slate-600 hover:bg-slate-100" onClick={() => onToggleDeactivate(user.id)}>
                                <Ban className="h-4 w-4" />
                              </button>
                            </div>
                          </td>
                        </tr>
                      ))}
                      {visibleRows.length === 0 ? (
                        <tr>
                          <td colSpan={5} className="px-4 py-6 text-center text-sm text-slate-500">Nu există utilizatori pentru filtrele selectate.</td>
                        </tr>
                      ) : null}
                    </tbody>
                  </table>
                </div>

                <footer className="mt-4 flex items-center justify-end gap-2 text-sm">
                  <button type="button" className="wm-btn-secondary" onClick={() => setPage((p) => Math.max(1, p - 1))} disabled={page === 1}>
                    Anterior
                  </button>
                  <span className="rounded border border-slate-200 px-3 py-1 text-slate-700">{page}</span>
                  <button type="button" className="wm-btn-secondary" onClick={() => setPage((p) => Math.min(pages, p + 1))} disabled={page === pages}>
                    Următor
                  </button>
                </footer>
              </>
            ) : (
              <div>
                <button type="button" className="text-sm font-medium text-slate-700 hover:text-slate-900" onClick={closeForm}>← Înapoi</button>
                <p className="mt-2 text-sm text-slate-600">Editează sau gestionează echipa ta.</p>

                <div className="mt-5 grid grid-cols-1 gap-6 xl:grid-cols-[260px_1fr]">
                  <aside className="space-y-2">
                    <button type="button" className="w-full rounded-md bg-indigo-50 px-3 py-2 text-left text-sm font-semibold text-indigo-700">Informații Utilizator</button>
                    <button type="button" className="w-full rounded-md px-3 py-2 text-left text-sm text-slate-700 hover:bg-slate-50">Roluri și Permisiuni</button>
                  </aside>

                  <form noValidate onSubmit={submit} className="space-y-5">
                    <div className="rounded-lg border border-slate-200 p-4">
                      <h2 className="text-base font-semibold text-slate-900">Informații Utilizator</h2>
                      <div className="mt-4 space-y-4">
                        <div>
                          <p className="text-sm font-medium text-slate-700">Imagine Profil</p>
                          <div className="mt-2 flex items-center gap-4">
                            <div className="h-24 w-24 rounded-full border border-slate-300 bg-slate-50" />
                            <p className="text-xs text-slate-500">Mărimea propusă este 512x512 px, nu mai mare de 2.5 MB.</p>
                          </div>
                        </div>

                        <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                          <label className="text-sm text-slate-700">
                            Prenume <span className="text-red-500">*</span>
                            <input placeholder="Prenume" className="wm-input mt-1" value={form.prenume} onChange={(e) => setForm((prev) => ({ ...prev, prenume: e.target.value }))} />
                            {errors.prenume ? <p className="mt-1 text-xs text-red-600">{errors.prenume}</p> : null}
                          </label>

                          <label className="text-sm text-slate-700">
                            Nume <span className="text-red-500">*</span>
                            <input placeholder="Nume" className="wm-input mt-1" value={form.nume} onChange={(e) => setForm((prev) => ({ ...prev, nume: e.target.value }))} />
                            {errors.nume ? <p className="mt-1 text-xs text-red-600">{errors.nume}</p> : null}
                          </label>

                          <label className="text-sm text-slate-700 md:col-span-2">
                            Email <span className="text-red-500">*</span>
                            <input type="email" placeholder="Email" className="wm-input mt-1" value={form.email} onChange={(e) => setForm((prev) => ({ ...prev, email: e.target.value }))} />
                            {errors.email ? <p className="mt-1 text-xs text-red-600">{errors.email}</p> : null}
                          </label>

                          <label className="text-sm text-slate-700">
                            Telefon
                            <input type="tel" placeholder="Telefon" className="wm-input mt-1" value={form.telefon} onChange={(e) => setForm((prev) => ({ ...prev, telefon: e.target.value }))} />
                          </label>

                          <label className="text-sm text-slate-700">
                            Extensie
                            <input inputMode="numeric" placeholder="Extensie" className="wm-input mt-1" value={form.extensie} onChange={(e) => setForm((prev) => ({ ...prev, extensie: e.target.value }))} />
                            {errors.extensie ? <p className="mt-1 text-xs text-red-600">{errors.extensie}</p> : null}
                          </label>
                        </div>
                      </div>
                    </div>

                    <div className="rounded-lg border border-slate-200 p-4">
                      <button type="button" className="flex w-full items-center justify-between text-left" onClick={() => setShowAdvanced((prev) => !prev)} aria-expanded={showAdvanced}>
                        <span className="text-sm font-semibold text-slate-800">Setări Avansate</span>
                        <ChevronDown className={["h-4 w-4 text-slate-600 transition-transform", showAdvanced ? "rotate-180" : "rotate-0"].join(" ")} />
                      </button>

                      {showAdvanced ? (
                        <div className="mt-4 overflow-hidden transition-all duration-300">
                          <label className="text-sm text-slate-700">
                            Parolă
                            <input type="password" placeholder="Parolă" className="wm-input mt-1" value={form.parola} onChange={(e) => setForm((prev) => ({ ...prev, parola: e.target.value }))} />
                          </label>
                        </div>
                      ) : null}
                    </div>

                    <footer className="flex justify-end gap-2 border-t border-slate-200 pt-4">
                      <button type="button" className="wm-btn-secondary" onClick={closeForm}>Anulează</button>
                      <button type="submit" className="wm-btn-primary">Înainte</button>
                    </footer>
                  </form>
                </div>
              </div>
            )}
          </section>
        </main>
      </AppShell>
    </ProtectedPage>
  );
}
