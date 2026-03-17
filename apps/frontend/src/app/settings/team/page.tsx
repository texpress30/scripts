"use client";

import React, { FormEvent, useEffect, useMemo, useState } from "react";
import { Camera, ChevronLeft, Loader2, Pencil, Search, Trash2, UserCircle2 } from "lucide-react";

import { AppShell } from "@/components/AppShell";
import { ProtectedPage } from "@/components/ProtectedPage";
import { ApiRequestError, TeamModuleCatalogItem, apiRequest, getTeamModuleCatalog, inviteTeamMember } from "@/lib/api";

type TeamMember = {
  id: number;
  membership_id?: number | null;
  user_id?: number | null;
  first_name: string;
  last_name: string;
  email: string;
  phone: string;
  extension: string;
  user_type: string;
  user_role: string;
  location: string;
  subaccount: string;
  module_keys?: string[];
};

type TeamListResponse = {
  items: TeamMember[];
  total: number;
  page: number;
  page_size: number;
};

type SubaccountOption = {
  id: number;
  name: string;
  label: string;
};

type SubaccountOptionsResponse = {
  items: SubaccountOption[];
};

type ModuleCatalogItem = {
  key: string;
  label: string;
  order: number;
};

const PAGE_SIZE = 10;

function initials(firstName: string, lastName: string) {
  const a = firstName.trim().charAt(0).toUpperCase();
  const b = lastName.trim().charAt(0).toUpperCase();
  return `${a || "?"}${b || "?"}`;
}

