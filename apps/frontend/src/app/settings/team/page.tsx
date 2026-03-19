"use client";

import React, { FormEvent, useEffect, useMemo, useState } from "react";
import { Camera, ChevronLeft, Loader2, Pencil, Power, RefreshCw, Search, Trash2, UserCircle2 } from "lucide-react";

import { AppShell } from "@/components/AppShell";
import { PermissionEditorItem, PermissionsEditor } from "@/components/team/PermissionsEditor";
import { ProtectedPage } from "@/components/ProtectedPage";
import {
  ApiRequestError,
  TeamMembershipDetailItem,
  TeamModuleCatalogItem,
  apiRequest,
  deactivateTeamMember,
  getTeamMembershipDetail,
  getTeamModuleCatalog,
  inviteTeamMember,
  reactivateTeamMember,
  removeTeamMember,
  updateTeamMembership,
} from "@/lib/api";

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
  membership_status?: "active" | "inactive" | string;
  is_inherited?: boolean;
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
  scope: "agency" | "subaccount";
  group_key: string;
  group_label: string;
  parent_key?: string | null;
  is_container: boolean;
};

type CatalogScope = "agency" | "subaccount";
type FormTab = "identity" | "permissions";
const PAGE_SIZE = 10;

function initials(firstName: string, lastName: string) {
  const a = firstName.trim().charAt(0).toUpperCase();
  const b = lastName.trim().charAt(0).toUpperCase();
  return `${a || "?"}${b || "?"}`;
}


function roleValueFromKey(roleKey: string): "admin" | "member" | "viewer" {
  const normalized = String(roleKey || "").trim().toLowerCase();
  if (normalized.endsWith("_admin")) return "admin";
  if (normalized.endsWith("_viewer")) return "viewer";
  return "member";
}

function roleKeyFromMode(userType: string, userRole: string): string {
  const type = String(userType || "").trim().toLowerCase();
  const role = String(userRole || "").trim().toLowerCase();
  if (type === "agency") {
    if (role === "admin") return "agency_admin";
    if (role === "viewer") return "agency_viewer";
    return "agency_member";
  }
  if (role === "admin") return "subaccount_admin";
  if (role === "viewer") return "subaccount_viewer";
  return "subaccount_user";
}

function activeScopeFromUserType(userType: string): CatalogScope {
  return userType === "agency" ? "agency" : "subaccount";
}

function normalizeCatalogItems(items: TeamModuleCatalogItem[] | undefined, scope: CatalogScope): ModuleCatalogItem[] {
  return (items ?? [])
    .map((item) => ({
      key: String(item.key ?? "").trim().toLowerCase(),
      label: String(item.label ?? "").trim() || String(item.key ?? "").trim(),
      order: Number(item.order ?? 0),
      scope: scope,
      group_key: String(item.group_key ?? "").trim().toLowerCase() || "main_nav",
      group_label: String(item.group_label ?? "").trim() || "Main Navigation",
      parent_key: String(item.parent_key ?? "").trim().toLowerCase() || null,
      is_container: Boolean(item.is_container),
    }))
    .filter((item) => item.key !== "")
    .sort((a, b) => a.order - b.order || a.label.localeCompare(b.label));
}

function normalizeSelectedKeys(keys: string[]): string[] {
  const out: string[] = [];
  for (const key of keys) {
    const normalized = String(key || "").trim().toLowerCase();
    if (normalized && !out.includes(normalized)) out.push(normalized);
  }
  return out;
}

