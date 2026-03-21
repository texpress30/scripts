"use client";

import React, { ChangeEvent, FormEvent, useEffect, useRef, useState } from "react";
import { Info, Upload, X } from "lucide-react";
import { useParams } from "next/navigation";

import { AppShell } from "@/components/AppShell";
import { ProtectedPage } from "@/components/ProtectedPage";
import { apiRequest } from "@/lib/api";

type GeneralForm = {
  friendlyName: string;
  legalName: string;
  email: string;
  phone: string;
  website: string;
  niche: string;
  currency: string;
};

type BusinessForm = {
  businessType: string;
  industry: string;
  registrationIdType: string;
  registrationNumber: string;
  notRegistered: boolean;
  regions: string[];
};

type AddressForm = {
  street: string;
  city: string;
  zipCode: string;
  region: string;
  country: string;
  timezone: string;
  language: string;
};

type RepresentativeForm = {
  firstName: string;
  lastName: string;
  email: string;
  jobPosition: string;
  phone: string;
};

const REGIONS = ["Africa", "Asia", "Europa", "America Latină", "SUA și Canada"];

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const URL_RE = /^https?:\/\/.+/i;
const PHONE_RE = /^\+?[0-9\s().-]{7,}$/;

function getRequiredError(value: string): string | null {
  return value.trim() === "" ? "Acest câmp este obligatoriu." : null;
}

function validateEmail(value: string): string | null {
  if (getRequiredError(value)) return "Adresa de email este obligatorie.";
  return EMAIL_RE.test(value.trim()) ? null : "Introdu o adresă de email validă.";
}

function validateUrl(value: string): string | null {
  if (getRequiredError(value)) return "Website-ul este obligatoriu.";
  return URL_RE.test(value.trim()) ? null : "Introdu un URL valid (ex: https://...).";
}

function validatePhone(value: string): string | null {
  if (getRequiredError(value)) return "Numărul de telefon este obligatoriu.";
  return PHONE_RE.test(value.trim()) ? null : "Introdu un număr de telefon valid.";
}

