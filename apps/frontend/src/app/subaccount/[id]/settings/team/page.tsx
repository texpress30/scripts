"use client";

import React, { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { Ban, ChevronDown, Copy, Pencil, Plus, Search, Trash2 } from "lucide-react";
import { useParams } from "next/navigation";

import { AppShell } from "@/components/AppShell";
import { ProtectedPage } from "@/components/ProtectedPage";
import {
  ApiRequestError,
  CreateSubaccountTeamMemberPayload,
  SubaccountTeamMemberItem,
  createSubaccountTeamMember,
  listSubaccountTeamMembers,
} from "@/lib/api";

type TeamUser = {
  id: string;
  prenume: string;
  nume: string;
  email: string;
  telefon: string;
  tip: string;
  roleKey: string;
  sourceLabel: string;
  inherited: boolean;
};

type TeamUserForm = {
  prenume: string;
  nume: string;
  email: string;
  telefon: string;
  extensie: string;
  parola: string;
  role: "subaccount_admin" | "subaccount_user" | "subaccount_viewer";
};

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const PER_PAGE = 5;

function initialsFor(user: TeamUser) {
  return `${user.prenume.charAt(0)}${user.nume.charAt(0)}`.toUpperCase();
}

function roleBadgeClass(role: string) {
  if (role === "subaccount_admin") return "bg-indigo-100 text-indigo-700";
  if (role === "subaccount_viewer") return "bg-teal-100 text-teal-700";
  if (role.startsWith("agency_")) return "bg-amber-100 text-amber-700";
  return "bg-slate-100 text-slate-700";
}

function defaultForm(): TeamUserForm {
  return {
    prenume: "",
    nume: "",
    email: "",
    telefon: "",
    extensie: "",
    parola: "",
    role: "subaccount_user",
  };
}

function mapMemberToUser(item: SubaccountTeamMemberItem): TeamUser {
  return {
    id: item.display_id,
    prenume: item.first_name,
    nume: item.last_name,
    email: item.email,
    telefon: item.phone || "-",
    tip: item.role_label,
    roleKey: item.role_key,
    sourceLabel: item.source_label,
    inherited: item.is_inherited,
  };
}

function getFriendlyListError(error: unknown): string {
  if (error instanceof ApiRequestError) {
    if (error.status === 403) return "Nu ai acces la acest sub-account.";
    if (error.status === 404) return "Sub-account inexistent.";
    if (error.status === 400) return error.message || "Date invalide pentru listare.";
  }
  if (error instanceof Error && error.message.trim()) return error.message;
  return "Nu am putut încărca membrii echipei.";
}

function getFriendlyCreateError(error: unknown): string {
  if (error instanceof ApiRequestError) {
    if (error.status === 403) return "Nu ai acces la acest sub-account.";
    if (error.status === 404) return "Sub-account inexistent.";
    if (error.status === 400) return error.message || "Date invalide.";
  }
  if (error instanceof Error && error.message.trim()) return error.message;
  return "Nu am putut crea utilizatorul.";
}

export default function SubAccountTeamPage() {
  const params = useParams<{ id: string }>();
  const parsedSubaccountId = useMemo(() => {
    const value = String(params?.id ?? "").trim();
    if (!/^\d+$/.test(value)) return null;
    const numeric = Number.parseInt(value, 10);
    return Number.isSafeInteger(numeric) && numeric > 0 ? numeric : null;
  }, [params?.id]);

  const [users, setUsers] = useState<TeamUser[]>([]);
  const [total, setTotal] = useState(0);
  const [activeRole, setActiveRole] = useState<string>("all");
  const [query, setQuery] = useState("");
  const [page, setPage] = useState(1);
  const [toast, setToast] = useState<string | null>(null);
  const [viewMode, setViewMode] = useState<"list" | "form">("list");

  const [form, setForm] = useState<TeamUserForm>(defaultForm());
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);

  const pages = Math.max(1, Math.ceil(total / PER_PAGE));

  useEffect(() => {
    setPage(1);
  }, [query, activeRole, parsedSubaccountId]);

  const loadMembers = useCallback(async () => {
    if (parsedSubaccountId === null) {
      setUsers([]);
      setTotal(0);
      setLoadError("ID de sub-account invalid.");
      return;
    }

    setIsLoading(true);
    setLoadError(null);
    try {
      const userRole = activeRole === "all" ? "" : activeRole;
      const payload = await listSubaccountTeamMembers({
        subaccountId: parsedSubaccountId,
        search: query,
        userRole,
        page,
        pageSize: PER_PAGE,
      });
      setUsers(payload.items.map(mapMemberToUser));
      setTotal(payload.total);
    } catch (error) {
      setUsers([]);
      setTotal(0);
      setLoadError(getFriendlyListError(error));
    } finally {
      setIsLoading(false);
    }
  }, [activeRole, page, parsedSubaccountId, query]);

  useEffect(() => {
    void loadMembers();
  }, [loadMembers]);

  function showToast(message: string) {
    setToast(message);
    window.setTimeout(() => setToast(null), 1800);
  }

  function openCreateForm() {
    setForm(defaultForm());
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

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const nextErrors = validate();
    setErrors(nextErrors);
    if (Object.keys(nextErrors).length > 0) return;
    if (parsedSubaccountId === null) {
      showToast("ID de sub-account invalid.");
      return;
    }

    setIsSubmitting(true);
    try {
      const payload: CreateSubaccountTeamMemberPayload = {
        first_name: form.prenume.trim(),
        last_name: form.nume.trim(),
        email: form.email.trim(),
        phone: form.telefon.trim(),
        extension: form.extensie.trim(),
        user_role: form.role,
      };
      if (form.parola.trim()) payload.password = form.parola;

      await createSubaccountTeamMember(parsedSubaccountId, payload);
      closeForm();
      showToast("Utilizator adăugat.");
      await loadMembers();
    } catch (error) {
      showToast(getFriendlyCreateError(error));
    } finally {
      setIsSubmitting(false);
    }
  }

  const isInvalidSubaccount = parsedSubaccountId === null;

  return (
    <ProtectedPage>
      <AppShell title="Setări sub-account">
        <main className="space-y-6 p-6">
          <header className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
            <h1 className="text-xl font-semibold text-slate-900">Echipa Mea</h1>
            <p className="mt-1 text-sm text-slate-600">Gestionează utilizatorii sub-account-ului #{params?.id ?? "-"}.</p>
          </header>

          {toast ? (
            <div role="status" className="rounded-md border border-emerald-200 bg-emerald-50 px-4 py-2 text-sm text-emerald-700">
              {toast}
            </div>
          ) : null}

          <section className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
            {viewMode === "list" ? (
              <>
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div className="flex flex-wrap items-center gap-2">
                    <button type="button" className="wm-btn-primary inline-flex items-center gap-2" onClick={openCreateForm} disabled={isInvalidSubaccount}>
                      <Plus className="h-4 w-4" />
                      Adaugă Utilizator
                    </button>
                  </div>

                  <div className="flex flex-wrap items-center gap-2">
                    <select
                      className="wm-input max-w-[220px]"
                      value={activeRole}
                      onChange={(e) => setActiveRole(e.target.value)}
                      aria-label="Filtru rol"
                    >
                      <option value="all">Toate rolurile</option>
                      <option value="subaccount_admin">Subaccount Admin</option>
                      <option value="subaccount_user">Subaccount User</option>
                      <option value="subaccount_viewer">Subaccount Viewer</option>
                    </select>
                    <label className="relative block">
                      <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
                      <input
                        className="wm-input pl-9"
                        placeholder="Nume, email, telefon, id-uri"
                        value={query}
                        onChange={(e) => setQuery(e.target.value)}
                      />
                    </label>
                  </div>
                </div>

                {loadError ? <p className="mt-4 rounded-md border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">{loadError}</p> : null}
                {isLoading ? <p className="mt-4 text-sm text-slate-500">Se încarcă membrii...</p> : null}

                {!isLoading && !loadError ? (
                  <>
                    <div className="mt-4 overflow-x-auto">
                      <table className="min-w-full border-separate border-spacing-0">
                        <thead>
                          <tr className="text-left text-xs uppercase tracking-wide text-slate-500">
                            <th className="border-b border-slate-200 px-3 py-2">Nume</th>
                            <th className="border-b border-slate-200 px-3 py-2">Email</th>
                            <th className="border-b border-slate-200 px-3 py-2">Telefon</th>
                            <th className="border-b border-slate-200 px-3 py-2">Tip Utilizator</th>
                            <th className="border-b border-slate-200 px-3 py-2">Acțiuni</th>
                          </tr>
                        </thead>
                        <tbody>
                          {users.map((user) => (
                            <tr key={user.id} className="text-sm text-slate-700">
                              <td className="border-b border-slate-100 px-3 py-3">
                                <div className="flex items-center gap-3">
                                  <div className="flex h-8 w-8 items-center justify-center rounded-full bg-slate-100 text-xs font-semibold text-slate-700">{initialsFor(user)}</div>
                                  <div>
                                    <p className="font-medium text-slate-900">{user.prenume} {user.nume}</p>
                                    <button type="button" className="mt-0.5 inline-flex items-center gap-1 text-xs text-slate-500 hover:text-slate-700" onClick={() => { navigator.clipboard.writeText(user.id).catch(() => {}); showToast("ID Copiat"); }}>
                                      <Copy className="h-3.5 w-3.5" />
                                      Copiere ID: {user.id}
                                    </button>
                                    {user.inherited ? <p className="text-xs text-amber-700">Acces moștenit • {user.sourceLabel}</p> : <p className="text-xs text-slate-500">Acces direct • {user.sourceLabel}</p>}
                                  </div>
                                </div>
                              </td>
                              <td className="border-b border-slate-100 px-3 py-3">{user.email}</td>
                              <td className="border-b border-slate-100 px-3 py-3">{user.telefon || "-"}</td>
                              <td className="border-b border-slate-100 px-3 py-3">
                                <span className={["inline-flex rounded-full px-2 py-1 text-xs font-semibold", roleBadgeClass(user.roleKey)].join(" ")}>{user.tip}</span>
                              </td>
                              <td className="border-b border-slate-100 px-3 py-3">
                                <div className="flex items-center gap-2 text-slate-500">
                                  <button type="button" className="rounded p-1.5 opacity-50" title="Urmează" disabled>
                                    <Pencil className="h-4 w-4" />
                                  </button>
                                  <button type="button" className="rounded p-1.5 opacity-50" title="Urmează" disabled>
                                    <Ban className="h-4 w-4" />
                                  </button>
                                  <button type="button" className="rounded p-1.5 opacity-50" title="Urmează" disabled>
                                    <Trash2 className="h-4 w-4" />
                                  </button>
                                </div>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>

                    {!users.length ? <p className="mt-4 text-sm text-slate-500">Nu există utilizatori pentru filtrele curente.</p> : null}
                  </>
                ) : null}

                <footer className="mt-4 flex items-center justify-between border-t border-slate-200 pt-3 text-sm text-slate-600">
                  <span>Pagina {page} din {pages}</span>
                  <div className="flex items-center gap-2">
                    <button type="button" className="wm-btn-secondary" onClick={() => setPage((p) => Math.max(1, p - 1))} disabled={page === 1 || isLoading}>Anterior</button>
                    <button type="button" className="wm-btn-secondary" onClick={() => setPage((p) => Math.min(pages, p + 1))} disabled={page === pages || isLoading}>Următor</button>
                  </div>
                </footer>
              </>
            ) : (
              <div>
                <button type="button" className="text-sm font-medium text-slate-700 hover:text-slate-900" onClick={closeForm}>← Înapoi</button>
                <p className="mt-2 text-sm text-slate-600">Adaugă un utilizator în echipa sub-account-ului.</p>

                <div className="mt-5 grid grid-cols-1 gap-6 xl:grid-cols-[260px_1fr]">
                  <aside className="space-y-2">
                    <button type="button" className="w-full rounded-md bg-indigo-50 px-3 py-2 text-left text-sm font-semibold text-indigo-700">Informații Utilizator</button>
                    <button type="button" className="w-full rounded-md px-3 py-2 text-left text-sm text-slate-700 hover:bg-slate-50">Roluri și Permisiuni</button>
                  </aside>

                  <form noValidate onSubmit={(event) => { void submit(event); }} className="space-y-5">
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
                      <label className="text-sm text-slate-700">
                        Rol utilizator
                        <select className="wm-input mt-1" value={form.role} onChange={(e) => setForm((prev) => ({ ...prev, role: e.target.value as TeamUserForm["role"] }))}>
                          <option value="subaccount_admin">Subaccount Admin</option>
                          <option value="subaccount_user">Subaccount User</option>
                          <option value="subaccount_viewer">Subaccount Viewer</option>
                        </select>
                      </label>
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
                      <button type="submit" className="wm-btn-primary" disabled={isSubmitting || isInvalidSubaccount}>{isSubmitting ? "Se salvează..." : "Înainte"}</button>
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