export default function SettingsTeamPage() {
  const [mode, setMode] = useState<"list" | "create" | "edit">("list");

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
  const [moduleCatalogByScope, setModuleCatalogByScope] = useState<Record<CatalogScope, ModuleCatalogItem[]>>({
    agency: [],
    subaccount: [],
  });
  const [moduleCatalogLoading, setModuleCatalogLoading] = useState(false);
  const [moduleCatalogError, setModuleCatalogError] = useState("");

  const [advancedOpen, setAdvancedOpen] = useState(false);
  const [activeFormTab, setActiveFormTab] = useState<FormTab>("identity");
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
  const [lifecycleLoadingByMembership, setLifecycleLoadingByMembership] = useState<Record<number, boolean>>({});
  const [removeLoadingByMembership, setRemoveLoadingByMembership] = useState<Record<number, boolean>>({});
  const [editingMembershipId, setEditingMembershipId] = useState<number | null>(null);
  const [loadingEditDetail, setLoadingEditDetail] = useState(false);
  const [editLockedInherited, setEditLockedInherited] = useState(false);
  const [editOriginal, setEditOriginal] = useState<{ userRole: string; moduleKeys: string[] } | null>(null);
  const activeScope = activeScopeFromUserType(userType);
  const activeCatalog = moduleCatalogByScope[activeScope];

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

  async function loadModuleCatalog(scope: CatalogScope) {
    setModuleCatalogLoading(true);
    setModuleCatalogError("");
    try {
      const data = await getTeamModuleCatalog(scope);
      const normalized = normalizeCatalogItems(data.items, scope);
      setModuleCatalogByScope((prev) => ({ ...prev, [scope]: normalized }));
    } catch (err) {
      setModuleCatalogByScope((prev) => ({ ...prev, [scope]: [] }));
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
    void loadModuleCatalog("agency");
    void loadModuleCatalog("subaccount");
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
    }
    setModuleFieldError("");
    if (mode === "create") {
      setSelectedModuleKeys(activeCatalog.map((item) => item.key));
    }
  }, [userType, mode, activeCatalog]);

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
    setSelectedModuleKeys(moduleCatalogByScope.agency.map((item) => item.key));
    setPassword("");
    setAutoInviteAfterCreate(false);
    setAdvancedOpen(false);
    setEditingMembershipId(null);
    setEditOriginal(null);
    setEditLockedInherited(false);
    setActiveFormTab("identity");
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

  function normalizeMembershipStatus(member: TeamMember): "active" | "inactive" {
    const status = String(member.membership_status || "active").trim().toLowerCase();
    return status === "inactive" ? "inactive" : "active";
  }

  function lifecycleErrorMessage(error: unknown): string {
    if (error instanceof ApiRequestError) {
      if (error.status === 403) return "Nu ai permisiuni suficiente pentru această acțiune";
      if (error.status === 404) return "Membership inexistent sau inaccesibil";
      if (error.status === 409) return "Acest access este moștenit și nu poate fi modificat aici";
      return error.message || "Nu am putut actualiza statusul membership-ului";
    }
    return error instanceof Error ? error.message : "Nu am putut actualiza statusul membership-ului";
  }

  function removeMembershipErrorMessage(error: unknown): string {
    if (error instanceof ApiRequestError) {
      if (error.status === 403) return "Nu ai permisiuni suficiente pentru a elimina acest acces";
      if (error.status === 404) return "Membership inexistent";
      if (error.status === 409) {
        const normalized = String(error.message || "").toLowerCase();
        if (normalized.includes("propriul membership") || normalized.includes("sesiunea curentă")) {
          return "Nu îți poți elimina accesul curent din această sesiune";
        }
        if (normalized.includes("moștenit")) {
          return "Acest acces este moștenit și nu poate fi eliminat aici";
        }
        return error.message || "Acest acces nu poate fi eliminat în acest moment";
      }
      return error.message || "Nu am putut elimina accesul";
    }
    return error instanceof Error ? error.message : "Nu am putut elimina accesul";
  }

  async function onRemoveMembership(member: TeamMember) {
    const membershipId = getMembershipId(member);
    if (membershipId === null) {
      setErrorMessage("Membership invalid pentru acțiunea selectată.");
      return;
    }

    const confirmed = window.confirm(
      "Sigur vrei să elimini acest acces? Această acțiune șterge doar access grant-ul curent, nu utilizatorul global.",
    );
    if (!confirmed) return;

    setErrorMessage("");
    setRemoveLoadingByMembership((prev) => ({ ...prev, [membershipId]: true }));
    try {
      const response = await removeTeamMember(membershipId);
      showToast(response.message || "Accesul a fost eliminat");
      await loadMembers();
    } catch (error) {
      if (error instanceof ApiRequestError && error.status === 404) {
        showToast(error.message || "Membership inexistent");
        await loadMembers();
      } else {
        setErrorMessage(removeMembershipErrorMessage(error));
      }
    } finally {
      setRemoveLoadingByMembership((prev) => {
        const next = { ...prev };
        delete next[membershipId];
        return next;
      });
    }
  }

  async function onToggleMembershipLifecycle(member: TeamMember) {
    const membershipId = getMembershipId(member);
    if (membershipId === null) {
      setErrorMessage("Membership invalid pentru acțiunea selectată.");
      return;
    }

    const currentStatus = normalizeMembershipStatus(member);
    if (currentStatus === "active") {
      const confirmed = window.confirm("Confirmi dezactivarea accesului pentru acest membership?");
      if (!confirmed) return;
    }

    setErrorMessage("");
    setLifecycleLoadingByMembership((prev) => ({ ...prev, [membershipId]: true }));
    try {
      if (currentStatus === "active") {
        const response = await deactivateTeamMember(membershipId);
        showToast(response.message || "Accesul a fost dezactivat pentru sesiunile noi și pentru verificările bazate pe datele curente.");
      } else {
        const response = await reactivateTeamMember(membershipId);
        showToast(response.message || "Accesul a fost reactivat.");
      }
      await loadMembers();
    } catch (error) {
      setErrorMessage(lifecycleErrorMessage(error));
    } finally {
      setLifecycleLoadingByMembership((prev) => {
        const next = { ...prev };
        delete next[membershipId];
        return next;
      });
    }
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

  function editErrorMessage(error: unknown): string {
    if (error instanceof ApiRequestError) {
      if (error.status === 400) return error.message || "Date invalide pentru actualizare";
      if (error.status === 403) return "Nu ai permisiuni suficiente pentru a edita acest membership";
      if (error.status === 404) return "Membership inexistent sau inaccesibil";
      if (error.status === 409) return "Acest access este moștenit și nu poate fi editat aici";
      return error.message || "Nu am putut actualiza membership-ul";
    }
    return error instanceof Error ? error.message : "Nu am putut actualiza membership-ul";
  }

  async function openEditForm(member: TeamMember) {
    const membershipId = getMembershipId(member);
    if (membershipId === null) {
      setErrorMessage("Rândul selectat nu are membership_id valid pentru editare.");
      return;
    }

    setErrorMessage("");
    setSaving(false);
    setLoadingEditDetail(true);
    setMode("edit");
    setActiveFormTab("identity");
    setEditingMembershipId(membershipId);
    setModuleFieldError("");
    setSubaccountFieldError("");
    try {
      const payload = await getTeamMembershipDetail(membershipId);
      const detail: TeamMembershipDetailItem = payload.item;
      setFirstName(detail.first_name || "");
      setLastName(detail.last_name || "");
      setEmail(detail.email || "");
      setPhone(detail.phone || "");
      setExtension(detail.extension || "");
      setLocation("România");
      setSubaccount(detail.subaccount_id ? String(detail.subaccount_id) : "");
      const scopeFromDetail: CatalogScope = detail.scope_type === "subaccount" ? "subaccount" : "agency";
      setUserType(scopeFromDetail === "subaccount" ? "client" : "agency");
      setUserRole(roleValueFromKey(detail.role_key));
      const catalogForScope = moduleCatalogByScope[scopeFromDetail];
      if (catalogForScope.length === 0) {
        void loadModuleCatalog(scopeFromDetail);
      }
      const normalizedKeys = normalizeSelectedKeys((detail.module_keys ?? []).map((key) => String(key)));
      const filteredKeys = normalizeSelectedKeys(
        normalizedKeys.filter((key) => catalogForScope.length === 0 || catalogForScope.some((item) => item.key === key)),
      );
      const coherentKeys = scopeFromDetail === "agency" ? applyAgencySettingsConsistency(filteredKeys) : filteredKeys;
      setSelectedModuleKeys(coherentKeys);
      setEditOriginal({ userRole: roleValueFromKey(detail.role_key), moduleKeys: [...coherentKeys].sort() });
      setEditLockedInherited(Boolean(detail.is_inherited));
      if (detail.is_inherited) {
        setErrorMessage("Acest access este moștenit și nu poate fi editat aici");
      }
      setAdvancedOpen(false);
      setAutoInviteAfterCreate(false);
    } catch (error) {
      setMode("list");
      setEditingMembershipId(null);
      setErrorMessage(editErrorMessage(error));
    } finally {
      setLoadingEditDetail(false);
    }
  }

  async function submitEditForm(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (editingMembershipId === null) {
      setErrorMessage("Membership inexistent sau inaccesibil");
      return;
    }
    if (editLockedInherited) {
      setErrorMessage("Acest access este moștenit și nu poate fi editat aici");
      return;
    }

    setSaving(true);
    setErrorMessage("");
    setModuleFieldError("");

    const nextModules = normalizeSelectedKeys(selectedModuleKeys).filter((key) => activeCatalog.some((item) => item.key === key));
    if (activeCatalog.length > 0 && nextModules.length === 0) {
      setSaving(false);
      setModuleFieldError("Selectează cel puțin o permisiune de navigare.");
      return;
    }

    const nextRole = userRole;

    const noRoleChange = editOriginal ? editOriginal.userRole === nextRole : false;
    const noModuleChange = editOriginal
      ? JSON.stringify([...editOriginal.moduleKeys].sort()) === JSON.stringify([...nextModules].sort())
      : false;

    if (editOriginal && noRoleChange && noModuleChange) {
      setSaving(false);
      return;
    }

    const payload: { user_role?: string; module_keys?: string[] } = {
      user_role: roleKeyFromMode(userType, userRole),
    };
    payload.module_keys = nextModules;

    try {
      await updateTeamMembership(editingMembershipId, payload);
      showToast("Permisiunile au fost actualizate");
      resetCreateForm();
      setMode("list");
      setPage(1);
      void loadMembers();
    } catch (error) {
      if (error instanceof ApiRequestError && error.status === 400) {
        const normalized = String(error.message || "").toLowerCase();
        if (normalized.includes("cheie de navigare invalid") || normalized.includes("modul invalid")) {
          setErrorMessage("Permisiunile selectate nu sunt valide pentru scope-ul acestui membership.");
        } else if (normalized.includes("în afara permisiunilor proprii")) {
          setErrorMessage("Nu poți acorda permisiuni peste grant-ceiling-ul tău curent.");
        } else {
          setErrorMessage(editErrorMessage(error));
        }
      } else {
        setErrorMessage(editErrorMessage(error));
      }
      if (error instanceof ApiRequestError && error.status === 409) {
        setEditLockedInherited(true);
      }
    } finally {
      setSaving(false);
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

    const nextModules = normalizeSelectedKeys(selectedModuleKeys).filter((key) => activeCatalog.some((item) => item.key === key));
    if (activeCatalog.length > 0 && nextModules.length === 0) {
      setSaving(false);
      setModuleFieldError("Selectează cel puțin o permisiune de navigare.");
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
      payload.module_keys = nextModules;

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
        const normalized = err.message.toLowerCase();
        if (normalized.includes("modul invalid") || normalized.includes("cheie de navigare invalid")) {
          setErrorMessage(`Permisiunile selectate sunt invalide pentru scope-ul curent. ${err.message}`);
        } else if (normalized.includes("în afara permisiunilor proprii")) {
          setErrorMessage("Nu poți acorda permisiuni peste grant-ceiling-ul tău curent.");
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

  function validateCreateIdentityStep(): boolean {
    const normalizedFirstName = firstName.trim();
    const normalizedLastName = lastName.trim();
    const normalizedEmail = email.trim();
    setErrorMessage("");
    setSubaccountFieldError("");
    if (!normalizedFirstName) {
      setErrorMessage("Prenumele este obligatoriu.");
      return false;
    }
    if (!normalizedLastName) {
      setErrorMessage("Numele este obligatoriu.");
      return false;
    }
    if (!normalizedEmail || !normalizedEmail.includes("@")) {
      setErrorMessage("Email-ul este obligatoriu.");
      return false;
    }
    if (userType === "client" && !subaccount.trim()) {
      setSubaccountFieldError("Selectarea unui sub-cont este obligatorie pentru utilizatorii de tip client.");
      return false;
    }
    return true;
  }

  const shouldShowModulePermissions = activeCatalog.length > 0;
  const permissionEditorItems = useMemo<PermissionEditorItem[]>(
    () =>
      activeCatalog.map((item) => ({
        key: item.key,
        label: item.label,
        order: item.order,
        groupKey: item.group_key,
        groupLabel: item.group_label,
        parentKey: item.parent_key ?? null,
        isContainer: item.is_container,
      })),
    [activeCatalog],
  );
  const isEditSaveDisabled = useMemo(() => {
    if (mode !== "edit") return false;
    if (saving || loadingEditDetail || editLockedInherited || editingMembershipId === null || editOriginal === null) return true;
    if (selectedModuleKeys.length === 0) return true;

    const sameRole = editOriginal.userRole === userRole;
    const normalizedNow = [...selectedModuleKeys.map((key) => key.trim().toLowerCase()).filter((key) => key !== "")].sort();
    const normalizedOriginal = [...editOriginal.moduleKeys].sort();
    const sameModules = JSON.stringify(normalizedNow) === JSON.stringify(normalizedOriginal);
    return sameRole && sameModules;
  }, [mode, saving, loadingEditDetail, editLockedInherited, editingMembershipId, editOriginal, selectedModuleKeys, userRole]);

  function applyAgencySettingsConsistency(keys: string[]): string[] {
    if (activeScope !== "agency") return normalizeSelectedKeys(keys);
    const normalized = new Set(normalizeSelectedKeys(keys));
    const settingsParent = activeCatalog.find((item) => item.key === "settings");
    const settingsChildren = activeCatalog.filter((item) => item.parent_key === "settings").map((item) => item.key);
    if (!settingsParent || settingsChildren.length === 0) return Array.from(normalized);
    if (!normalized.has("settings")) {
      settingsChildren.forEach((child) => normalized.delete(child));
      return Array.from(normalized);
    }
    const hasAnyChild = settingsChildren.some((child) => normalized.has(child));
    if (!hasAnyChild) {
      normalized.delete("settings");
    }
    if (hasAnyChild) {
      normalized.add("settings");
    }
    return Array.from(normalized);
  }

  function toggleModule(moduleKey: string) {
    setSelectedModuleKeys((prev) => {
      const nextSet = new Set(normalizeSelectedKeys(prev));
      const isEnabled = nextSet.has(moduleKey);
      const isSettingsParent = activeScope === "agency" && moduleKey === "settings";
      const isSettingsChild = activeScope === "agency" && activeCatalog.some((item) => item.parent_key === "settings" && item.key === moduleKey);
      const settingsChildren = activeCatalog.filter((item) => item.parent_key === "settings").map((item) => item.key);

      if (isSettingsParent) {
        if (isEnabled) {
          nextSet.delete("settings");
          settingsChildren.forEach((child) => nextSet.delete(child));
        } else {
          nextSet.add("settings");
          settingsChildren.forEach((child) => nextSet.add(child));
        }
      } else if (isSettingsChild) {
        if (isEnabled) nextSet.delete(moduleKey);
        else {
          nextSet.add(moduleKey);
          nextSet.add("settings");
        }
      } else if (isEnabled) {
        nextSet.delete(moduleKey);
      } else {
        nextSet.add(moduleKey);
      }
      return applyAgencySettingsConsistency(Array.from(nextSet));
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
                <button
                  className="wm-btn-primary"
                  type="button"
                  onClick={() => {
                    resetCreateForm();
                    setMode("create");
                    setActiveFormTab("identity");
                  }}
                >
                  + Adaugă Utilizator
                </button>
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
                        <th className="px-3 py-2">Status</th>
                        <th className="px-3 py-2">Locație</th>
                        <th className="px-3 py-2 text-right">Acțiuni</th>
                      </tr>
                    </thead>
                    <tbody>
                      {loadingMembers ? (
                        <tr>
                          <td className="px-3 py-6 text-center text-slate-500" colSpan={7}>Se încarcă membri...</td>
                        </tr>
                      ) : members.length === 0 ? (
                        <tr>
                          <td className="px-3 py-6 text-center text-slate-500" colSpan={7}>Nu există membri pentru filtrele curente.</td>
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
                            <td className="px-3 py-2">
                              {normalizeMembershipStatus(member) === "active" ? (
                                <span className="inline-flex rounded-full bg-emerald-50 px-2 py-0.5 text-xs font-medium text-emerald-700">Activ</span>
                              ) : (
                                <span className="inline-flex rounded-full bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-600">Inactiv</span>
                              )}
                            </td>
                            <td className="px-3 py-2">{member.location}</td>
                            <td className="px-3 py-2">
                              <div className="flex items-center justify-end gap-2 text-slate-500">
                                <button type="button" className="rounded p-1 hover:bg-slate-100" title="Editează" onClick={() => void openEditForm(member)}><Pencil className="h-4 w-4" /></button>
                                {(() => {
                                  const membershipId = getMembershipId(member);
                                  const loadingLifecycle = membershipId !== null && Boolean(lifecycleLoadingByMembership[membershipId]);
                                  const isInherited = Boolean(member.is_inherited);
                                  const isActive = normalizeMembershipStatus(member) === "active";
                                  const label = isActive ? "Dezactivează" : "Reactivează";
                                  return (
                                    <button
                                      type="button"
                                      className="rounded p-1 hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-50"
                                      title={isInherited ? "Access moștenit — indisponibil" : label}
                                      aria-label={label}
                                      disabled={membershipId === null || loadingLifecycle || isInherited}
                                      onClick={() => void onToggleMembershipLifecycle(member)}
                                    >
                                      {loadingLifecycle ? <Loader2 className="h-4 w-4 animate-spin" /> : isActive ? <Power className="h-4 w-4" /> : <RefreshCw className="h-4 w-4" />}
                                    </button>
                                  );
                                })()}
                                {(() => {
                                  const membershipId = getMembershipId(member);
                                  const isInherited = Boolean(member.is_inherited);
                                  const loadingRemove = membershipId !== null && Boolean(removeLoadingByMembership[membershipId]);
                                  return (
                                    <button
                                      type="button"
                                      className="rounded border border-rose-200 px-2 py-1 text-xs text-rose-700 hover:bg-rose-50 disabled:cursor-not-allowed disabled:opacity-50"
                                      title={isInherited ? "Acces moștenit — nu poate fi eliminat local" : "Elimină accesul"}
                                      aria-label="Elimină accesul"
                                      disabled={membershipId === null || loadingRemove || isInherited}
                                      onClick={() => void onRemoveMembership(member)}
                                    >
                                      <span className="inline-flex items-center gap-1">
                                        {loadingRemove ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Trash2 className="h-3.5 w-3.5" />}
                                        Elimină accesul
                                      </span>
                                    </button>
                                  );
                                })()}
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
                  <div className="space-y-2">
                    <button
                      type="button"
                      className={`block w-full rounded-md px-3 py-2 text-left text-sm font-medium ${
                        activeFormTab === "identity" ? "bg-indigo-50 text-indigo-700" : "text-slate-600 hover:bg-slate-50"
                      }`}
                      onClick={() => setActiveFormTab("identity")}
                    >
                      Informații Utilizator
                    </button>
                    <button
                      type="button"
                      className={`block w-full rounded-md px-3 py-2 text-left text-sm font-medium ${
                        activeFormTab === "permissions" ? "bg-indigo-50 text-indigo-700" : "text-slate-600 hover:bg-slate-50"
                      }`}
                      onClick={() => setActiveFormTab("permissions")}
                    >
                      Roluri și Permisiuni
                    </button>
                  </div>
                </aside>

                <form className="wm-card space-y-4 p-4" onSubmit={mode === "edit" ? submitEditForm : submitCreateForm}>
                  <h2 className="text-lg font-semibold text-slate-900">{activeFormTab === "identity" ? "Informații Utilizator" : "Roluri și Permisiuni"}</h2>

                  {activeFormTab === "identity" ? (
                    <>
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
                          <input className="wm-input mt-1" value={firstName} onChange={(e) => setFirstName(e.target.value)} required disabled={mode === "edit"} />
                        </label>
                        <label className="text-sm text-slate-700">
                          Nume
                          <input className="wm-input mt-1" value={lastName} onChange={(e) => setLastName(e.target.value)} required disabled={mode === "edit"} />
                        </label>
                        <label className="text-sm text-slate-700 md:col-span-2">
                          Email <span className="text-red-500">*</span>
                          <input className="wm-input mt-1" type="email" value={email} onChange={(e) => setEmail(e.target.value)} required disabled={mode === "edit"} />
                        </label>
                        <label className="text-sm text-slate-700">
                          Telefon
                          <input className="wm-input mt-1" value={phone} onChange={(e) => setPhone(e.target.value)} disabled={mode === "edit"} />
                        </label>
                        <label className="text-sm text-slate-700">
                          Extensie
                          <input className="wm-input mt-1" value={extension} onChange={(e) => setExtension(e.target.value)} disabled={mode === "edit"} />
                        </label>
                        <label className="text-sm text-slate-700">
                          Tip Utilizator
                          <select className="wm-input mt-1" value={userType} onChange={(e) => setUserType(e.target.value)} disabled={mode === "edit"}>
                            <option value="agency">Agency</option>
                            <option value="client">Client</option>
                          </select>
                        </label>
                        <label className="text-sm text-slate-700">
                          Rol Utilizator
                          <select className="wm-input mt-1" value={userRole} onChange={(e) => setUserRole(e.target.value)} disabled={editLockedInherited}>
                            <option value="admin">Admin</option>
                            <option value="member">Membru</option>
                            <option value="viewer">Viewer</option>
                          </select>
                        </label>
                        <label className="text-sm text-slate-700">
                          Locație
                          <input className="wm-input mt-1" value={location} onChange={(e) => setLocation(e.target.value)} disabled={mode === "edit"} />
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
                            disabled={userType === "agency" || mode === "edit"}
                          >
                            <option value="">Selectează Sub-cont</option>
                            {subaccountOptions.map((item) => (
                              <option key={item.id} value={String(item.id)}>{item.label || item.name}</option>
                            ))}
                          </select>
                          {subaccountFieldError ? <p className="mt-1 text-xs text-red-600">{subaccountFieldError}</p> : null}
                        </label>
                      </div>
                    </>
                  ) : shouldShowModulePermissions ? (
                    <PermissionsEditor
                      scope={activeScope}
                      items={permissionEditorItems}
                      selectedKeys={selectedModuleKeys}
                      onToggle={toggleModule}
                      loading={moduleCatalogLoading}
                      loadError={moduleCatalogError ? `Nu am putut încărca modulele: ${moduleCatalogError}` : null}
                      fieldError={moduleFieldError}
                      readOnly={editLockedInherited}
                      summaryHint="Rolul selectat rămâne baza de acces. Toggle-urile restrâng ce vede utilizatorul în navigație."
                      getItemDisabled={(item) =>
                        editLockedInherited ||
                        (activeScope === "agency" && Boolean(item.parentKey) && item.parentKey === "settings" && !selectedModuleKeys.includes("settings"))
                      }
                    />
                  ) : null}

                  {mode === "edit" && editingMembershipId !== null ? (
                    <p className="rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-700">
                      Status membership curent: <span className="font-semibold">{members.find((item) => getMembershipId(item) === editingMembershipId)?.membership_status === "inactive" ? "Inactiv" : "Activ"}</span>
                    </p>
                  ) : null}

                  {activeFormTab === "identity"
                    ? mode !== "edit" ? (
                        <>
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
                        </>
                      ) : (
                        <p className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">
                          Editarea identității globale (nume/email/telefon) va fi disponibilă într-un task ulterior.
                        </p>
                      )
                    : null}

                  <div className="flex items-center justify-end gap-2 border-t border-slate-100 pt-3">
                    <button type="button" className="wm-btn-secondary" onClick={() => { resetCreateForm(); setMode("list"); }}>
                      Anulează
                    </button>
                    {mode === "create" && activeFormTab === "identity" ? (
                      <button
                        type="button"
                        className="wm-btn-primary"
                        disabled={saving}
                        onClick={() => {
                          if (!validateCreateIdentityStep()) return;
                          setActiveFormTab("permissions");
                        }}
                      >
                        Pasul Următor
                      </button>
                    ) : (
                      <button type="submit" className="wm-btn-primary" disabled={mode === "edit" ? isEditSaveDisabled : saving}>
                        {saving ? <span className="inline-flex items-center gap-2"><Loader2 className="h-4 w-4 animate-spin" /> Se salvează...</span> : mode === "edit" ? "Salvează" : "Creează utilizator"}
                      </button>
                    )}
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