export default function SubAccountSettingsPage() {
  const params = useParams<{ id: string }>();
  const subaccountId = String(params.id ?? "").trim();
  const [headerClientName, setHeaderClientName] = useState("");

  const [general, setGeneral] = useState<GeneralForm>({
    friendlyName: "",
    legalName: "",
    email: "",
    phone: "",
    website: "",
    niche: "",
    currency: "",
  });
  const [business, setBusiness] = useState<BusinessForm>({
    businessType: "",
    industry: "",
    registrationIdType: "",
    registrationNumber: "",
    notRegistered: false,
    regions: [],
  });
  const [address, setAddress] = useState<AddressForm>({
    street: "",
    city: "",
    zipCode: "",
    region: "",
    country: "",
    timezone: "",
    language: "",
  });
  const [representative, setRepresentative] = useState<RepresentativeForm>({
    firstName: "",
    lastName: "",
    email: "",
    jobPosition: "",
    phone: "",
  });

  const [logoError, setLogoError] = useState("");
  const [logoName, setLogoName] = useState("");
  const [logoPreviewUrl, setLogoPreviewUrl] = useState("");
  const [loading, setLoading] = useState(true);
  const [toastMessage, setToastMessage] = useState("");
  const [errorMessage, setErrorMessage] = useState("");
  const [generalErrors, setGeneralErrors] = useState<Record<string, string>>({});
  const [businessErrors, setBusinessErrors] = useState<Record<string, string>>({});
  const [addressErrors, setAddressErrors] = useState<Record<string, string>>({});
  const [representativeErrors, setRepresentativeErrors] = useState<Record<string, string>>({});

  const logoInputRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function loadProfile() {
      setLoading(true);
      setErrorMessage("");
      try {
        const profilePayload = await apiRequest<{
          client_name?: string;
          general?: Partial<GeneralForm>;
          business?: Partial<BusinessForm>;
          address?: Partial<AddressForm>;
          representative?: Partial<RepresentativeForm>;
          logo_url?: string;
        }>(`/clients/${subaccountId}/business-profile`);
        if (cancelled) return;
        setHeaderClientName(String(profilePayload?.client_name ?? "").trim());
        setGeneral((prev) => ({ ...prev, ...(profilePayload.general ?? {}) }));
        setBusiness((prev) => ({ ...prev, ...(profilePayload.business ?? {}) }));
        setAddress((prev) => ({ ...prev, ...(profilePayload.address ?? {}) }));
        setRepresentative((prev) => ({ ...prev, ...(profilePayload.representative ?? {}) }));
        const loadedLogo = String(profilePayload.logo_url ?? "").trim();
        setLogoPreviewUrl(loadedLogo);
        setLogoName(loadedLogo ? "Logo salvat" : "");
      } catch (err) {
        if (!cancelled) setErrorMessage(err instanceof Error ? err.message : "Nu am putut încărca profilul business.");
      }
      if (!cancelled) setLoading(false);
    }

    void loadProfile();
    return () => {
      cancelled = true;
    };
  }, [subaccountId]);

  async function saveBusinessProfile() {
    await apiRequest(`/clients/${subaccountId}/business-profile`, {
      method: "PUT",
      body: JSON.stringify({
        general,
        business,
        address,
        representative,
        logo_url: logoPreviewUrl.trim(),
      }),
    });
    if (typeof window !== "undefined") {
      window.dispatchEvent(new CustomEvent("subaccount-business-profile-updated", { detail: { subaccountId } }));
    }
  }

  function showToast(message: string) {
    setToastMessage(message);
    window.setTimeout(() => setToastMessage(""), 2200);
  }

  function onLogoChange(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    if (file.size > 2.5 * 1024 * 1024) {
      setLogoError("Fișierul depășește limita de 2.5 MB.");
      setLogoName("");
      if (logoInputRef.current) logoInputRef.current.value = "";
      return;
    }
    const reader = new FileReader();
    reader.onload = () => {
      const result = typeof reader.result === "string" ? reader.result : "";
      setLogoError("");
      setLogoName(file.name);
      setLogoPreviewUrl(result);
    };
    reader.readAsDataURL(file);
  }

  function removeLogo() {
    setLogoName("");
    setLogoError("");
    setLogoPreviewUrl("");
    if (logoInputRef.current) logoInputRef.current.value = "";
  }

  async function submitGeneral(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const nextErrors: Record<string, string> = {};

    const friendlyErr = getRequiredError(general.friendlyName);
    if (friendlyErr) nextErrors.friendlyName = friendlyErr;
    const legalErr = getRequiredError(general.legalName);
    if (legalErr) nextErrors.legalName = legalErr;
    const emailErr = validateEmail(general.email);
    if (emailErr) nextErrors.email = emailErr;
    const phoneErr = validatePhone(general.phone);
    if (phoneErr) nextErrors.phone = phoneErr;
    const websiteErr = validateUrl(general.website);
    if (websiteErr) nextErrors.website = websiteErr;
    const nicheErr = getRequiredError(general.niche);
    if (nicheErr) nextErrors.niche = nicheErr;
    const currencyErr = getRequiredError(general.currency);
    if (currencyErr) nextErrors.currency = currencyErr;

    setGeneralErrors(nextErrors);
    if (Object.keys(nextErrors).length > 0) return;
    try {
      setErrorMessage("");
      await saveBusinessProfile();
      showToast("Informațiile generale au fost actualizate.");
    } catch (err) {
      setErrorMessage(err instanceof Error ? err.message : "Nu am putut salva informațiile generale.");
    }
  }

  async function submitBusiness(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const nextErrors: Record<string, string> = {};

    const typeErr = getRequiredError(business.businessType);
    if (typeErr) nextErrors.businessType = typeErr;
    const industryErr = getRequiredError(business.industry);
    if (industryErr) nextErrors.industry = industryErr;
    const regTypeErr = getRequiredError(business.registrationIdType);
    if (regTypeErr) nextErrors.registrationIdType = regTypeErr;
    if (!business.notRegistered) {
      const regNumberErr = getRequiredError(business.registrationNumber);
      if (regNumberErr) nextErrors.registrationNumber = regNumberErr;
    }
    if (business.regions.length <= 0) {
      nextErrors.regions = "Selectează cel puțin o regiune de operare.";
    }

    setBusinessErrors(nextErrors);
    if (Object.keys(nextErrors).length > 0) return;
    try {
      setErrorMessage("");
      await saveBusinessProfile();
      showToast("Informațiile despre business au fost actualizate.");
    } catch (err) {
      setErrorMessage(err instanceof Error ? err.message : "Nu am putut salva informațiile business.");
    }
  }

  async function submitAddress(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const nextErrors: Record<string, string> = {};

    for (const [key, value] of Object.entries(address)) {
      const err = getRequiredError(String(value));
      if (err) nextErrors[key] = err;
    }

    setAddressErrors(nextErrors);
    if (Object.keys(nextErrors).length > 0) return;
    try {
      setErrorMessage("");
      await saveBusinessProfile();
      showToast("Adresa business-ului a fost actualizată.");
    } catch (err) {
      setErrorMessage(err instanceof Error ? err.message : "Nu am putut salva adresa business-ului.");
    }
  }

  async function submitRepresentative(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const nextErrors: Record<string, string> = {};

    const firstErr = getRequiredError(representative.firstName);
    if (firstErr) nextErrors.firstName = firstErr;
    const lastErr = getRequiredError(representative.lastName);
    if (lastErr) nextErrors.lastName = lastErr;
    const emailErr = validateEmail(representative.email);
    if (emailErr) nextErrors.email = emailErr;
    const jobErr = getRequiredError(representative.jobPosition);
    if (jobErr) nextErrors.jobPosition = jobErr;
    const phoneErr = validatePhone(representative.phone);
    if (phoneErr) nextErrors.phone = phoneErr;

    setRepresentativeErrors(nextErrors);
    if (Object.keys(nextErrors).length > 0) return;
    try {
      setErrorMessage("");
      await saveBusinessProfile();
      showToast("Datele reprezentantului au fost actualizate.");
    } catch (err) {
      setErrorMessage(err instanceof Error ? err.message : "Nu am putut salva datele reprezentantului.");
    }
  }

  return (
    <ProtectedPage>
      <AppShell title={headerClientName ? `${headerClientName} — Profil Business` : `Sub-account #${params.id} — Profil Business`}>
        <main className="p-6">
          {loading ? <p className="mb-4 text-sm text-slate-500">Se încarcă profilul business...</p> : null}
          {toastMessage ? (
            <div className="mb-4 rounded-md border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-700">{toastMessage}</div>
          ) : null}
          {errorMessage ? <div className="mb-4 rounded-md border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">{errorMessage}</div> : null}

          <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
            <div className="space-y-4">
              <section className="wm-card rounded-lg p-4 shadow-sm">
                <h2 className="text-base font-semibold text-slate-900">Informații generale</h2>

                <div className="mt-3 rounded-md border border-dashed border-slate-300 bg-slate-50 p-3">
                  <p className="text-sm font-medium text-slate-700">Logo business</p>
                  <div className="mt-2 flex h-[180px] w-full max-w-[350px] items-center justify-center overflow-hidden rounded-md border border-slate-200 bg-white text-sm text-slate-400">
                    {logoPreviewUrl ? (
                      // eslint-disable-next-line @next/next/no-img-element
                      <img src={logoPreviewUrl} alt="Logo business" className="h-full w-full object-contain" />
                    ) : (
                      logoName || "350px × 180px (max 2.5 MB)"
                    )}
                  </div>
                  <div className="mt-3 flex flex-wrap gap-2">
                    <input ref={logoInputRef} type="file" className="hidden" onChange={onLogoChange} data-testid="logo-input" />
                    <button type="button" className="wm-btn-secondary inline-flex items-center gap-2" onClick={() => logoInputRef.current?.click()}>
                      <Upload className="h-4 w-4" /> Upload
                    </button>
                    <button type="button" className="wm-btn-secondary inline-flex items-center gap-2" onClick={removeLogo}>
                      <X className="h-4 w-4" /> Remove
                    </button>
                  </div>
                  {logoError ? <p className="mt-2 text-xs text-red-600">{logoError}</p> : null}
                </div>

                <form noValidate className="mt-4 space-y-3" onSubmit={submitGeneral}>
                  <label className="block text-sm text-slate-700">
                    Nume business (friendly) <span className="text-red-500">*</span>
                    <input className="wm-input mt-1" value={general.friendlyName} onChange={(e) => setGeneral((prev) => ({ ...prev, friendlyName: e.target.value }))} />
                    {generalErrors.friendlyName ? <p className="mt-1 text-xs text-red-600">{generalErrors.friendlyName}</p> : null}
                  </label>

                  <label className="block text-sm text-slate-700">
                    <span className="inline-flex items-center gap-1">
                      Denumire legală business <span className="text-red-500">*</span>
                      <span title="Denumirea oficială din actele firmei.">
                        <Info className="h-4 w-4 text-slate-400" />
                      </span>
                    </span>
                    <input className="wm-input mt-1" value={general.legalName} onChange={(e) => setGeneral((prev) => ({ ...prev, legalName: e.target.value }))} />
                    {generalErrors.legalName ? <p className="mt-1 text-xs text-red-600">{generalErrors.legalName}</p> : null}
                  </label>

                  <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                    <label className="text-sm text-slate-700 md:col-span-2">
                      Email business <span className="text-red-500">*</span>
                      <input type="email" className="wm-input mt-1" value={general.email} onChange={(e) => setGeneral((prev) => ({ ...prev, email: e.target.value }))} />
                      {generalErrors.email ? <p className="mt-1 text-xs text-red-600">{generalErrors.email}</p> : null}
                    </label>

                    <label className="text-sm text-slate-700">
                      Telefon business <span className="text-red-500">*</span>
                      <input type="tel" className="wm-input mt-1" value={general.phone} onChange={(e) => setGeneral((prev) => ({ ...prev, phone: e.target.value }))} />
                      {generalErrors.phone ? <p className="mt-1 text-xs text-red-600">{generalErrors.phone}</p> : null}
                    </label>

                    <label className="text-sm text-slate-700">
                      Website business <span className="text-red-500">*</span>
                      <input type="url" className="wm-input mt-1" value={general.website} onChange={(e) => setGeneral((prev) => ({ ...prev, website: e.target.value }))} />
                      {generalErrors.website ? <p className="mt-1 text-xs text-red-600">{generalErrors.website}</p> : null}
                    </label>

                    <label className="text-sm text-slate-700">
                      Nișa business <span className="text-red-500">*</span>
                      <select className="wm-input mt-1" value={general.niche} onChange={(e) => setGeneral((prev) => ({ ...prev, niche: e.target.value }))}>
                        <option value="">Selectează</option>
                        <option value="agencie_marketing">Agenție de marketing</option>
                        <option value="ecommerce">E-commerce</option>
                        <option value="parc_auto">Parc Auto</option>
                        <option value="saas">SaaS</option>
                      </select>
                      {generalErrors.niche ? <p className="mt-1 text-xs text-red-600">{generalErrors.niche}</p> : null}
                    </label>

                    <label className="text-sm text-slate-700">
                      Monedă business <span className="text-red-500">*</span>
                      <select className="wm-input mt-1" value={general.currency} onChange={(e) => setGeneral((prev) => ({ ...prev, currency: e.target.value }))}>
                        <option value="">Selectează</option>
                        <option value="RON">RON - Leu românesc</option>
                        <option value="EUR">EUR - Euro</option>
                        <option value="USD">USD - Dolar american</option>
                      </select>
                      {generalErrors.currency ? <p className="mt-1 text-xs text-red-600">{generalErrors.currency}</p> : null}
                    </label>
                  </div>

                  <div className="flex justify-end">
                    <button className="wm-btn-primary" type="submit">Actualizează informațiile</button>
                  </div>
                </form>
              </section>

              <section className="wm-card rounded-lg p-4 shadow-sm">
                <h2 className="text-base font-semibold text-slate-900">Informații business</h2>

                <form noValidate className="mt-4 space-y-3" onSubmit={submitBusiness}>
                  <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                    <label className="text-sm text-slate-700">
                      Tip business <span className="text-red-500">*</span>
                      <select className="wm-input mt-1" value={business.businessType} onChange={(e) => setBusiness((prev) => ({ ...prev, businessType: e.target.value }))}>
                        <option value="">Selectează</option>
                        <option value="srl">SRL</option>
                        <option value="sa">SA</option>
                        <option value="snc">SNC</option>
                        <option value="scs">SCS</option>
                        <option value="sca">SCA</option>
                        <option value="srl-d">SRL-D</option>
                        <option value="pfa">PFA</option>
                        <option value="ii">II</option>
                        <option value="if">IF</option>
                      </select>
                      {businessErrors.businessType ? <p className="mt-1 text-xs text-red-600">{businessErrors.businessType}</p> : null}
                    </label>

                    <label className="text-sm text-slate-700">
                      Industrie <span className="text-red-500">*</span>
                      <select className="wm-input mt-1" value={business.industry} onChange={(e) => setBusiness((prev) => ({ ...prev, industry: e.target.value }))}>
                        <option value="">Selectează</option>
                        <option value="media">Media</option>
                        <option value="marketing">Marketing</option>
                        <option value="retail">Retail</option>
                      </select>
                      {businessErrors.industry ? <p className="mt-1 text-xs text-red-600">{businessErrors.industry}</p> : null}
                    </label>

                    <label className="text-sm text-slate-700">
                      Tip identificator înregistrare <span className="text-red-500">*</span>
                      <select className="wm-input mt-1" value={business.registrationIdType} onChange={(e) => setBusiness((prev) => ({ ...prev, registrationIdType: e.target.value }))}>
                        <option value="">Selectează</option>
                        <option value="ro_vat">România: Număr TVA</option>
                      </select>
                      {businessErrors.registrationIdType ? <p className="mt-1 text-xs text-red-600">{businessErrors.registrationIdType}</p> : null}
                    </label>

                    <label className="text-sm text-slate-700">
                      Număr de înregistrare business {!business.notRegistered ? <span className="text-red-500">*</span> : null}
                      <input
                        className="wm-input mt-1"
                        value={business.registrationNumber}
                        disabled={business.notRegistered}
                        onChange={(e) => setBusiness((prev) => ({ ...prev, registrationNumber: e.target.value }))}
                      />
                      {businessErrors.registrationNumber ? <p className="mt-1 text-xs text-red-600">{businessErrors.registrationNumber}</p> : null}
                    </label>
                  </div>

                  <label className="inline-flex items-center gap-2 text-sm text-slate-700">
                    <input
                      type="checkbox"
                      checked={business.notRegistered}
                      onChange={(e) => setBusiness((prev) => ({ ...prev, notRegistered: e.target.checked }))}
                    />
                    Business-ul meu nu este înregistrat
                  </label>

                  <div>
                    <p className="text-sm text-slate-700">Regiuni de operare business <span className="text-red-500">*</span></p>
                    <div className="mt-2 grid grid-cols-1 gap-2 sm:grid-cols-2">
                      {REGIONS.map((region) => (
                        <label key={region} className="inline-flex items-center gap-2 text-sm text-slate-700">
                          <input
                            type="checkbox"
                            checked={business.regions.includes(region)}
                            onChange={(e) => {
                              setBusiness((prev) => ({
                                ...prev,
                                regions: e.target.checked ? [...prev.regions, region] : prev.regions.filter((item) => item !== region),
                              }));
                            }}
                          />
                          {region}
                        </label>
                      ))}
                    </div>
                    {businessErrors.regions ? <p className="mt-1 text-xs text-red-600">{businessErrors.regions}</p> : null}
                  </div>

                  <div className="flex justify-end">
                    <button className="wm-btn-primary" type="submit">Actualizează informațiile</button>
                  </div>
                </form>
              </section>
            </div>

            <div className="space-y-4">
              <section className="wm-card rounded-lg p-4 shadow-sm">
                <h2 className="text-base font-semibold text-slate-900">Adresă fizică business</h2>

                <form noValidate className="mt-4 space-y-3" onSubmit={submitAddress}>
                  <label className="block text-sm text-slate-700">
                    Adresă stradă <span className="text-red-500">*</span>
                    <input className="wm-input mt-1" value={address.street} onChange={(e) => setAddress((prev) => ({ ...prev, street: e.target.value }))} />
                    {addressErrors.street ? <p className="mt-1 text-xs text-red-600">{addressErrors.street}</p> : null}
                  </label>

                  <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                    <label className="text-sm text-slate-700">
                      Oraș <span className="text-red-500">*</span>
                      <input className="wm-input mt-1" value={address.city} onChange={(e) => setAddress((prev) => ({ ...prev, city: e.target.value }))} />
                      {addressErrors.city ? <p className="mt-1 text-xs text-red-600">{addressErrors.city}</p> : null}
                    </label>
                    <label className="text-sm text-slate-700">
                      Cod poștal/ZIP <span className="text-red-500">*</span>
                      <input className="wm-input mt-1" value={address.zipCode} onChange={(e) => setAddress((prev) => ({ ...prev, zipCode: e.target.value }))} />
                      {addressErrors.zipCode ? <p className="mt-1 text-xs text-red-600">{addressErrors.zipCode}</p> : null}
                    </label>
                    <label className="text-sm text-slate-700">
                      Județ / Regiune <span className="text-red-500">*</span>
                      <input className="wm-input mt-1" value={address.region} onChange={(e) => setAddress((prev) => ({ ...prev, region: e.target.value }))} />
                      {addressErrors.region ? <p className="mt-1 text-xs text-red-600">{addressErrors.region}</p> : null}
                    </label>
                    <label className="text-sm text-slate-700">
                      Țară <span className="text-red-500">*</span>
                      <select className="wm-input mt-1" value={address.country} onChange={(e) => setAddress((prev) => ({ ...prev, country: e.target.value }))}>
                        <option value="">Selectează</option>
                        <option value="RO">România</option>
                        <option value="US">Statele Unite</option>
                      </select>
                      {addressErrors.country ? <p className="mt-1 text-xs text-red-600">{addressErrors.country}</p> : null}
                    </label>
                    <label className="text-sm text-slate-700 md:col-span-2">
                      Fus orar <span className="text-red-500">*</span>
                      <select className="wm-input mt-1" value={address.timezone} onChange={(e) => setAddress((prev) => ({ ...prev, timezone: e.target.value }))}>
                        <option value="">Selectează</option>
                        <option value="Europe/Bucharest">GMT+02:00 Europe/Bucharest (EET)</option>
                        <option value="UTC">UTC</option>
                      </select>
                      {addressErrors.timezone ? <p className="mt-1 text-xs text-red-600">{addressErrors.timezone}</p> : null}
                    </label>
                    <label className="text-sm text-slate-700 md:col-span-2">
                      Limbă platformă <span className="text-red-500">*</span>
                      <select className="wm-input mt-1" value={address.language} onChange={(e) => setAddress((prev) => ({ ...prev, language: e.target.value }))}>
                        <option value="">Selectează</option>
                        <option value="ro">Română</option>
                        <option value="en">Engleză</option>
                      </select>
                      {addressErrors.language ? <p className="mt-1 text-xs text-red-600">{addressErrors.language}</p> : null}
                    </label>
                  </div>

                  <div className="flex justify-end">
                    <button className="wm-btn-primary" type="submit">Actualizează informațiile</button>
                  </div>
                </form>
              </section>

              <section className="wm-card rounded-lg p-4 shadow-sm">
                <h2 className="text-base font-semibold text-slate-900">Reprezentant autorizat</h2>

                <form noValidate className="mt-4 space-y-3" onSubmit={submitRepresentative}>
                  <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                    <label className="text-sm text-slate-700">
                      Prenume <span className="text-red-500">*</span>
                      <input className="wm-input mt-1" value={representative.firstName} onChange={(e) => setRepresentative((prev) => ({ ...prev, firstName: e.target.value }))} />
                      {representativeErrors.firstName ? <p className="mt-1 text-xs text-red-600">{representativeErrors.firstName}</p> : null}
                    </label>

                    <label className="text-sm text-slate-700">
                      Nume <span className="text-red-500">*</span>
                      <input className="wm-input mt-1" value={representative.lastName} onChange={(e) => setRepresentative((prev) => ({ ...prev, lastName: e.target.value }))} />
                      {representativeErrors.lastName ? <p className="mt-1 text-xs text-red-600">{representativeErrors.lastName}</p> : null}
                    </label>

                    <label className="text-sm text-slate-700 md:col-span-2">
                      Email reprezentant <span className="text-red-500">*</span>
                      <input type="email" className="wm-input mt-1" value={representative.email} onChange={(e) => setRepresentative((prev) => ({ ...prev, email: e.target.value }))} />
                      {representativeErrors.email ? <p className="mt-1 text-xs text-red-600">{representativeErrors.email}</p> : null}
                    </label>

                    <label className="text-sm text-slate-700">
                      Funcție <span className="text-red-500">*</span>
                      <select className="wm-input mt-1" value={representative.jobPosition} onChange={(e) => setRepresentative((prev) => ({ ...prev, jobPosition: e.target.value }))}>
                        <option value="">Selectează</option>
                        <option value="administrator">Administrator</option>
                        <option value="director_general">Director general</option>
                        <option value="owner">Owner</option>
                      </select>
                      {representativeErrors.jobPosition ? <p className="mt-1 text-xs text-red-600">{representativeErrors.jobPosition}</p> : null}
                    </label>

                    <label className="text-sm text-slate-700">
                      Număr telefon <span className="text-red-500">*</span>
                      <input type="tel" className="wm-input mt-1" value={representative.phone} onChange={(e) => setRepresentative((prev) => ({ ...prev, phone: e.target.value }))} />
                      {representativeErrors.phone ? <p className="mt-1 text-xs text-red-600">{representativeErrors.phone}</p> : null}
                    </label>
                  </div>

                  <div className="flex justify-end">
                    <button className="wm-btn-primary" type="submit">Actualizează informațiile</button>
                  </div>
                </form>
              </section>
            </div>
          </div>
        </main>
      </AppShell>
    </ProtectedPage>
  );
}
