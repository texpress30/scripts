"use client";

import React from "react";
import { FormEvent, useEffect, useState } from "react";
import { Loader2, Trash2, Upload } from "lucide-react";

import { AppShell } from "@/components/AppShell";
import { ProtectedPage } from "@/components/ProtectedPage";
import { apiRequest } from "@/lib/api";
import { completeDirectUpload, getMediaAccessUrl, initDirectUpload, uploadFileToPresignedUrl } from "@/lib/storage-client";

type CompanySettings = {
  company_name: string;
  company_email: string;
  company_phone_prefix: string;
  company_phone: string;
  company_website: string;
  business_category: string;
  business_niche: string;
  platform_primary_use: string;
  address_line1: string;
  city: string;
  postal_code: string;
  region: string;
  country: string;
  timezone: string;
  logo_url: string;
  logo_media_id?: string | null;
  logo_storage_client_id?: number | null;
};

const DEFAULT_FORM: CompanySettings = {
  company_name: "",
  company_email: "",
  company_phone_prefix: "+40",
  company_phone: "",
  company_website: "",
  business_category: "",
  business_niche: "",
  platform_primary_use: "",
  address_line1: "",
  city: "",
  postal_code: "",
  region: "",
  country: "România",
  timezone: "Europe/Bucharest",
  logo_url: "",
  logo_media_id: null,
  logo_storage_client_id: null,
};

