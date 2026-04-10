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
  GENERIC_API_KEY_PLATFORMS,
  testGenericApiKeyConnectionPreSave,
  type GenericApiKeyPlatformDefinition,
  type GenericApiKeyPlatformKey,
  type GenericApiKeyTestConnectionResponse,
} from "@/lib/hooks/useGenericApiKeySource";

/**
 * Reusable Step 3 form for the six generic-API-key e-commerce platforms.
 *
 * The form is fully driven by the :class:`GenericApiKeyPlatformDefinition`
 * looked up from ``GENERIC_API_KEY_PLATFORMS[platform]`` — labels,
 * placeholders, help text, and the ``hasApiSecret`` toggle all come from
 * a single backend-mirroring source. Adding a 7th platform on the
 * frontend is one new entry in that map; this component requires no
 * changes.
 *
 * Mirrors the visual layout of ``MagentoSourceForm`` (Tailwind ``wm-*``
 * utility classes, Romanian copy, Eye / EyeOff password toggle, inline
 * test-connection result banner) so the wizard feels consistent
 * regardless of which platform the merchant picks.
 */

export type GenericApiKeyFormData = {
  source_name: string;
  store_url: string;
  api_key: string;
  api_secret?: string;
};

type FormErrors = Partial<Record<keyof GenericApiKeyFormData, string>>;


export function GenericApiKeySourceForm({
  platform,
  onSubmit,
  onCancel,
  busy,
}: {
  platform: GenericApiKeyPlatformKey;
  onSubmit: (data: GenericApiKeyFormData) => void;
  onCancel: () => void;
  busy: boolean;
}) {
  const definition: GenericApiKeyPlatformDefinition =
    GENERIC_API_KEY_PLATFORMS[platform];

  const [name, setName] = useState("");
  const [storeUrl, setStoreUrl] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [apiSecret, setApiSecret] = useState("");
  const [showApiSecret, setShowApiSecret] = useState(false);
  const [errors, setErrors] = useState<FormErrors>({});
  const [testStatus, setTestStatus] =
    useState<GenericApiKeyTestConnectionResponse | null>(null);
  const [testing, setTesting] = useState(false);

  function currentData(): GenericApiKeyFormData {
    const data: GenericApiKeyFormData = {
      source_name: name.trim(),
      store_url: storeUrl.trim(),
      api_key: apiKey.trim(),
    };
    if (definition.hasApiSecret && apiSecret.trim()) {
      data.api_secret = apiSecret;
    }
    return data;
  }

  function validate(): boolean {
    const next: FormErrors = {};
    if (!name.trim()) next.source_name = "Numele sursei este obligatoriu.";
    if (!storeUrl.trim()) {
      next.store_url = "Store URL este obligatoriu.";
    } else {
      try {
        const parsed = new URL(storeUrl);
        if (parsed.protocol !== "https:" && parsed.protocol !== "http:") {
          next.store_url = "Store URL trebuie să înceapă cu http:// sau https://";
        }
      } catch {
        next.store_url = "Store URL nu este valid.";
      }
    }
    if (!apiKey.trim()) {
      next.api_key = `${definition.apiKeyLabel} este obligatoriu.`;
    }
    if (definition.hasApiSecret && !apiSecret.trim()) {
      next.api_secret = `${definition.apiSecretLabel ?? "API Secret"} este obligatoriu.`;
    }
    setErrors(next);
    return Object.keys(next).length === 0;
  }

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!validate()) return;
    onSubmit(currentData());
  }

  async function handleTestConnection() {
    if (!storeUrl.trim()) {
      setErrors({ store_url: "Store URL este obligatoriu pentru test." });
      return;
    }
    setTesting(true);
    setTestStatus(null);
    try {
      const result = await testGenericApiKeyConnectionPreSave(
        platform,
        storeUrl.trim(),
      );
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

  function onCredentialChange(setter: (value: string) => void) {
    return (value: string) => {
      setter(value);
      if (testStatus !== null) setTestStatus(null);
    };
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-5">
      <div>
        <label
          htmlFor="gak-name"
          className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300"
        >
          Source Name
        </label>
        <input
          id="gak-name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder={`Ex: Main ${definition.displayName} Store`}
          className="wm-input"
          autoComplete="off"
        />
        {errors.source_name ? (
          <p className="mt-1 text-xs text-red-600">{errors.source_name}</p>
        ) : null}
      </div>

      <div>
        <label
          htmlFor="gak-url"
          className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300"
        >
          Store URL
        </label>
        <input
          id="gak-url"
          value={storeUrl}
          onChange={(e) => onCredentialChange(setStoreUrl)(e.target.value)}
          placeholder="https://mystore.com"
          className="wm-input"
          autoComplete="off"
          spellCheck={false}
        />
        {errors.store_url ? (
          <p className="mt-1 text-xs text-red-600">{errors.store_url}</p>
        ) : (
          <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
            URL-ul de bază al magazinului {definition.displayName} (fără
            trailing slash).
          </p>
        )}
      </div>

      <div>
        <label
          htmlFor="gak-api-key"
          className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300"
        >
          {definition.apiKeyLabel}
        </label>
        <input
          id="gak-api-key"
          value={apiKey}
          onChange={(e) => onCredentialChange(setApiKey)(e.target.value)}
          placeholder={definition.apiKeyPlaceholder}
          className="wm-input"
          autoComplete="off"
          spellCheck={false}
        />
        {errors.api_key ? (
          <p className="mt-1 text-xs text-red-600">{errors.api_key}</p>
        ) : null}
      </div>

      {definition.hasApiSecret ? (
        <div>
          <label
            htmlFor="gak-api-secret"
            className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300"
          >
            {definition.apiSecretLabel ?? "API Secret"}
          </label>
          <div className="relative">
            <input
              id="gak-api-secret"
              type={showApiSecret ? "text" : "password"}
              value={apiSecret}
              onChange={(e) => onCredentialChange(setApiSecret)(e.target.value)}
              placeholder={definition.apiSecretPlaceholder ?? "••••••••"}
              className="wm-input pr-10"
              autoComplete="off"
              spellCheck={false}
            />
            <button
              type="button"
              onClick={() => setShowApiSecret((v) => !v)}
              className="absolute inset-y-0 right-0 flex items-center px-3 text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-200"
              aria-label={
                showApiSecret
                  ? "Ascunde valoarea"
                  : "Afișează valoarea"
              }
              tabIndex={-1}
            >
              {showApiSecret ? (
                <EyeOff className="h-4 w-4" />
              ) : (
                <Eye className="h-4 w-4" />
              )}
            </button>
          </div>
          {errors.api_secret ? (
            <p className="mt-1 text-xs text-red-600">{errors.api_secret}</p>
          ) : null}
        </div>
      ) : null}

      <details className="text-xs text-slate-500 dark:text-slate-400">
        <summary className="flex cursor-pointer items-center gap-1 hover:text-slate-700 dark:hover:text-slate-300">
          <ExternalLink className="h-3.5 w-3.5" />
          Cum obții {definition.apiKeyLabel} din {definition.displayName} Admin?
        </summary>
        <p className="mt-2 max-w-prose leading-relaxed">{definition.helpText}</p>
      </details>

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

      <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-xs text-amber-800 dark:border-amber-800 dark:bg-amber-900/20 dark:text-amber-200">
        <strong>Notă:</strong> Sincronizarea automată a produselor pentru{" "}
        {definition.displayName} este în dezvoltare. Pentru moment poți salva
        sursa și configurația — importul automat va fi disponibil în curând.
      </div>

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
