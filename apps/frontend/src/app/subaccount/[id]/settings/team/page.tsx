"use client";

import React, { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { ChevronDown, Copy, Mail, Pencil, Plus, Power, RefreshCw, Search, Trash2 } from "lucide-react";
import { useParams } from "next/navigation";

import { AppShell } from "@/components/AppShell";
import { PermissionEditorItem, PermissionsEditor } from "@/components/team/PermissionsEditor";
import { ProtectedPage } from "@/components/ProtectedPage";
import {
  ApiRequestError,
  CreateSubaccountTeamMemberPayload,
  SubaccountTeamMemberItem,
  TeamModuleCatalogItem,
  TeamMembershipDetailItem,
  createSubaccountTeamMember,
  deactivateTeamMember,
  getSubaccountGrantableModules,
  getTeamModuleCatalog,
  getTeamMembershipDetail,
  inviteTeamMember,
  listSubaccountTeamMembers,
  reactivateTeamMember,
  removeTeamMember,
  updateTeamMembership,
} from "@/lib/api";

type TeamUser = {
  id: string;
  membershipId: number | null;
  prenume: string;
  nume: string;
  email: string;
  telefon: string;
  tip: string;
  roleKey: string;
  sourceLabel: string;
  inherited: boolean;
  membershipStatus: "active" | "inactive";
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
type FormTab = "user" | "permissions";

type ModulePermissionOption = {
  key: string;
  label: string;
  order: number;
  scope: "subaccount";
  groupKey: string;
  groupLabel: string;
  parentKey: string | null;
  isContainer: boolean;
  grantable: boolean;
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
    membershipId: Number.isFinite(item.membership_id) ? item.membership_id : null,
    prenume: item.first_name,
    nume: item.last_name,
    email: item.email,
    telefon: item.phone || "-",
    tip: item.role_label,
    roleKey: item.role_key,
    sourceLabel: item.source_label,
    inherited: item.is_inherited,
    membershipStatus: String(item.membership_status || "").trim().toLowerCase() === "inactive" || item.is_active === false ? "inactive" : "active",
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
    if (error.status === 403) return "Permisiuni insuficiente pentru această acțiune.";
    if (error.status === 404) return "Sub-account inexistent.";
    if (error.status === 400) {
      const message = error.message || "Date invalide.";
      if (message.toLowerCase().includes("modul invalid")) return message;
      if (message.toLowerCase().includes("în afara permisiunilor proprii")) return message;
      return message;
    }
  }
  if (error instanceof Error && error.message.trim()) return error.message;
  return "Nu am putut crea utilizatorul.";
}

function getFriendlyInviteError(error: unknown): string {
  if (error instanceof ApiRequestError) {
    if (error.status === 403) return "Nu ai permisiunea să trimiți invitația pentru acest utilizator.";
    if (error.status === 404) return "Membership-ul sau utilizatorul nu a fost găsit.";
    if (error.status === 503) return "Invitațiile sunt indisponibile temporar. Încearcă din nou mai târziu.";
    if (error.message.trim()) return error.message;
  }
  if (error instanceof Error && error.message.trim()) return error.message;
  return "Nu am putut trimite invitația.";
}



function getFriendlyEditError(error: unknown): string {
  if (error instanceof ApiRequestError) {
    if (error.status === 400) return error.message || "Date invalide pentru actualizare";
    if (error.status === 403) return "Permisiuni insuficiente pentru această modificare.";
    if (error.status === 404) return "Membership inexistent sau inaccesibil.";
    if (error.status === 409) return "Acest access este moștenit și nu poate fi editat aici";
    if (error.message.trim()) return error.message;
  }
  if (error instanceof Error && error.message.trim()) return error.message;
  return "Nu am putut actualiza permisiunile.";
}

function getFriendlyLifecycleError(error: unknown): string {
  if (error instanceof ApiRequestError) {
    if (error.status === 403) return "Nu ai permisiuni suficiente pentru această acțiune.";
    if (error.status === 404) return "Membership inexistent sau inaccesibil.";
    if (error.status === 409) return "Acest access este moștenit și nu poate fi modificat aici";
    if (error.message.trim()) return error.message;
  }
  if (error instanceof Error && error.message.trim()) return error.message;
  return "Nu am putut actualiza statusul accesului.";
}

function getFriendlyRemoveError(error: unknown): string {
  if (error instanceof ApiRequestError) {
    if (error.status === 403) return "Nu ai permisiuni suficiente pentru a elimina acest acces.";
    if (error.status === 404) return "Membership inexistent.";
    if (error.status === 409) {
      const normalized = String(error.message || "").toLowerCase();
      if (normalized.includes("propriul membership") || normalized.includes("sesiunea curentă")) {
        return "Nu îți poți elimina accesul curent din această sesiune";
      }
      if (normalized.includes("moștenit")) {
        return "Acest access este moștenit și nu poate fi eliminat aici";
      }
      return error.message || "Acest acces nu poate fi eliminat în acest moment.";
    }
    if (error.message.trim()) return error.message;
  }
  if (error instanceof Error && error.message.trim()) return error.message;
  return "Nu am putut elimina accesul.";
}

function toSubaccountRole(roleKey: string): TeamUserForm["role"] {
  const key = String(roleKey || "").trim().toLowerCase();
  if (key === "subaccount_admin") return "subaccount_admin";
  if (key === "subaccount_viewer") return "subaccount_viewer";
  return "subaccount_user";
}

function hasValidEmail(email: string): boolean {
  return EMAIL_RE.test(String(email || "").trim());
}

function canInviteUser(user: TeamUser): boolean {
  return typeof user.membershipId === "number" && user.membershipId > 0 && hasValidEmail(user.email);
}

function normalizeModuleKey(value: string): string {
  return String(value || "").trim().toLowerCase();
}

function normalizeUniqueModuleKeys(keys: string[]): string[] {
  const out: string[] = [];
  for (const raw of keys) {
    const normalized = normalizeModuleKey(raw);
    if (!normalized) continue;
    if (!out.includes(normalized)) out.push(normalized);
  }
  return out;
}

function normalizeCatalogItems(items: TeamModuleCatalogItem[] | undefined): ModulePermissionOption[] {
  const normalized: ModulePermissionOption[] = [];
  for (const [idx, item] of (items ?? []).entries()) {
    const key = normalizeModuleKey(String(item.key ?? ""));
    if (!key) continue;
    const scopeRaw = String(item.scope ?? "subaccount").trim().toLowerCase();
    if (scopeRaw !== "subaccount") continue;
    if (normalized.some((candidate) => candidate.key === key)) continue;
    const groupKey = normalizeModuleKey(String(item.group_key ?? "")) || "main_nav";
    const groupLabel = String(item.group_label ?? "").trim() || "Main Navigation";
    normalized.push({
      key,
      label: String(item.label ?? "").trim() || key.replaceAll("_", " "),
      order: Number.isFinite(Number(item.order)) ? Number(item.order) : idx + 1,
      scope: "subaccount",
      groupKey,
      groupLabel,
      parentKey: normalizeModuleKey(String(item.parent_key ?? "")) || null,
      isContainer: Boolean(item.is_container),
      grantable: false,
    });
  }
  return normalized.sort((a, b) => a.order - b.order || a.label.localeCompare(b.label));
}

function mergeCatalogWithGrantable(
  catalog: ModulePermissionOption[],
  grantableItems: { key: string; label: string; order: number; grantable: boolean }[] | undefined,
): ModulePermissionOption[] {
  const byKey = new Map<string, ModulePermissionOption>();
  for (const item of catalog) byKey.set(item.key, item);

  for (const grantableItem of grantableItems ?? []) {
    const key = normalizeModuleKey(String(grantableItem.key ?? ""));
    if (!key) continue;
    const current = byKey.get(key);
    if (!current) continue;
    byKey.set(key, { ...current, grantable: Boolean(grantableItem.grantable) });
  }

  return Array.from(byKey.values()).sort((a, b) => a.order - b.order || a.label.localeCompare(b.label));
}

function applySettingsConsistency(keys: string[], options: ModulePermissionOption[]): string[] {
  const selected = new Set(normalizeUniqueModuleKeys(keys));
  const settingsItem = options.find((item) => item.key === "settings");
  if (!settingsItem) return Array.from(selected);

  const settingsChildren = options
    .filter((item) => item.parentKey === "settings")
    .map((item) => item.key);
  if (settingsChildren.length === 0) return Array.from(selected);

  if (!selected.has("settings")) {
    settingsChildren.forEach((child) => selected.delete(child));
    return Array.from(selected);
  }

  const hasAnyChildEnabled = settingsChildren.some((child) => selected.has(child));
  if (!hasAnyChildEnabled) selected.delete("settings");
  return Array.from(selected);
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
  const [viewMode, setViewMode] = useState<"list" | "create" | "edit">("list");

  const [form, setForm] = useState<TeamUserForm>(defaultForm());
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [inviteError, setInviteError] = useState<string | null>(null);
  const [lifecycleError, setLifecycleError] = useState<string | null>(null);
  const [removeError, setRemoveError] = useState<string | null>(null);
  const [invitingMembershipId, setInvitingMembershipId] = useState<number | null>(null);
  const [lifecycleLoadingByMembership, setLifecycleLoadingByMembership] = useState<Record<number, boolean>>({});
  const [removeLoadingByMembership, setRemoveLoadingByMembership] = useState<Record<number, boolean>>({});
  const [moduleOptions, setModuleOptions] = useState<ModulePermissionOption[]>([]);
  const [selectedModuleKeys, setSelectedModuleKeys] = useState<string[]>([]);
  const [isLoadingModules, setIsLoadingModules] = useState(false);
  const [moduleLoadError, setModuleLoadError] = useState<string | null>(null);
  const [moduleNotice, setModuleNotice] = useState<string | null>(null);
  const [editingMembershipId, setEditingMembershipId] = useState<number | null>(null);
  const [isLoadingEditDetail, setIsLoadingEditDetail] = useState(false);
  const [editInheritedLocked, setEditInheritedLocked] = useState(false);
  const [editUnsafeGrantGap, setEditUnsafeGrantGap] = useState(false);
  const [editOriginal, setEditOriginal] = useState<{ role: TeamUserForm["role"]; moduleKeys: string[] } | null>(null);
  const [activeFormTab, setActiveFormTab] = useState<FormTab>("user");

  const moduleOptionByKey = useMemo(() => {
    const out = new Map<string, ModulePermissionOption>();
    for (const item of moduleOptions) out.set(item.key, item);
    return out;
  }, [moduleOptions]);
  const grantableModuleKeys = useMemo(
    () => moduleOptions.filter((item) => item.grantable).map((item) => item.key),
    [moduleOptions],
  );
  const permissionEditorItems = useMemo<PermissionEditorItem[]>(
    () =>
      moduleOptions.map((item) => {
        const isReadOnlyGapKey = editUnsafeGrantGap && selectedModuleKeys.includes(item.key) && !item.grantable;
        const disabledReason = !item.grantable
          ? isReadOnlyGapKey
            ? "Permisiune existentă, dar ne-editabilă pentru actorul curent."
            : "Nu poate fi acordat din grant ceiling-ul tău curent."
          : null;
        return {
          key: item.key,
          label: item.label,
          order: item.order,
          groupKey: item.groupKey,
          groupLabel: item.groupLabel,
          parentKey: item.parentKey,
          isContainer: item.isContainer,
          disabledReason,
        };
      }),
    [moduleOptions, editUnsafeGrantGap, selectedModuleKeys],
  );

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

  async function onInvite(user: TeamUser) {
    if (!canInviteUser(user) || user.membershipId === null) {
      setInviteError("Invitația nu poate fi trimisă pentru acest utilizator.");
      return;
    }

    setInviteError(null);
    setLifecycleError(null);
    setRemoveError(null);
    setInvitingMembershipId(user.membershipId);
    try {
      const response = await inviteTeamMember(user.membershipId);
      showToast(response.message || "Invitația a fost trimisă");
    } catch (error) {
      setInviteError(getFriendlyInviteError(error));
    } finally {
      setInvitingMembershipId((current) => (current === user.membershipId ? null : current));
    }
  }

  async function onToggleLifecycle(user: TeamUser) {
    if (user.membershipId === null) {
      setLifecycleError("Membership inexistent sau inaccesibil.");
      return;
    }
    if (user.inherited) {
      setLifecycleError("Acest access este moștenit și nu poate fi modificat aici");
      return;
    }

    if (user.membershipStatus === "active") {
      const confirmed = window.confirm("Confirmi dezactivarea accesului pentru acest membership?");
      if (!confirmed) return;
    }

    setInviteError(null);
    setLifecycleError(null);
    setRemoveError(null);
    setLifecycleLoadingByMembership((prev) => ({ ...prev, [user.membershipId as number]: true }));
    try {
      if (user.membershipStatus === "active") {
        const response = await deactivateTeamMember(user.membershipId);
        showToast(response.message || "Accesul a fost dezactivat pentru sesiunile noi și pentru verificările bazate pe datele curente.");
      } else {
        const response = await reactivateTeamMember(user.membershipId);
        showToast(response.message || "Accesul a fost reactivat");
      }
      await loadMembers();
    } catch (error) {
      setLifecycleError(getFriendlyLifecycleError(error));
    } finally {
      setLifecycleLoadingByMembership((prev) => {
        const next = { ...prev };
        delete next[user.membershipId as number];
        return next;
      });
    }
  }

  async function onRemoveAccess(user: TeamUser) {
    if (user.membershipId === null) {
      setRemoveError("Membership inexistent sau inaccesibil.");
      return;
    }
    if (user.inherited) {
      setRemoveError("Acest access este moștenit și nu poate fi eliminat aici");
      return;
    }

    const confirmed = window.confirm(
      "Sigur vrei să elimini acest acces? Această acțiune șterge doar access grant-ul curent, nu utilizatorul global.",
    );
    if (!confirmed) return;

    setInviteError(null);
    setLifecycleError(null);
    setRemoveError(null);
    setRemoveLoadingByMembership((prev) => ({ ...prev, [user.membershipId as number]: true }));
    try {
      const response = await removeTeamMember(user.membershipId);
      showToast(response.message || "Accesul a fost eliminat");
      await loadMembers();
    } catch (error) {
      if (error instanceof ApiRequestError && error.status === 404) {
        showToast(error.message || "Membership inexistent");
        await loadMembers();
      } else {
        setRemoveError(getFriendlyRemoveError(error));
      }
    } finally {
      setRemoveLoadingByMembership((prev) => {
        const next = { ...prev };
        delete next[user.membershipId as number];
        return next;
      });
    }
  }

  async function loadScopedModuleOptions(subaccountId: number): Promise<ModulePermissionOption[]> {
    const [catalogPayload, grantablePayload] = await Promise.all([
      getTeamModuleCatalog("subaccount"),
      getSubaccountGrantableModules(subaccountId),
    ]);
    const catalog = normalizeCatalogItems(catalogPayload.items);
    return mergeCatalogWithGrantable(catalog, grantablePayload.items);
  }

  async function openCreateForm() {
    setForm(defaultForm());
    setErrors({});
    setShowAdvanced(false);
    setViewMode("create");
    setActiveFormTab("user");
    if (parsedSubaccountId === null) {
      setModuleOptions([]);
      setSelectedModuleKeys([]);
      setModuleLoadError("ID de sub-account invalid.");
      return;
    }

    setIsLoadingModules(true);
    setModuleLoadError(null);
    setModuleNotice(null);
    try {
      const options = await loadScopedModuleOptions(parsedSubaccountId);
      const defaultSelection = applySettingsConsistency(
        options.filter((item) => item.grantable).map((item) => item.key),
        options,
      );
      setModuleOptions(options);
      setSelectedModuleKeys(defaultSelection);
    } catch (error) {
      setModuleOptions([]);
      setSelectedModuleKeys([]);
      setModuleLoadError(getFriendlyCreateError(error));
    } finally {
      setIsLoadingModules(false);
    }
  }

  function closeForm() {
    setViewMode("list");
    setErrors({});
    setShowAdvanced(false);
    setModuleLoadError(null);
    setModuleNotice(null);
    setLifecycleError(null);
    setRemoveError(null);
    setIsLoadingModules(false);
    setModuleNotice(null);
    setEditingMembershipId(null);
    setIsLoadingEditDetail(false);
    setEditInheritedLocked(false);
    setEditUnsafeGrantGap(false);
    setEditOriginal(null);
    setActiveFormTab("user");
  }

  function validate(): Record<string, string> {
    const next: Record<string, string> = {};
    if (viewMode === "create") {
      if (form.prenume.trim() === "") next.prenume = "Prenumele este obligatoriu.";
      if (form.nume.trim() === "") next.nume = "Numele este obligatoriu.";
      if (form.email.trim() === "") next.email = "Email-ul este obligatoriu.";
      else if (!EMAIL_RE.test(form.email.trim())) next.email = "Introdu o adresă de email validă.";
      if (form.extensie.trim() !== "" && !/^\d+$/.test(form.extensie.trim())) next.extensie = "Extensia trebuie să fie numerică.";
    }
    const selectedGrantable = normalizeUniqueModuleKeys(selectedModuleKeys).filter((key) => grantableModuleKeys.includes(key));
    if (grantableModuleKeys.length === 0) next.module_keys = "Nu poți acorda permisiuni de navigare pentru acest sub-account.";
    else if (selectedGrantable.length === 0) next.module_keys = "Selectează cel puțin o permisiune de navigare.";
    if (viewMode === "edit" && editUnsafeGrantGap) next.module_keys = "Acest utilizator are permisiuni care depășesc accesul tău curent. Contactează un administrator pentru modificare.";

    return next;
  }

  async function openEditForm(user: TeamUser) {
    if (parsedSubaccountId === null || user.membershipId === null) {
      setLoadError("Membership inexistent sau sub-account invalid.");
      return;
    }

    setErrors({});
    setModuleLoadError(null);
    setModuleNotice(null);
    setViewMode("edit");
    setActiveFormTab("user");
    setEditingMembershipId(user.membershipId);
    setIsLoadingEditDetail(true);
    setEditInheritedLocked(false);
    setEditUnsafeGrantGap(false);
    try {
      const [detailPayload, options] = await Promise.all([
        getTeamMembershipDetail(user.membershipId),
        loadScopedModuleOptions(parsedSubaccountId),
      ]);
      const detail: TeamMembershipDetailItem = detailPayload.item;
      const detailKeys = normalizeUniqueModuleKeys((detail.module_keys ?? []).map((key) => String(key)));
      const grantableSet = new Set(options.filter((item) => item.grantable).map((item) => item.key));
      const hasGap = detailKeys.some((key) => !grantableSet.has(key));
      const coherentDetailKeys = applySettingsConsistency(detailKeys, options);

      setModuleOptions(options);
      setSelectedModuleKeys(coherentDetailKeys);
      setForm({
        prenume: detail.first_name,
        nume: detail.last_name,
        email: detail.email,
        telefon: detail.phone,
        extensie: detail.extension,
        parola: "",
        role: toSubaccountRole(detail.role_key),
      });
      setEditOriginal({ role: toSubaccountRole(detail.role_key), moduleKeys: [...coherentDetailKeys].sort() });
      setEditInheritedLocked(Boolean(detail.is_inherited));
      setEditUnsafeGrantGap(hasGap);
      if (detail.is_inherited) {
        setModuleNotice("Acest access este moștenit și nu poate fi editat aici");
      } else if (hasGap) {
        setModuleNotice("Acest utilizator are permisiuni care depășesc accesul tău curent. Contactează un administrator pentru modificare.");
      }
      setShowAdvanced(false);
    } catch (error) {
      closeForm();
      setLoadError(getFriendlyEditError(error));
    } finally {
      setIsLoadingEditDetail(false);
    }
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
      const selectedGrantable = normalizeUniqueModuleKeys(selectedModuleKeys)
        .filter((key) => moduleOptionByKey.has(key))
        .filter((key) => grantableModuleKeys.includes(key));
      if (viewMode === "create") {
        const payload: CreateSubaccountTeamMemberPayload = {
          first_name: form.prenume.trim(),
          last_name: form.nume.trim(),
          email: form.email.trim(),
          phone: form.telefon.trim(),
          extension: form.extensie.trim(),
          user_role: form.role,
          module_keys: selectedGrantable,
        };
        if (form.parola.trim()) payload.password = form.parola;

        await createSubaccountTeamMember(parsedSubaccountId, payload);
        closeForm();
        showToast("Utilizator adăugat.");
        await loadMembers();
      } else if (viewMode === "edit" && editingMembershipId !== null) {
        const patchPayload: { user_role: TeamUserForm["role"]; module_keys: string[] } = {
          user_role: form.role,
          module_keys: selectedGrantable,
        };
        await updateTeamMembership(editingMembershipId, patchPayload);
        closeForm();
        showToast("Permisiunile au fost actualizate");
        await loadMembers();
      }
    } catch (error) {
      if (viewMode === "edit") {
        let message = getFriendlyEditError(error);
        if (error instanceof ApiRequestError && error.status === 400) {
          const normalized = String(error.message || "").toLowerCase();
          if (normalized.includes("cheie de navigare invalid") || normalized.includes("modul invalid")) {
            message = "Permisiunile selectate nu sunt valide pentru scope-ul sub-account.";
          } else if (normalized.includes("în afara permisiunilor proprii")) {
            message = "Nu poți acorda permisiuni peste grant-ceiling-ul tău curent.";
          }
        }
        setModuleLoadError(message);
        if (error instanceof ApiRequestError && error.status === 409) setEditInheritedLocked(true);
        showToast(message);
      } else {
        showToast(getFriendlyCreateError(error));
      }
    } finally {
      setIsSubmitting(false);
    }
  }

  const isInvalidSubaccount = parsedSubaccountId === null;

  const isSaveDisabled = useMemo(() => {
    if (isSubmitting || isInvalidSubaccount) return true;
    if (viewMode === "create") return false;
    if (viewMode !== "edit") return true;
    if (isLoadingEditDetail || editInheritedLocked || editUnsafeGrantGap || editingMembershipId === null || !editOriginal) return true;
    const currentKeys = [...normalizeUniqueModuleKeys(selectedModuleKeys).filter((key) => grantableModuleKeys.includes(key))].sort();
    const originalKeys = [...normalizeUniqueModuleKeys(editOriginal.moduleKeys).filter((key) => grantableModuleKeys.includes(key))].sort();
    const sameModules = JSON.stringify(currentKeys) === JSON.stringify(originalKeys);
    const sameRole = editOriginal.role === form.role;
    return sameModules && sameRole;
  }, [isSubmitting, isInvalidSubaccount, viewMode, isLoadingEditDetail, editInheritedLocked, editUnsafeGrantGap, editingMembershipId, editOriginal, selectedModuleKeys, grantableModuleKeys, form.role]);

  function toggleModuleKey(moduleKey: string, grantable: boolean) {
    if (!grantable) return;
    setSelectedModuleKeys((prev) => {
      const key = normalizeModuleKey(moduleKey);
      const selected = new Set(normalizeUniqueModuleKeys(prev));
      const settingsChildren = moduleOptions
        .filter((item) => item.parentKey === "settings")
        .map((item) => item.key);
      const isSettingsParent = key === "settings";
      const isSettingsChild = moduleOptions.some((item) => item.parentKey === "settings" && item.key === key);
      const enabled = selected.has(key);

      if (isSettingsParent) {
        if (enabled) {
          selected.delete("settings");
          settingsChildren.forEach((child) => selected.delete(child));
        } else {
          selected.add("settings");
          settingsChildren
            .filter((child) => moduleOptionByKey.get(child)?.grantable)
            .forEach((child) => selected.add(child));
        }
      } else if (isSettingsChild) {
        if (enabled) {
          selected.delete(key);
        } else {
          selected.add(key);
          selected.add("settings");
        }
      } else if (enabled) {
        selected.delete(key);
      } else {
        selected.add(key);
      }
      return applySettingsConsistency(Array.from(selected), moduleOptions);
    });
  }

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
                    <button type="button" className="wm-btn-primary inline-flex items-center gap-2" onClick={() => { void openCreateForm(); }} disabled={isInvalidSubaccount}>
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
                {inviteError ? <p className="mt-4 rounded-md border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">{inviteError}</p> : null}
                {lifecycleError ? <p className="mt-4 rounded-md border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">{lifecycleError}</p> : null}
                {removeError ? <p className="mt-4 rounded-md border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">{removeError}</p> : null}
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
                            <th className="border-b border-slate-200 px-3 py-2">Status</th>
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
                                {user.membershipStatus === "active" ? (
                                  <span className="inline-flex rounded-full bg-emerald-50 px-2 py-1 text-xs font-semibold text-emerald-700">Activ</span>
                                ) : (
                                  <span className="inline-flex rounded-full bg-slate-100 px-2 py-1 text-xs font-semibold text-slate-700">Inactiv</span>
                                )}
                              </td>
                              <td className="border-b border-slate-100 px-3 py-3">
                                <div className="flex items-center gap-2 text-slate-500">
                                  <button
                                    type="button"
                                    className="inline-flex items-center gap-1 rounded border border-slate-200 px-2 py-1 text-xs text-slate-700 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
                                    title={canInviteUser(user) ? "Trimite invitație" : "Invitația nu este disponibilă pentru acest rând"}
                                    disabled={!canInviteUser(user) || invitingMembershipId === user.membershipId}
                                    onClick={() => { void onInvite(user); }}
                                  >
                                    <Mail className="h-3.5 w-3.5" />
                                    {invitingMembershipId === user.membershipId ? "Se trimite..." : "Trimite invitație"}
                                  </button>
                                  <button
                                    type="button"
                                    className="rounded p-1.5 text-slate-600 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-40"
                                    title={user.membershipId === null ? "Membership inexistent sau inaccesibil" : "Editează"}
                                    aria-label="Editează"
                                    disabled={user.membershipId === null}
                                    onClick={() => { void openEditForm(user); }}
                                  >
                                    <Pencil className="h-4 w-4" />
                                  </button>
                                  {(() => {
                                    const lifecycleLoading = user.membershipId !== null && Boolean(lifecycleLoadingByMembership[user.membershipId]);
                                    return (
                                      <button
                                        type="button"
                                        className="inline-flex items-center gap-1 rounded border border-slate-200 px-2 py-1 text-xs text-slate-700 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
                                        title={user.inherited ? "Acest access este moștenit și nu poate fi modificat aici" : user.membershipStatus === "active" ? "Dezactivează" : "Reactivează"}
                                        aria-label={user.membershipStatus === "active" ? "Dezactivează" : "Reactivează"}
                                        disabled={user.membershipId === null || lifecycleLoading || user.inherited}
                                        onClick={() => { void onToggleLifecycle(user); }}
                                      >
                                        {lifecycleLoading ? (
                                          "Se procesează..."
                                        ) : user.membershipStatus === "active" ? (
                                          <><Power className="h-3.5 w-3.5" /> Dezactivează</>
                                        ) : (
                                          <><RefreshCw className="h-3.5 w-3.5" /> Reactivează</>
                                        )}
                                      </button>
                                    );
                                  })()}
                                  {(() => {
                                    const removeLoading = user.membershipId !== null && Boolean(removeLoadingByMembership[user.membershipId]);
                                    return (
                                      <button
                                        type="button"
                                        className="inline-flex items-center gap-1 rounded border border-rose-200 px-2 py-1 text-xs text-rose-700 transition hover:bg-rose-50 disabled:cursor-not-allowed disabled:opacity-50"
                                        title={user.inherited ? "Acest access este moștenit și nu poate fi eliminat aici" : "Elimină accesul"}
                                        aria-label="Elimină accesul"
                                        disabled={user.membershipId === null || removeLoading || user.inherited}
                                        onClick={() => { void onRemoveAccess(user); }}
                                      >
                                        {removeLoading ? "Se elimină..." : <><Trash2 className="h-3.5 w-3.5" /> Elimină accesul</>}
                                      </button>
                                    );
                                  })()}
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
                <p className="mt-2 text-sm text-slate-600">{viewMode === "edit" ? "Editează permisiunile și statusul accesului pentru membership-ul selectat." : "Adaugă un utilizator în echipa sub-account-ului."}</p>

                <div className="mt-5 grid grid-cols-1 gap-6 xl:grid-cols-[260px_1fr]">
                  <aside className="space-y-2">
                    <button
                      type="button"
                      className={[
                        "w-full rounded-md px-3 py-2 text-left text-sm",
                        activeFormTab === "user" ? "bg-indigo-50 font-semibold text-indigo-700" : "text-slate-700 hover:bg-slate-50",
                      ].join(" ")}
                      onClick={() => setActiveFormTab("user")}
                    >
                      Informații Utilizator
                    </button>
                    <button
                      type="button"
                      className={[
                        "w-full rounded-md px-3 py-2 text-left text-sm",
                        activeFormTab === "permissions" ? "bg-indigo-50 font-semibold text-indigo-700" : "text-slate-700 hover:bg-slate-50",
                      ].join(" ")}
                      onClick={() => setActiveFormTab("permissions")}
                    >
                      Roluri și Permisiuni
                    </button>
                  </aside>

                  <form noValidate onSubmit={(event) => { void submit(event); }} className="space-y-5">
                    {activeFormTab === "user" ? (
                      <>
                        <div className="rounded-lg border border-slate-200 p-4">
                          <h2 className="text-base font-semibold text-slate-900">Informații Utilizator</h2>
                          {viewMode === "edit" && editingMembershipId !== null ? (
                            <p className="mt-2 rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-700">
                              Status membership curent: <span className="font-semibold">{users.find((item) => item.membershipId === editingMembershipId)?.membershipStatus === "inactive" ? "Inactiv" : "Activ"}</span>
                            </p>
                          ) : null}
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
                                <input placeholder="Prenume" className="wm-input mt-1" value={form.prenume} onChange={(e) => setForm((prev) => ({ ...prev, prenume: e.target.value }))} disabled={viewMode === "edit"} />
                                {errors.prenume ? <p className="mt-1 text-xs text-red-600">{errors.prenume}</p> : null}
                              </label>

                              <label className="text-sm text-slate-700">
                                Nume <span className="text-red-500">*</span>
                                <input placeholder="Nume" className="wm-input mt-1" value={form.nume} onChange={(e) => setForm((prev) => ({ ...prev, nume: e.target.value }))} disabled={viewMode === "edit"} />
                                {errors.nume ? <p className="mt-1 text-xs text-red-600">{errors.nume}</p> : null}
                              </label>

                              <label className="text-sm text-slate-700 md:col-span-2">
                                Email <span className="text-red-500">*</span>
                                <input type="email" placeholder="Email" className="wm-input mt-1" value={form.email} onChange={(e) => setForm((prev) => ({ ...prev, email: e.target.value }))} disabled={viewMode === "edit"} />
                                {errors.email ? <p className="mt-1 text-xs text-red-600">{errors.email}</p> : null}
                              </label>

                              <label className="text-sm text-slate-700">
                                Telefon
                                <input type="tel" placeholder="Telefon" className="wm-input mt-1" value={form.telefon} onChange={(e) => setForm((prev) => ({ ...prev, telefon: e.target.value }))} disabled={viewMode === "edit"} />
                              </label>

                              <label className="text-sm text-slate-700">
                                Extensie
                                <input inputMode="numeric" placeholder="Extensie" className="wm-input mt-1" value={form.extensie} onChange={(e) => setForm((prev) => ({ ...prev, extensie: e.target.value }))} disabled={viewMode === "edit"} />
                                {errors.extensie ? <p className="mt-1 text-xs text-red-600">{errors.extensie}</p> : null}
                              </label>
                            </div>
                          </div>
                        </div>

                        {viewMode === "create" ? (
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
                        ) : null}
                      </>
                    ) : (
                      <>
                        <div className="rounded-lg border border-slate-200 p-4">
                          <label className="text-sm text-slate-700">
                            Rol utilizator
                            <select className="wm-input mt-1" value={form.role} onChange={(e) => setForm((prev) => ({ ...prev, role: e.target.value as TeamUserForm["role"] }))} disabled={editInheritedLocked || isLoadingEditDetail}>
                              <option value="subaccount_admin">Subaccount Admin</option>
                              <option value="subaccount_user">Subaccount User</option>
                              <option value="subaccount_viewer">Subaccount Viewer</option>
                            </select>
                          </label>
                        </div>

                        <PermissionsEditor
                          scope="subaccount"
                          items={permissionEditorItems}
                          selectedKeys={selectedModuleKeys}
                          onToggle={(key) => {
                            const item = moduleOptionByKey.get(normalizeModuleKey(key));
                            toggleModuleKey(key, Boolean(item?.grantable));
                          }}
                          loading={isLoadingModules}
                          loadError={moduleLoadError}
                          fieldError={errors.module_keys}
                          readOnly={editInheritedLocked}
                          summaryHint="Poți acorda doar cheile de navigare pe care le ai deja în acest sub-account (grant ceiling)."
                          getItemAriaLabel={(item) => `Permisiune modul ${item.label}`}
                          getItemDisabled={(item) => {
                            const source = moduleOptionByKey.get(item.key);
                            const isReadOnlyGapKey = editUnsafeGrantGap && selectedModuleKeys.includes(item.key) && !source?.grantable;
                            return !source?.grantable || isReadOnlyGapKey || editInheritedLocked;
                          }}
                        />
                        {moduleNotice ? <p className="mt-3 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-700">{moduleNotice}</p> : null}
                      </>
                    )}

                    <footer className="flex justify-end gap-2 border-t border-slate-200 pt-4">
                      <button type="button" className="wm-btn-secondary" onClick={closeForm}>Anulează</button>
                      <button type="submit" className="wm-btn-primary" disabled={isSaveDisabled}>{isSubmitting ? "Se salvează..." : viewMode === "edit" ? "Salvează" : "Înainte"}</button>
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