export default function SettingsCompanyPage() {
  const [form, setForm] = useState<CompanySettings>(DEFAULT_FORM);
  const [initialForm, setInitialForm] = useState<CompanySettings>(DEFAULT_FORM);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [logoUploading, setLogoUploading] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");
  const [toastMessage, setToastMessage] = useState("");

  function showToast(message: string) {
    setToastMessage(message);
    window.setTimeout(() => setToastMessage(""), 2400);
  }

  async function loadCompanySettings() {
    setLoading(true);
    setErrorMessage("");
    try {
      const payload = await apiRequest<CompanySettings>("/company/settings", { requireAuth: true, cache: "no-store" });
      setForm(payload);
      setInitialForm(payload);
    } catch (err) {
      setErrorMessage(err instanceof Error ? err.message : "Nu am putut încărca setările companiei.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadCompanySettings();
  }, []);

  function updateField<K extends keyof CompanySettings>(key: K, value: CompanySettings[K]) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  async function onLogoPick(file: File) {
    const allowedTypes = ["image/png", "image/jpeg", "image/jpg", "image/webp", "image/svg+xml"];
    if (!allowedTypes.includes(file.type)) {
      setErrorMessage("Tip de fișier invalid. Acceptăm PNG, JPG, WEBP sau SVG.");
      return;
    }
    if (file.size > 2.5 * 1024 * 1024) {
      setErrorMessage("Fișierul depășește limita de 2.5 MB.");
      return;
    }
    const storageClientId = Number(form.logo_storage_client_id ?? 0);
    if (!Number.isFinite(storageClientId) || storageClientId <= 0) {
      setErrorMessage("Nu am putut identifica clientul storage pentru logo.");
      return;
    }
    setLogoUploading(true);
    setErrorMessage("");
    try {
      const initPayload = await initDirectUpload({
        clientId: storageClientId,
        kind: "image",
        fileName: file.name,
        mimeType: file.type,
        sizeBytes: file.size,
        metadata: { source: "agency_company_logo" },
      });
      await uploadFileToPresignedUrl({
        url: initPayload.upload.url,
        method: initPayload.upload.method,
        headers: initPayload.upload.headers,
        file,
      });
      await completeDirectUpload({
        clientId: storageClientId,
        mediaId: initPayload.media_id,
      });
      let previewUrl = "";
      try {
        const accessPayload = await getMediaAccessUrl({
          clientId: storageClientId,
          mediaId: initPayload.media_id,
          disposition: "inline",
        });
        previewUrl = String(accessPayload.url || "").trim();
      } catch {
        previewUrl = URL.createObjectURL(file);
      }
      setForm((prev) => ({
        ...prev,
        logo_media_id: initPayload.media_id,
        logo_url: previewUrl,
      }));
    } catch (err) {
      setErrorMessage(err instanceof Error ? err.message : "Upload logo eșuat.");
    } finally {
      setLogoUploading(false);
    }
  }

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaving(true);
    setErrorMessage("");
    try {
      const updated = await apiRequest<CompanySettings>("/company/settings", {
        requireAuth: true,
        method: "PATCH",
        body: JSON.stringify({
          ...form,
          logo_media_id: form.logo_media_id ?? null,
          logo_url: form.logo_media_id ? "" : form.logo_url,
        }),
      });
      setForm(updated);
      setInitialForm(updated);
      if (typeof window !== "undefined") {
        window.dispatchEvent(new CustomEvent("company-settings-updated"));
      }
      showToast("Setările companiei au fost salvate cu succes.");
    } catch (err) {
      setErrorMessage(err instanceof Error ? err.message : "Nu am putut salva setările companiei.");
    } finally {
      setSaving(false);
    }
  }

  function onCancel() {
    setForm(initialForm);
    setErrorMessage("");
  }

  return (
    <ProtectedPage>
      <AppShell title="Setări Companie">
        <main className="space-y-4 p-6">
          {toastMessage ? <div className="rounded-md border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-700">{toastMessage}</div> : null}
          {errorMessage ? <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{errorMessage}</div> : null}

          <h1 className="text-2xl font-semibold text-slate-900">Setări Companie</h1>

          <form className="space-y-6" onSubmit={onSubmit}>
            <section className="grid grid-cols-1 gap-4 lg:grid-cols-[280px_minmax(0,1fr)]">
              <div>
                <h2 className="text-base font-semibold text-slate-900">Logo și Branding</h2>
                <p className="mt-1 text-sm text-slate-500">Actualizează logo-ul care va fi folosit și ca favicon.</p>
              </div>

              <article className="wm-card space-y-4 p-4">
                <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
                  <div className="flex h-28 w-full max-w-[360px] items-center justify-center overflow-hidden rounded-lg border border-dashed border-slate-300 bg-slate-50">
                    {form.logo_url ? (
                      // eslint-disable-next-line @next/next/no-img-element
                      <img src={form.logo_url} alt="Logo companie" className="h-full w-full object-contain" />
                    ) : (
                      <span className="text-sm text-slate-500">Drop logo aici sau selectează fișier</span>
                    )}
                  </div>

                  <div className="flex items-center gap-2">
                    <label className="wm-btn-secondary inline-flex cursor-pointer items-center gap-2">
                      <Upload className="h-4 w-4" /> Înlocuiește
                      <input
                        type="file"
                        className="hidden"
                        data-testid="company-logo-input"
                        accept="image/png,image/jpeg,image/webp,image/svg+xml"
                        onChange={(e) => {
                          const file = e.target.files?.[0];
                          if (file) void onLogoPick(file);
                        }}
                      />
                    </label>
                    <button
                      type="button"
                      data-testid="company-logo-remove"
                      className="rounded-md border border-red-200 p-2 text-red-600 hover:bg-red-50"
                      onClick={() => setForm((prev) => ({ ...prev, logo_url: "", logo_media_id: null }))}
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </div>
                </div>
                <p className="text-sm text-slate-500">Mărimea propusă este 350px * 180px. Nu mai mare de 2.5 MB</p>
              </article>
            </section>

            <section className="grid grid-cols-1 gap-4 lg:grid-cols-[280px_minmax(0,1fr)]">
              <div>
                <h2 className="text-base font-semibold text-slate-900">Detalii Companie</h2>
                <p className="mt-1 text-sm text-slate-500">Actualizează detaliile de bază ale companiei.</p>
              </div>

              <article className="wm-card p-4">
                <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                  <label className="text-sm text-slate-700">
                    Nume Companie <span className="text-red-500">*</span>
                    <input className="wm-input mt-1" value={form.company_name} onChange={(e) => updateField("company_name", e.target.value)} required />
                  </label>
                  <label className="text-sm text-slate-700">
                    Email Companie <span className="text-red-500">*</span>
                    <input className="wm-input mt-1" type="email" value={form.company_email} onChange={(e) => updateField("company_email", e.target.value)} required />
                  </label>

                  <label className="text-sm text-slate-700 md:col-span-2">
                    Telefon Companie
                    <div className="mt-1 grid grid-cols-[110px_minmax(0,1fr)] gap-2">
                      <select className="wm-input" value={form.company_phone_prefix} onChange={(e) => updateField("company_phone_prefix", e.target.value)}>
                        <option value="+40">🇷🇴 +40</option>
                        <option value="+1">🇺🇸 +1</option>
                        <option value="+44">🇬🇧 +44</option>
                        <option value="+49">🇩🇪 +49</option>
                      </select>
                      <input className="wm-input" value={form.company_phone} onChange={(e) => updateField("company_phone", e.target.value)} />
                    </div>
                  </label>

                  <label className="text-sm text-slate-700 md:col-span-2">
                    Website Companie
                    <input className="wm-input mt-1" value={form.company_website} onChange={(e) => updateField("company_website", e.target.value)} />
                  </label>

                  <label className="text-sm text-slate-700">
                    Categorie Business
                    <select className="wm-input mt-1" value={form.business_category} onChange={(e) => updateField("business_category", e.target.value)}>
                      <option value="">Selectează categorie</option>
                      <option value="E-commerce">E-commerce</option>
                      <option value="Servicii">Servicii</option>
                      <option value="SaaS">SaaS</option>
                      <option value="Educație">Educație</option>
                    </select>
                  </label>
                  <label className="text-sm text-slate-700">
                    Nișă Business
                    <select className="wm-input mt-1" value={form.business_niche} onChange={(e) => updateField("business_niche", e.target.value)}>
                      <option value="">Selectează nișă</option>
                      <option value="Fashion">Fashion</option>
                      <option value="Beauty">Beauty</option>
                      <option value="B2B">B2B</option>
                      <option value="Local">Local</option>
                    </select>
                  </label>

                  <label className="text-sm text-slate-700 md:col-span-2">
                    Pentru ce folosești în principal platforma?
                    <select className="wm-input mt-1" value={form.platform_primary_use} onChange={(e) => updateField("platform_primary_use", e.target.value)}>
                      <option value="">Selectează opțiune</option>
                      <option value="Administrare campanii">Administrare campanii</option>
                      <option value="Raportare și analytics">Raportare și analytics</option>
                      <option value="Automatizări de optimizare">Automatizări de optimizare</option>
                    </select>
                  </label>
                </div>
              </article>
            </section>

            <section className="grid grid-cols-1 gap-4 lg:grid-cols-[280px_minmax(0,1fr)]">
              <div>
                <h2 className="text-base font-semibold text-slate-900">Adresă Companie</h2>
                <p className="mt-1 text-sm text-slate-500">Actualizează adresa sediului.</p>
              </div>

              <article className="wm-card space-y-3 p-4">
                <label className="text-sm text-slate-700">
                  Adresă <span className="text-red-500">*</span>
                  <input className="wm-input mt-1" value={form.address_line1} onChange={(e) => updateField("address_line1", e.target.value)} required />
                </label>

                <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                  <label className="text-sm text-slate-700">
                    Oraș <span className="text-red-500">*</span>
                    <input className="wm-input mt-1" value={form.city} onChange={(e) => updateField("city", e.target.value)} required />
                  </label>
                  <label className="text-sm text-slate-700">
                    Cod Poștal <span className="text-red-500">*</span>
                    <input className="wm-input mt-1" value={form.postal_code} onChange={(e) => updateField("postal_code", e.target.value)} required />
                  </label>
                </div>

                <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                  <label className="text-sm text-slate-700">
                    Stat / Provincie / Regiune <span className="text-red-500">*</span>
                    <input className="wm-input mt-1" value={form.region} onChange={(e) => updateField("region", e.target.value)} required />
                  </label>
                  <label className="text-sm text-slate-700">
                    Țară <span className="text-red-500">*</span>
                    <input className="wm-input mt-1" value={form.country} onChange={(e) => updateField("country", e.target.value)} required />
                  </label>
                </div>

                <label className="text-sm text-slate-700">
                  Fus Orar <span className="text-red-500">*</span>
                  <select className="wm-input mt-1" value={form.timezone} onChange={(e) => updateField("timezone", e.target.value)} required>
                    <option value="Europe/Bucharest">Europe/Bucharest</option>
                    <option value="Europe/London">Europe/London</option>
                    <option value="America/New_York">America/New_York</option>
                    <option value="UTC">UTC</option>
                  </select>
                </label>
              </article>
            </section>

            <div className="flex items-center justify-end gap-2">
              <button type="button" className="wm-btn-secondary" onClick={onCancel} disabled={saving || loading}>
                Anulează
              </button>
              <button type="submit" className="wm-btn-primary" disabled={saving || loading || logoUploading}>
                {saving || logoUploading ? (
                  <span className="inline-flex items-center gap-2"><Loader2 className="h-4 w-4 animate-spin" /> Se salvează...</span>
                ) : (
                  "Salvează Modificările"
                )}
              </button>
            </div>
          </form>
        </main>
      </AppShell>
    </ProtectedPage>
  );
}
