"use client";

import { FormEvent, useState } from "react";
import {
  CheckCircle,
  ExternalLink,
  HelpCircle,
  Loader2,
  XCircle,
} from "lucide-react";

import {
  LIGHTSPEED_REGIONS,
  testLightspeedConnectionPreSave,
  type LightspeedTestConnectionResponse,
} from "@/lib/hooks/useLightspeedSource";

/**
 * Dedicated Step 3 form for Lightspeed eCom sources.
 *
 * Lightspeed connections need Shop ID, Shop Language, and Shop Region
 * instead of API credentials.  This form collects those non-sensitive
 * metadata fields alongside the store URL.
 *
 * Mirrors the visual layout of ``GenericApiKeySourceForm`` (Tailwind
 * ``wm-*`` utility classes, Romanian copy, inline test-connection
 * result banner) for wizard consistency.
 */

export type LightspeedFormData = {
  source_name: string;
  store_url: string;
  shop_id: string;
  shop_language: string;
  shop_region: string;
};

type FormErrors = Partial<Record<keyof LightspeedFormData, string>>;

export function LightspeedSourceForm({
  onSubmit,
  onCancel,
  busy,
}: {
  onSubmit: (data: LightspeedFormData) => void;
  onCancel: () => void;
  busy: boolean;
}) {
  const [name, setName] = useState("");
  const [storeUrl, setStoreUrl] = useState("");
  const [shopId, setShopId] = useState("");
  const [shopLanguage, setShopLanguage] = useState("");
  const [shopRegion, setShopRegion] = useState("");
  const [errors, setErrors] = useState<FormErrors>({});
  const [testStatus, setTestStatus] =
    useState<LightspeedTestConnectionResponse | null>(null);
  const [testing, setTesting] = useState(false);

  function validate(): boolean {
    const next: FormErrors = {};
    if (!name.trim()) next.source_name = "Numele sursei este obligatoriu.";
    if (!storeUrl.trim()) {
      next.store_url = "Store URL este obligatoriu.";
    } else {
      try {
        const parsed = new URL(storeUrl);
        if (parsed.protocol !== "https:" && parsed.protocol !== "http:") {
          next.store_url =
            "Store URL trebuie să înceapă cu http:// sau https://";
        }
      } catch {
        next.store_url = "Store URL nu este valid.";
      }
    }
    if (!shopId.trim()) next.shop_id = "Shop ID este obligatoriu.";
    if (!shopRegion) next.shop_region = "Shop Region este obligatoriu.";
    setErrors(next);
    return Object.keys(next).length === 0;
  }

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!validate()) return;
    onSubmit({
      source_name: name.trim(),
      store_url: storeUrl.trim(),
      shop_id: shopId.trim(),
      shop_language: shopLanguage.trim(),
      shop_region: shopRegion,
    });
  }

  async function handleTestConnection() {
    if (!storeUrl.trim()) {
      setErrors({ store_url: "Store URL este obligatoriu pentru test." });
      return;
    }
    setTesting(true);
    setTestStatus(null);
    try {
      const result = await testLightspeedConnectionPreSave(storeUrl.trim());
      setTestStatus(result);
    } catch (err) {
      setTestStatus({
        success: false,
        message: err instanceof Error ? err.message : "Eroare la testare.",
        details: {},
      });
    } finally {
      setTesting(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-5">
      {/* Source Name */}
      <div>
        <label
          htmlFor="ls-name"
          className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300"
        >
          Source Name
        </label>
        <input
          id="ls-name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Ex: Main Lightspeed Store"
          className="wm-input"
          autoComplete="off"
        />
        {errors.source_name ? (
          <p className="mt-1 text-xs text-red-600">{errors.source_name}</p>
        ) : null}
      </div>

      {/* Store URL */}
      <div>
        <label
          htmlFor="ls-url"
          className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300"
        >
          Store URL
        </label>
        <input
          id="ls-url"
          value={storeUrl}
          onChange={(e) => {
            setStoreUrl(e.target.value);
            if (testStatus) setTestStatus(null);
          }}
          placeholder="https://mystore.com"
          className="wm-input"
          autoComplete="off"
          spellCheck={false}
        />
        {errors.store_url ? (
          <p className="mt-1 text-xs text-red-600">{errors.store_url}</p>
        ) : (
          <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
            URL-ul de bază al magazinului Lightspeed eCom al clientului.
          </p>
        )}
      </div>

      {/* Shop ID */}
      <div>
        <label
          htmlFor="ls-shop-id"
          className="mb-1 flex items-center gap-1 text-sm font-medium text-slate-700 dark:text-slate-300"
        >
          Shop ID
          <span className="group relative">
            <HelpCircle className="h-3.5 w-3.5 text-slate-400" />
            <span className="pointer-events-none absolute bottom-full left-1/2 z-10 mb-2 w-64 -translate-x-1/2 rounded-lg border border-slate-200 bg-white p-2 text-xs font-normal text-slate-600 opacity-0 shadow-lg transition-opacity group-hover:opacity-100 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-300">
              În Lightspeed, Shop ID (Shop Number) se găsește după click pe
              numele magazinului în partea de sus a panoului din stânga.
            </span>
          </span>
        </label>
        <input
          id="ls-shop-id"
          value={shopId}
          onChange={(e) => setShopId(e.target.value)}
          placeholder="ex: 123456"
          className="wm-input"
          autoComplete="off"
          spellCheck={false}
        />
        {errors.shop_id ? (
          <p className="mt-1 text-xs text-red-600">{errors.shop_id}</p>
        ) : null}
      </div>

      {/* Shop Language */}
      <div>
        <label
          htmlFor="ls-shop-language"
          className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300"
        >
          Shop Language
        </label>
        <select
          id="ls-shop-language"
          value={shopLanguage}
          onChange={(e) => setShopLanguage(e.target.value)}
          className="wm-input"
        >
          <option value="">— Selectează limba —</option>
          <option value="en">English</option>
          <option value="nl">Nederlands</option>
          <option value="fr">Français</option>
          <option value="de">Deutsch</option>
          <option value="es">Español</option>
          <option value="it">Italiano</option>
          <option value="pt">Português</option>
          <option value="da">Dansk</option>
          <option value="sv">Svenska</option>
          <option value="fi">Suomi</option>
          <option value="nb">Norsk</option>
          <option value="pl">Polski</option>
          <option value="cs">Čeština</option>
          <option value="ro">Română</option>
        </select>
        {errors.shop_language ? (
          <p className="mt-1 text-xs text-red-600">{errors.shop_language}</p>
        ) : null}
      </div>

      {/* Shop Region */}
      <div>
        <label
          htmlFor="ls-shop-region"
          className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300"
        >
          Shop Region
        </label>
        <select
          id="ls-shop-region"
          value={shopRegion}
          onChange={(e) => setShopRegion(e.target.value)}
          className="wm-input"
        >
          <option value="">— Selectează regiunea —</option>
          {LIGHTSPEED_REGIONS.map((region) => (
            <option key={region} value={region}>
              {region}
            </option>
          ))}
        </select>
        {errors.shop_region ? (
          <p className="mt-1 text-xs text-red-600">{errors.shop_region}</p>
        ) : null}
      </div>

      {/* Help text */}
      <details className="text-xs text-slate-500 dark:text-slate-400">
        <summary className="flex cursor-pointer items-center gap-1 hover:text-slate-700 dark:hover:text-slate-300">
          <ExternalLink className="h-3.5 w-3.5" />
          Cum obții datele de conectare din Lightspeed?
        </summary>
        <p className="mt-2 max-w-prose leading-relaxed">
          Solicită clientului aceste date din panoul de administrare Lightspeed
          eCom. Shop ID (Shop Number) se găsește după click pe numele
          magazinului în partea de sus a panoului din stânga. Shop Language și
          Shop Region se aleg din setările magazinului.
        </p>
      </details>

      {/* Test connection result */}
      {testStatus ? (
        <div
          className={`flex items-start gap-2 rounded-lg p-3 text-sm ${
            testStatus.success
              ? "bg-emerald-50 text-emerald-700 dark:bg-emerald-900/20 dark:text-emerald-400"
              : "bg-red-50 text-red-700 dark:bg-red-900/20 dark:text-red-400"
          }`}
        >
          {testStatus.success ? (
            <CheckCircle className="mt-0.5 h-4 w-4 flex-shrink-0" />
          ) : (
            <XCircle className="mt-0.5 h-4 w-4 flex-shrink-0" />
          )}
          <div className="flex-1">
            <p className="font-medium">{testStatus.message}</p>
          </div>
        </div>
      ) : null}

      {/* Sync note */}
      <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-xs text-amber-800 dark:border-amber-800 dark:bg-amber-900/20 dark:text-amber-200">
        <strong>Notă:</strong> Conectorul complet pentru Lightspeed este în
        dezvoltare. Pentru moment poți salva sursa și configurația —
        sincronizarea automată a produselor va fi disponibilă în curând.
      </div>

      {/* Buttons */}
      <div className="flex flex-wrap items-center gap-3 pt-2">
        <button type="submit" className="wm-btn-primary" disabled={busy}>
          {busy ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
          {busy ? "Se creează..." : "Creează sursă"}
        </button>
        <button
          type="button"
          onClick={() => void handleTestConnection()}
          className="wm-btn-secondary"
          disabled={testing || busy}
        >
          {testing ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
          {testing ? "Se testează..." : "Testează conexiunea"}
        </button>
        <button
          type="button"
          onClick={onCancel}
          className="wm-btn-secondary"
          disabled={busy}
        >
          Anulează
        </button>
      </div>
    </form>
  );
}
