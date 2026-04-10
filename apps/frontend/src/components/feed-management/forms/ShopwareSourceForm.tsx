"use client";

import { FormEvent, useState } from "react";
import {
  CheckCircle,
  ExternalLink,
  Eye,
  EyeOff,
  Loader2,
  XCircle,
} from "lucide-react";

import {
  testShopwareConnectionPreSave,
  type ShopwareTestConnectionResponse,
} from "@/lib/hooks/useShopwareSource";

/**
 * Dedicated Step 3 form for Shopware sources.
 *
 * Shopware connections need Store Key, Bridge Endpoint, and API Access
 * Key — three fields obtained from the Shopware connector extension.
 */

export type ShopwareFormData = {
  source_name: string;
  store_url: string;
  store_key: string;
  bridge_endpoint: string;
  api_access_key: string;
};

type FormErrors = Partial<Record<keyof ShopwareFormData, string>>;

export function ShopwareSourceForm({
  onSubmit,
  onCancel,
  busy,
}: {
  onSubmit: (data: ShopwareFormData) => void;
  onCancel: () => void;
  busy: boolean;
}) {
  const [name, setName] = useState("");
  const [storeUrl, setStoreUrl] = useState("");
  const [storeKey, setStoreKey] = useState("");
  const [bridgeEndpoint, setBridgeEndpoint] = useState("");
  const [apiAccessKey, setApiAccessKey] = useState("");
  const [showStoreKey, setShowStoreKey] = useState(false);
  const [showApiAccessKey, setShowApiAccessKey] = useState(false);
  const [errors, setErrors] = useState<FormErrors>({});
  const [testStatus, setTestStatus] =
    useState<ShopwareTestConnectionResponse | null>(null);
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
    if (!storeKey.trim()) next.store_key = "Store Key este obligatoriu.";
    if (!bridgeEndpoint.trim())
      next.bridge_endpoint = "Bridge Endpoint este obligatoriu.";
    if (!apiAccessKey.trim())
      next.api_access_key = "API Access Key este obligatoriu.";
    setErrors(next);
    return Object.keys(next).length === 0;
  }

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!validate()) return;
    onSubmit({
      source_name: name.trim(),
      store_url: storeUrl.trim(),
      store_key: storeKey.trim(),
      bridge_endpoint: bridgeEndpoint.trim(),
      api_access_key: apiAccessKey.trim(),
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
      const result = await testShopwareConnectionPreSave(storeUrl.trim());
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

  function onFieldChange(setter: (v: string) => void) {
    return (value: string) => {
      setter(value);
      if (testStatus) setTestStatus(null);
    };
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-5">
      {/* Source Name */}
      <div>
        <label
          htmlFor="sw-name"
          className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300"
        >
          Source Name
        </label>
        <input
          id="sw-name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Ex: Main Shopware Store"
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
          htmlFor="sw-url"
          className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300"
        >
          Store URL
        </label>
        <input
          id="sw-url"
          value={storeUrl}
          onChange={(e) => onFieldChange(setStoreUrl)(e.target.value)}
          placeholder="https://mystore.com"
          className="wm-input"
          autoComplete="off"
          spellCheck={false}
        />
        {errors.store_url ? (
          <p className="mt-1 text-xs text-red-600">{errors.store_url}</p>
        ) : (
          <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
            URL-ul de bază al magazinului Shopware al clientului.
          </p>
        )}
      </div>

      {/* Store Key */}
      <div>
        <label
          htmlFor="sw-store-key"
          className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300"
        >
          Store Key
        </label>
        <div className="relative">
          <input
            id="sw-store-key"
            type={showStoreKey ? "text" : "password"}
            value={storeKey}
            onChange={(e) => onFieldChange(setStoreKey)(e.target.value)}
            placeholder="ex: your-store-key"
            className="wm-input pr-10"
            autoComplete="off"
            spellCheck={false}
          />
          <button
            type="button"
            onClick={() => setShowStoreKey((v) => !v)}
            className="absolute inset-y-0 right-0 flex items-center px-3 text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-200"
            tabIndex={-1}
          >
            {showStoreKey ? (
              <EyeOff className="h-4 w-4" />
            ) : (
              <Eye className="h-4 w-4" />
            )}
          </button>
        </div>
        {errors.store_key ? (
          <p className="mt-1 text-xs text-red-600">{errors.store_key}</p>
        ) : null}
      </div>

      {/* Bridge Endpoint */}
      <div>
        <label
          htmlFor="sw-bridge-endpoint"
          className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300"
        >
          Bridge Endpoint
        </label>
        <input
          id="sw-bridge-endpoint"
          value={bridgeEndpoint}
          onChange={(e) => onFieldChange(setBridgeEndpoint)(e.target.value)}
          placeholder="ex: https://mystore.com/bridge/..."
          className="wm-input"
          autoComplete="off"
          spellCheck={false}
        />
        {errors.bridge_endpoint ? (
          <p className="mt-1 text-xs text-red-600">{errors.bridge_endpoint}</p>
        ) : null}
      </div>

      {/* API Access Key */}
      <div>
        <label
          htmlFor="sw-api-access-key"
          className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300"
        >
          API Access Key
        </label>
        <div className="relative">
          <input
            id="sw-api-access-key"
            type={showApiAccessKey ? "text" : "password"}
            value={apiAccessKey}
            onChange={(e) => onFieldChange(setApiAccessKey)(e.target.value)}
            placeholder="ex: SWIAXYZ..."
            className="wm-input pr-10"
            autoComplete="off"
            spellCheck={false}
          />
          <button
            type="button"
            onClick={() => setShowApiAccessKey((v) => !v)}
            className="absolute inset-y-0 right-0 flex items-center px-3 text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-200"
            tabIndex={-1}
          >
            {showApiAccessKey ? (
              <EyeOff className="h-4 w-4" />
            ) : (
              <Eye className="h-4 w-4" />
            )}
          </button>
        </div>
        {errors.api_access_key ? (
          <p className="mt-1 text-xs text-red-600">{errors.api_access_key}</p>
        ) : null}
      </div>

      {/* Help text */}
      <details className="text-xs text-slate-500 dark:text-slate-400">
        <summary className="flex cursor-pointer items-center gap-1 hover:text-slate-700 dark:hover:text-slate-300">
          <ExternalLink className="h-3.5 w-3.5" />
          Cum obții datele de conectare din Shopware?
        </summary>
        <p className="mt-2 max-w-prose leading-relaxed">
          Solicită clientului aceste date din Shopware. Clientul trebuie să
          instaleze conectorul în Shopware Admin → Extensions → My Extensions,
          să-l activeze, apoi din pagina de configurare a conectorului copiază
          Store Key, Bridge Endpoint și API Access Key.
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
        <strong>Notă:</strong> Sincronizarea automată a produselor pentru
        Shopware este în dezvoltare. Pentru moment poți salva sursa și
        configurația — importul automat va fi disponibil în curând.
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