export default function SettingsTeamPage() {
  const [mode, setMode] = useState<"list" | "create">("list");

  const [search, setSearch] = useState("");
  const [userTypeFilter, setUserTypeFilter] = useState("");
  const [userRoleFilter, setUserRoleFilter] = useState("");
  const [subaccountFilter, setSubaccountFilter] = useState("");

  const [members, setMembers] = useState<TeamMember[]>([]);
  const [loadingMembers, setLoadingMembers] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");
  const [toastMessage, setToastMessage] = useState("");
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);

  const [subaccountOptions, setSubaccountOptions] = useState<SubaccountOption[]>([]);
  const [subaccountOptionsLoading, setSubaccountOptionsLoading] = useState(false);
  const [subaccountOptionsError, setSubaccountOptionsError] = useState("");
  const [moduleCatalog, setModuleCatalog] = useState<ModuleCatalogItem[]>([]);
  const [moduleCatalogLoading, setModuleCatalogLoading] = useState(false);
  const [moduleCatalogError, setModuleCatalogError] = useState("");

  const [advancedOpen, setAdvancedOpen] = useState(false);
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [extension, setExtension] = useState("");
  const [userType, setUserType] = useState("agency");
  const [userRole, setUserRole] = useState("member");
  const [location, setLocation] = useState("România");
  const [subaccount, setSubaccount] = useState("");
  const [subaccountFieldError, setSubaccountFieldError] = useState("");
  const [moduleFieldError, setModuleFieldError] = useState("");
  const [selectedModuleKeys, setSelectedModuleKeys] = useState<string[]>([]);
  const [password, setPassword] = useState("");
  const [autoInviteAfterCreate, setAutoInviteAfterCreate] = useState(false);
  const [saving, setSaving] = useState(false);
  const [inviteLoadingByMembership, setInviteLoadingByMembership] = useState<Record<number, boolean>>({});

  const totalPages = useMemo(() => Math.max(1, Math.ceil(total / PAGE_SIZE)), [total]);

  function showToast(message: string) {
    setToastMessage(message);
    window.setTimeout(() => setToastMessage(""), 2200);
  }

  async function loadSubaccountOptions() {
    setSubaccountOptionsLoading(true);
    setSubaccountOptionsError("");
    try {
      const data = await apiRequest<SubaccountOptionsResponse>("/team/subaccount-options");
      const normalized = (data.items ?? []).map((item) => ({
        id: Number(item.id),
        name: String(item.name ?? "").trim(),
        label: String(item.label ?? "").trim() || String(item.name ?? "").trim(),
      }));
      setSubaccountOptions(normalized.filter((item) => item.name !== "" && Number.isFinite(item.id)));
    } catch (err) {
      setSubaccountOptions([]);
      setSubaccountOptionsError(err instanceof Error ? err.message : "Nu am putut încărca sub-conturile.");
    } finally {
      setSubaccountOptionsLoading(false);
    }
  }

  async function loadModuleCatalog() {
    setModuleCatalogLoading(true);
    setModuleCatalogError("");
    try {
      const data = await getTeamModuleCatalog("subaccount");
      const normalized = (data.items ?? [])
        .map((item: TeamModuleCatalogItem) => ({
          key: String(item.key ?? "").trim().toLowerCase(),
          label: String(item.label ?? "").trim() || String(item.key ?? "").trim(),
          order: Number(item.order ?? 0),
        }))
        .filter((item) => item.key !== "")
        .sort((a, b) => a.order - b.order || a.label.localeCompare(b.label));
      setModuleCatalog(normalized);
      setSelectedModuleKeys((prev) => {
        if (prev.length > 0) return prev;
        return normalized.map((item) => item.key);
      });
    } catch (err) {
      setModuleCatalog([]);
      setModuleCatalogError(err instanceof Error ? err.message : "Nu am putut încărca modulele disponibile.");
    } finally {
      setModuleCatalogLoading(false);
    }
  }

  async function loadMembers() {
    setLoadingMembers(true);
    setErrorMessage("");
    try {
      const params = new URLSearchParams({
        page: String(page),
        page_size: String(PAGE_SIZE),
      });
      if (search.trim()) params.set("search", search.trim());
      if (userTypeFilter) params.set("user_type", userTypeFilter);
      if (userRoleFilter) params.set("user_role", userRoleFilter);
      if (subaccountFilter) params.set("subaccount", subaccountFilter);

      const data = await apiRequest<TeamListResponse>(`/team/members?${params.toString()}`);
      setMembers(data.items);
      setTotal(data.total);
    } catch (err) {
      setErrorMessage(err instanceof Error ? err.message : "Nu am putut încărca echipa.");
      setMembers([]);
      setTotal(0);
    } finally {
      setLoadingMembers(false);
    }
  }

  useEffect(() => {
    void loadSubaccountOptions();
    void loadModuleCatalog();
  }, []);

  useEffect(() => {
    if (mode === "list") {
      void loadMembers();
    }
  }, [mode, page, search, userTypeFilter, userRoleFilter, subaccountFilter]);

  useEffect(() => {
    if (userType === "agency") {
      setSubaccount("");
      setSubaccountFieldError("");
      setModuleFieldError("");
    }
  }, [userType]);

  function resetCreateForm() {
    setFirstName("");
    setLastName("");
    setEmail("");
    setPhone("");
    setExtension("");
    setUserType("agency");
    setUserRole("member");
    setLocation("România");
    setSubaccount("");
    setSubaccountFieldError("");
    setModuleFieldError("");
    setSelectedModuleKeys(moduleCatalog.map((item) => item.key));
    setPassword("");
    setAutoInviteAfterCreate(false);
    setAdvancedOpen(false);
  }

  function getMembershipId(member: TeamMember): number | null {
    const candidate = member.membership_id ?? member.id;
    if (!Number.isFinite(Number(candidate))) return null;
    return Number(candidate);
  }

  function canInviteMember(member: TeamMember): boolean {
    const membershipId = getMembershipId(member);
        return membershipId !== null && String(member.email || "").trim() !== "";
  }

  function inviteErrorMessage(error: unknown): string {
    if (error instanceof ApiRequestError) {
      if (error.status === 403) return "Nu ai permisiunea să trimiți invitații pentru acest utilizator";
      if (error.status === 404) return "Utilizatorul sau membership-ul nu mai există";
      if (error.status === 503) return "Invitațiile sunt indisponibile temporar. Încearcă din nou mai târziu.";
      return error.message || "Nu am putut trimite invitația";
    }
    return error instanceof Error ? error.message : "Nu am putut trimite invitația";
  }

  async function onInviteMember(member: TeamMember) {
    const membershipId = getMembershipId(member);
    if (membershipId === null) {
      setErrorMessage("Utilizatorul nu are un membership valid pentru invitație.");
      return;
    }

    setErrorMessage("");
    setInviteLoadingByMembership((prev) => ({ ...prev, [membershipId]: true }));
    try {
      const response = await inviteTeamMember(membershipId);
      showToast(response.message || "Invitația a fost trimisă");
    } catch (err) {
      setErrorMessage(inviteErrorMessage(err));
    } finally {
      setInviteLoadingByMembership((prev) => {
        const next = { ...prev };
        delete next[membershipId];
        return next;
      });
    }
  }

  async function submitCreateForm(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaving(true);
    setErrorMessage("");
    setSubaccountFieldError("");
    setModuleFieldError("");

    if (userType === "client" && !subaccount.trim()) {
      setSaving(false);
      setSubaccountFieldError("Selectarea unui sub-cont este obligatorie pentru utilizatorii de tip client.");
      return;
    }

    const shouldSendModuleKeys = userType === "client" && subaccount.trim() !== "" && moduleCatalog.length > 0;
    if (shouldSendModuleKeys && selectedModuleKeys.length === 0) {
      setSaving(false);
      setModuleFieldError("Selectează cel puțin un modul pentru utilizatorul de tip client.");
      return;
    }

    try {
      const payload: Record<string, unknown> = {
        first_name: firstName,
        last_name: lastName,
        email,
        phone,
        extension,
        user_type: userType,
        user_role: userRole,
        location,
        subaccount: userType === "client" ? subaccount : "",
        password: advancedOpen ? password : undefined,
      };
      if (shouldSendModuleKeys) {
        payload.module_keys = selectedModuleKeys;
      }

      const createResponse = await apiRequest<{ item: TeamMember }>("/team/members", {
        method: "POST",
        body: JSON.stringify(payload),
      });

      if (!autoInviteAfterCreate) {
        showToast("Utilizator adăugat cu succes.");
      } else {
        const createdMembershipId = (() => {
          const candidate = createResponse.item?.membership_id ?? createResponse.item?.id;
          if (!Number.isFinite(Number(candidate))) return null;
          return Number(candidate);
        })();

        if (createdMembershipId === null) {
          showToast("Utilizatorul a fost creat, dar invitația nu a putut fi trimisă");
        } else {
          try {
            await inviteTeamMember(createdMembershipId);
            showToast("Utilizatorul a fost creat și invitația a fost trimisă");
          } catch (inviteError) {
            showToast(`Utilizatorul a fost creat, dar invitația nu a putut fi trimisă. ${inviteErrorMessage(inviteError)}`);
          }
        }
      }

      resetCreateForm();
      setMode("list");
      setPage(1);
      void loadMembers();
    } catch (err) {
      if (err instanceof ApiRequestError) {
        if (err.message.toLowerCase().includes("modul invalid")) {
          setErrorMessage(`Modulele selectate sunt invalide. ${err.message}`);
        } else if (err.message.toLowerCase().includes("module_keys este permis doar")) {
          setErrorMessage("Permisiunile pe module sunt disponibile doar pentru utilizatorii de tip client/sub-account.");
        } else {
          setErrorMessage(err.message || "Nu am putut adăuga utilizatorul.");
        }
      } else {
        setErrorMessage(err instanceof Error ? err.message : "Nu am putut adăuga utilizatorul.");
      }
    } finally {
      setSaving(false);
    }
  }

  const shouldShowModulePermissions = userType === "client" && subaccount.trim() !== "";

  function toggleModule(moduleKey: string) {
    setSelectedModuleKeys((prev) => {
      if (prev.includes(moduleKey)) {
        return prev.filter((key) => key !== moduleKey);
      }
      return [...prev, moduleKey];
    });
    setModuleFieldError("");
  }

  return (
    <ProtectedPage>
      <AppShell title="Settings — Echipă">
        <main className="p-6">
          {toastMessage ? <div className="mb-3 rounded-md border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-700">{toastMessage}</div> : null}
          {errorMessage ? <div className="mb-3 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{errorMessage}</div> : null}

          {mode === "list" ? (
            <section className="space-y-4">
              <header className="flex flex-wrap items-center justify-between gap-3">
                <h1 className="text-2xl font-semibold text-slate-900">Echipă</h1>
                <button className="wm-btn-primary" type="button" onClick={() => setMode("create")}>+ Adaugă Utilizator</button>
              </header>

              <div className="wm-card space-y-4 p-4">
                {subaccountOptionsError ? <p className="text-xs text-amber-700">Sub-conturile nu au putut fi încărcate: {subaccountOptionsError}</p> : null}

                <div className="grid grid-cols-1 gap-3 lg:grid-cols-4">
                  <select className="wm-input" value={userTypeFilter} onChange={(e) => { setPage(1); setUserTypeFilter(e.target.value); }}>
                    <option value="">Tip Utilizator</option>
                    <option value="agency">Agency</option>
                    <option value="client">Client</option>
                  </select>
                  <select className="wm-input" value={userRoleFilter} onChange={(e) => { setPage(1); setUserRoleFilter(e.target.value); }}>
                    <option value="">Rol Utilizator</option>
                    <option value="admin">Admin</option>
                    <option value="member">Membru</option>
                    <option value="viewer">Viewer</option>
                  </select>
                  <select className="wm-input" value={subaccountFilter} onChange={(e) => { setPage(1); setSubaccountFilter(e.target.value); }}>
                    <option value="">Toate</option>
                    {subaccountOptions.map((item) => (
                      <option key={item.id} value={String(item.id)}>{item.label || item.name}</option>
                    ))}
                  </select>
                  <label className="relative">
                    <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
                    <input className="wm-input pl-9" placeholder="Caută nume, email, telefon" value={search} onChange={(e) => { setPage(1); setSearch(e.target.value); }} />
                  </label>
                </div>

                <div className="overflow-hidden rounded-lg border border-slate-200">
                  <table className="w-full text-sm">
                    <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
                      <tr>
                        <th className="px-3 py-2">Nume</th>
                        <th className="px-3 py-2">Email</th>
                        <th className="px-3 py-2">Telefon</th>
                        <th className="px-3 py-2">Tip Utilizator</th>
                        <th className="px-3 py-2">Locație</th>
                        <th className="px-3 py-2 text-right">Acțiuni</th>
                      </tr>
                    </thead>
                    <tbody>
                      {loadingMembers ? (
                        <tr>
                          <td className="px-3 py-6 text-center text-slate-500" colSpan={6}>Se încarcă membri...</td>
                        </tr>
                      ) : members.length === 0 ? (
                        <tr>
                          <td className="px-3 py-6 text-center text-slate-500" colSpan={6}>Nu există membri pentru filtrele curente.</td>
                        </tr>
                      ) : (
                        members.map((member) => (
                          <tr key={member.id} className="border-t border-slate-100">
                            <td className="px-3 py-2">
                              <div className="flex items-center gap-2">
                                <span className="inline-flex h-8 w-8 items-center justify-center rounded-full bg-indigo-100 text-xs font-semibold text-indigo-700">
                                  {initials(member.first_name, member.last_name)}
                                </span>
                                <span>{member.first_name} {member.last_name}</span>
                              </div>
                            </td>
                            <td className="px-3 py-2">{member.email}</td>
                            <td className="px-3 py-2">{member.phone || "-"}</td>
                            <td className="px-3 py-2">{member.user_type}</td>
                            <td className="px-3 py-2">{member.location}</td>
                            <td className="px-3 py-2">
                              <div className="flex items-center justify-end gap-2 text-slate-500">
                                <button type="button" className="rounded p-1 hover:bg-slate-100" title="Editează"><Pencil className="h-4 w-4" /></button>
                                <button type="button" className="rounded p-1 hover:bg-slate-100" title="Șterge"><Trash2 className="h-4 w-4" /></button>
                                {(() => {
                                  const membershipId = getMembershipId(member);
                                  const eligible = canInviteMember(member);
                                  const loadingInvite = membershipId !== null && Boolean(inviteLoadingByMembership[membershipId]);
                                  return (
                                    <button
                                      type="button"
                                      className="rounded border border-slate-200 px-2 py-1 text-xs text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
                                      title="Trimite invitație"
                                      disabled={!eligible || loadingInvite}
                                      onClick={() => void onInviteMember(member)}
                                    >
                                      {loadingInvite ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : "Trimite invitație"}
                                    </button>
                                  );
                                })()}
                              </div>
                            </td>
                          </tr>
                        ))
                      )}
                    </tbody>
                  </table>
                </div>

                <footer className="flex items-center justify-between border-t border-slate-100 pt-3 text-sm text-slate-600">
                  <span>Pagina {page} din {totalPages}</span>
                  <div className="flex items-center gap-2">
                    <button className="wm-btn-secondary" type="button" onClick={() => setPage((prev) => Math.max(1, prev - 1))} disabled={page <= 1}>
                      Înapoi
                    </button>
                    <button className="wm-btn-secondary" type="button" onClick={() => setPage((prev) => Math.min(totalPages, prev + 1))} disabled={page >= totalPages}>
                      Înainte
                    </button>
                  </div>
                </footer>
              </div>
            </section>
          ) : (
            <section className="space-y-4">
              <header className="flex items-center gap-3">
                <button className="inline-flex items-center gap-1 rounded-md border border-slate-200 px-2 py-1 text-sm text-slate-600 hover:bg-slate-50" type="button" onClick={() => setMode("list")}>
                  <ChevronLeft className="h-4 w-4" /> Înapoi
                </button>
                <h1 className="text-2xl font-semibold text-slate-900">Editează sau gestionează echipa</h1>
              </header>

              <div className="grid grid-cols-1 gap-4 lg:grid-cols-[220px_minmax(0,1fr)]">
                <aside className="wm-card p-4">
                  <p className="text-sm font-semibold text-slate-900">Informații Utilizator</p>
                  <p className="mt-2 text-sm text-slate-500">Roluri și Permisiuni</p>
                </aside>

                <form className="wm-card space-y-4 p-4" onSubmit={submitCreateForm}>
                  <h2 className="text-lg font-semibold text-slate-900">Informații Utilizator</h2>

                  {subaccountOptionsError ? <p className="text-xs text-amber-700">Sub-conturile nu au putut fi încărcate: {subaccountOptionsError}</p> : null}
                  {subaccountOptionsLoading ? <p className="text-xs text-slate-500">Se încarcă sub-conturile...</p> : null}

                  <div className="flex flex-col gap-3 md:flex-row md:items-center">
                    <div className="relative h-24 w-24 rounded-full border border-slate-200 bg-slate-50">
                      <div className="flex h-full w-full items-center justify-center text-slate-400">
                        <UserCircle2 className="h-14 w-14" />
                      </div>
                      <button type="button" className="absolute -bottom-1 -right-1 rounded-full border border-slate-200 bg-white p-1 text-slate-500 hover:bg-slate-50" title="Adaugă imagine">
                        <Camera className="h-3.5 w-3.5" />
                      </button>
                    </div>
                    <p className="text-sm text-slate-500">Mărimea propusă este 512x512 px, nu mai mare de 2.5 MB</p>
                  </div>

                  <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                    <label className="text-sm text-slate-700">
                      Prenume
                      <input className="wm-input mt-1" value={firstName} onChange={(e) => setFirstName(e.target.value)} required />
                    </label>
                    <label className="text-sm text-slate-700">
                      Nume
                      <input className="wm-input mt-1" value={lastName} onChange={(e) => setLastName(e.target.value)} required />
                    </label>
                    <label className="text-sm text-slate-700 md:col-span-2">
                      Email <span className="text-red-500">*</span>
                      <input className="wm-input mt-1" type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
                    </label>
                    <label className="text-sm text-slate-700">
                      Telefon
                      <input className="wm-input mt-1" value={phone} onChange={(e) => setPhone(e.target.value)} />
                    </label>
                    <label className="text-sm text-slate-700">
                      Extensie
                      <input className="wm-input mt-1" value={extension} onChange={(e) => setExtension(e.target.value)} />
                    </label>
                    <label className="text-sm text-slate-700">
                      Tip Utilizator
                      <select className="wm-input mt-1" value={userType} onChange={(e) => setUserType(e.target.value)}>
                        <option value="agency">Agency</option>
                        <option value="client">Client</option>
                      </select>
                    </label>
                    <label className="text-sm text-slate-700">
                      Rol Utilizator
                      <select className="wm-input mt-1" value={userRole} onChange={(e) => setUserRole(e.target.value)}>
                        <option value="admin">Admin</option>
                        <option value="member">Membru</option>
                        <option value="viewer">Viewer</option>
                      </select>
                    </label>
                    <label className="text-sm text-slate-700">
                      Locație
                      <input className="wm-input mt-1" value={location} onChange={(e) => setLocation(e.target.value)} />
                    </label>
                    <label className="text-sm text-slate-700">
                      Sub-cont
                      <select
                        className="wm-input mt-1"
                        value={subaccount}
                        onChange={(e) => {
                          setSubaccount(e.target.value);
                          setSubaccountFieldError("");
                        }}
                        disabled={userType === "agency"}
                      >
                        <option value="">Selectează Sub-cont</option>
                        {subaccountOptions.map((item) => (
                          <option key={item.id} value={String(item.id)}>{item.label || item.name}</option>
                        ))}
                      </select>
                      {subaccountFieldError ? <p className="mt-1 text-xs text-red-600">{subaccountFieldError}</p> : null}
                    </label>
                  </div>

                  {shouldShowModulePermissions ? (
                    <section className="space-y-2 rounded-lg border border-slate-200 bg-slate-50 p-3">
                      <h3 className="text-sm font-semibold text-slate-900">Roluri și Permisiuni</h3>
                      <p className="text-xs text-slate-600">Rolul selectat rămâne baza de acces. Modulele de mai jos restrâng ce vede utilizatorul în sub-account.</p>
                      {moduleCatalogLoading ? <p className="text-xs text-slate-500">Se încarcă modulele...</p> : null}
                      {moduleCatalogError ? <p className="text-xs text-red-600">Nu am putut încărca modulele: {moduleCatalogError}</p> : null}
                      {!moduleCatalogLoading && moduleCatalog.length > 0 ? (
                        <div className="grid grid-cols-1 gap-2 md:grid-cols-2">
                          {moduleCatalog.map((moduleItem) => (
                            <label key={moduleItem.key} className="inline-flex items-center gap-2 rounded border border-slate-200 bg-white px-2 py-1.5 text-sm text-slate-700">
                              <input
                                type="checkbox"
                                className="h-4 w-4 rounded border-slate-300 text-indigo-600"
                                checked={selectedModuleKeys.includes(moduleItem.key)}
                                onChange={() => toggleModule(moduleItem.key)}
                              />
                              {moduleItem.label}
                            </label>
                          ))}
                        </div>
                      ) : null}
                      {moduleFieldError ? <p className="text-xs text-red-600">{moduleFieldError}</p> : null}
                    </section>
                  ) : null}

                  <div>
                    <button type="button" className="text-sm font-medium text-indigo-600 hover:text-indigo-700" onClick={() => setAdvancedOpen((prev) => !prev)}>
                      Setări Avansate
                    </button>
                    {advancedOpen ? (
                      <label className="mt-2 block text-sm text-slate-700">
                        Parolă
                        <input className="wm-input mt-1" type="password" value={password} onChange={(e) => setPassword(e.target.value)} />
                      </label>
                    ) : null}
                  </div>


                  <label className="inline-flex items-center gap-2 text-sm text-slate-700">
                    <input
                      type="checkbox"
                      className="h-4 w-4 rounded border-slate-300 text-indigo-600"
                      checked={autoInviteAfterCreate}
                      onChange={(e) => setAutoInviteAfterCreate(e.target.checked)}
                    />
                    Trimite invitație imediat după creare
                  </label>

                  <div className="flex items-center justify-end gap-2 border-t border-slate-100 pt-3">
                    <button type="button" className="wm-btn-secondary" onClick={() => { resetCreateForm(); setMode("list"); }}>
                      Anulează
                    </button>
                    <button type="submit" className="wm-btn-primary" disabled={saving}>
                      {saving ? <span className="inline-flex items-center gap-2"><Loader2 className="h-4 w-4 animate-spin" /> Se salvează...</span> : "Pasul Următor"}
                    </button>
                  </div>
                </form>
              </div>
            </section>
          )}
        </main>
      </AppShell>
    </ProtectedPage>
  );
}
