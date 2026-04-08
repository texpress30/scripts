"use client";

import { FormEvent, useState } from "react";
import { CheckCircle, Eye, EyeOff, ExternalLink, Loader2, XCircle } from "lucide-react";

/**
 * Dedicated Magento 2 source form for wizard Step 3.
 *
 * Collects the four OAuth 1.0a credentials that the merchant mints in
 * ``System → Extensions → Integrations`` (plus the storefront URL and an
 * optional store view code) and exposes two independent actions:
 *
 * * **Testează conexiunea** — calls ``onTestConnection`` which hits
 *   ``POST /integrations/magento/test-connection`` with the credentials
 *   directly in the request body. The values are NEVER persisted on the
 *   backend for this call.
 * * **Creează sursa** — calls ``onSubmit`` which hits
 *   ``POST /integrations/magento/sources``. Disabled until a successful
 *   Test Connection, unless the user explicitly overrides via
 *   "Salvează fără testare".
 *
 * Mirrors the style + UX of ``GenericEcommerceForm`` / ``ShopifySourceForm``
 * so it feels native in the wizard — same ``wm-input`` / ``wm-btn-*``
 * utility classes, Romanian copy, inline error messages.
 */

export type MagentoConnectFormData = {
  source_name: string;
  magento_base_url: string;
  magento_store_code: string;
  consumer_key: string;
  consumer_secret: string;
  access_token: string;
  access_token_secret: string;
};

export type MagentoTestConnectionResult = {
  success: boolean;
  message: string;
  store_name?: string | null;
  base_currency?: string | null;
};

type FormErrors = Partial<Record<keyof MagentoConnectFormData, string>>;

const CONSUMER_KEY_MIN_LENGTH = 10;
const DEFAULT_STORE_CODE = "default";

function isHttpsUrl(value: string): boolean {
  const trimmed = value.trim();
  if (!trimmed) return false;
  if (!trimmed.toLowerCase().startsWith("https://")) return false;
  try {
    new URL(trimmed);
    return true;
  } catch {
    return false;
  }
}

export function MagentoSourceForm({
  onSubmit,
  onTestConnection,
  onCancel,
  busy,
}: {
  onSubmit: (data: MagentoConnectFormData) => void;
  onTestConnection: (data: MagentoConnectFormData) => Promise<MagentoTestConnectionResult>;
  onCancel: () => void;
  busy: boolean;
}) {
  const [name, setName] = useState("");
  const [baseUrl, setBaseUrl] = useState("");
  const [storeCode, setStoreCode] = useState(DEFAULT_STORE_CODE);
  const [consumerKey, setConsumerKey] = useState("");
  const [consumerSecret, setConsumerSecret] = useState("");
  const [accessToken, setAccessToken] = useState("");
  const [accessTokenSecret, setAccessTokenSecret] = useState("");
  const [showConsumerSecret, setShowConsumerSecret] = useState(false);
  const [showAccessTokenSecret, setShowAccessTokenSecret] = useState(false);
  const [errors, setErrors] = useState<FormErrors>({});
  const [testStatus, setTestStatus] = useState<MagentoTestConnectionResult | null>(null);
  const [testing, setTesting] = useState(false);
  const [testTimeoutNotice, setTestTimeoutNotice] = useState(false);
  const [forceAllowCreate, setForceAllowCreate] = useState(false);

  const canCreate = testStatus?.success === true || forceAllowCreate;

  function currentData(): MagentoConnectFormData {
    return {
      source_name: name.trim(),
      magento_base_url: baseUrl.trim(),
      magento_store_code: storeCode.trim() || DEFAULT_STORE_CODE,
      consumer_key: consumerKey.trim(),
      consumer_secret: consumerSecret.trim(),
      access_token: accessToken.trim(),
      access_token_secret: accessTokenSecret.trim(),
    };
  }

  function validate(requireSourceName: boolean): FormErrors {
    const next: FormErrors = {};
    if (requireSourceName && !name.trim()) {
      next.source_name = "Numele sursei este obligatoriu.";
    }
    if (!baseUrl.trim()) {
      next.magento_base_url = "Magento Base URL este obligatoriu.";
    } else if (!isHttpsUrl(baseUrl)) {
      next.magento_base_url = "Magento Base URL trebuie să înceapă cu https://";
    }
    if (!consumerKey.trim()) {
      next.consumer_key = "Consumer Key este obligatoriu.";
    } else if (consumerKey.trim().length < CONSUMER_KEY_MIN_LENGTH) {
      next.consumer_key = `Consumer Key are minim ${CONSUMER_KEY_MIN_LENGTH} caractere.`;
    }
    if (!consumerSecret.trim()) {
      next.consumer_secret = "Consumer Secret este obligatoriu.";
    }
    if (!accessToken.trim()) {
      next.access_token = "Access Token este obligatoriu.";
    } else if (accessToken.trim().length < CONSUMER_KEY_MIN_LENGTH) {
      next.access_token = `Access Token are minim ${CONSUMER_KEY_MIN_LENGTH} caractere.`;
    }
    if (!accessTokenSecret.trim()) {
      next.access_token_secret = "Access Token Secret este obligatoriu.";
    }
    return next;
  }

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    const next = validate(true);
    setErrors(next);
    if (Object.keys(next).length > 0) return;
    onSubmit(currentData());
  }

  async function handleTestConnection() {
    const next = validate(false);
    setErrors(next);
    if (Object.keys(next).length > 0) return;

    setTesting(true);
    setTestStatus(null);
    setTestTimeoutNotice(false);

    // Slow-network hint — visible after 12s like the backend probe timeout.
    const timeoutId = window.setTimeout(() => setTestTimeoutNotice(true), 12_000);

    try {
      const result = await onTestConnection(currentData());
      setTestStatus(result);
      if (result.success) {
        // Once the merchant has proven the credentials work, re-enable Create
        // automatically — no need to re-click the override checkbox.
        setForceAllowCreate(false);
      }
    } catch (err) {
      setTestStatus({
        success: false,
        message: err instanceof Error ? err.message : "Eroare la testarea conexiunii.",
      });
    } finally {
      window.clearTimeout(timeoutId);
      setTesting(false);
      setTestTimeoutNotice(false);
    }
  }

  // Any credential change after a successful test invalidates it — the
  // merchant must re-run Test Connection before we re-enable Create.
  function onCredentialChange(setter: (value: string) => void) {
    return (value: string) => {
      setter(value);
      if (testStatus !== null) setTestStatus(null);
    };
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-5">
      <div>
        <label htmlFor="mg-name" className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">
          Source Name
        </label>
        <input
          id="mg-name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Ex: Main Magento Store"
          className="wm-input"
          autoComplete="off"
        />
        {errors.source_name ? <p className="mt-1 text-xs text-red-600">{errors.source_name}</p> : null}
      </div>

      <div>
        <label htmlFor="mg-url" className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">
          Magento Base URL
        </label>
        <input
          id="mg-url"
          value={baseUrl}
          onChange={(e) => onCredentialChange(setBaseUrl)(e.target.value)}
          placeholder="https://magento.example.com"
          className="wm-input"
          autoComplete="off"
          spellCheck={false}
        />
        {errors.magento_base_url ? (
          <p className="mt-1 text-xs text-red-600">{errors.magento_base_url}</p>
        ) : (
          <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
            URL-ul de frontal al magazinului (fără trailing slash). Magento modern necesită HTTPS.
          </p>
        )}
      </div>

      <div>
        <label htmlFor="mg-store-code" className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">
          Store View Code <span className="text-slate-400">(opțional)</span>
        </label>
        <input
          id="mg-store-code"
          value={storeCode}
          onChange={(e) => onCredentialChange(setStoreCode)(e.target.value)}
          placeholder="default"
          className="wm-input"
          autoComplete="off"
        />
        <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
          Codul store view-ului Magento. Lasă „default" dacă magazinul are un singur store view.
        </p>
      </div>

      <div>
        <label htmlFor="mg-ck" className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">
          Consumer Key
        </label>
        <input
          id="mg-ck"
          value={consumerKey}
          onChange={(e) => onCredentialChange(setConsumerKey)(e.target.value)}
          placeholder="abcdef1234567890…"
          className="wm-input"
          autoComplete="off"
          spellCheck={false}
        />
        {errors.consumer_key ? <p className="mt-1 text-xs text-red-600">{errors.consumer_key}</p> : null}
      </div>

      <div>
        <label htmlFor="mg-cs" className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">
          Consumer Secret
        </label>
        <div className="relative">
          <input
            id="mg-cs"
            type={showConsumerSecret ? "text" : "password"}
            value={consumerSecret}
            onChange={(e) => onCredentialChange(setConsumerSecret)(e.target.value)}
            placeholder="••••••••"
            className="wm-input pr-10"
            autoComplete="off"
            spellCheck={false}
          />
          <button
            type="button"
            onClick={() => setShowConsumerSecret((v) => !v)}
            className="absolute inset-y-0 right-0 flex items-center px-3 text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-200"
            aria-label={showConsumerSecret ? "Ascunde Consumer Secret" : "Afișează Consumer Secret"}
            tabIndex={-1}
          >
            {showConsumerSecret ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
          </button>
        </div>
        {errors.consumer_secret ? <p className="mt-1 text-xs text-red-600">{errors.consumer_secret}</p> : null}
      </div>

      <div>
        <label htmlFor="mg-at" className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">
          Access Token
        </label>
        <input
          id="mg-at"
          value={accessToken}
          onChange={(e) => onCredentialChange(setAccessToken)(e.target.value)}
          placeholder="abcdef1234567890…"
          className="wm-input"
          autoComplete="off"
          spellCheck={false}
        />
        {errors.access_token ? <p className="mt-1 text-xs text-red-600">{errors.access_token}</p> : null}
      </div>

      <div>
        <label htmlFor="mg-ats" className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">
          Access Token Secret
        </label>
        <div className="relative">
          <input
            id="mg-ats"
            type={showAccessTokenSecret ? "text" : "password"}
            value={accessTokenSecret}
            onChange={(e) => onCredentialChange(setAccessTokenSecret)(e.target.value)}
            placeholder="••••••••"
            className="wm-input pr-10"
            autoComplete="off"
            spellCheck={false}
          />
          <button
            type="button"
            onClick={() => setShowAccessTokenSecret((v) => !v)}
            className="absolute inset-y-0 right-0 flex items-center px-3 text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-200"
            aria-label={showAccessTokenSecret ? "Ascunde Access Token Secret" : "Afișează Access Token Secret"}
            tabIndex={-1}
          >
            {showAccessTokenSecret ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
          </button>
        </div>
        {errors.access_token_secret ? (
          <p className="mt-1 text-xs text-red-600">{errors.access_token_secret}</p>
        ) : null}
      </div>

      <details className="text-xs text-slate-500 dark:text-slate-400">
        <summary className="flex cursor-pointer items-center gap-1 hover:text-slate-700 dark:hover:text-slate-300">
          <ExternalLink className="h-3.5 w-3.5" />
          De unde iau aceste credențiale?
        </summary>
        <p className="mt-2 max-w-prose leading-relaxed">
          În Magento Admin accesează <strong>System → Extensions → Integrations → Add New Integration</strong>.
          Setează permisiunile pe resource <code>Catalog → Inventory → Products</code> (read) și
          <code> Stores → Settings → Configuration</code> (read). Apasă <strong>Save</strong>, apoi butonul
          <strong> Activate</strong>. Magento îți va afișa cele 4 credențiale OAuth 1.0a — copiază-le aici.
          Ele NU se pot recupera ulterior: dacă le pierzi, reactivează Integration-ul pentru a genera altele noi.
        </p>
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
            {testStatus.success && (testStatus.store_name || testStatus.base_currency) ? (
              <p className="mt-0.5 text-xs opacity-80">
                {testStatus.store_name ? <span>{testStatus.store_name}</span> : null}
                {testStatus.store_name && testStatus.base_currency ? " · " : null}
                {testStatus.base_currency ? <span>{testStatus.base_currency}</span> : null}
              </p>
            ) : null}
          </div>
        </div>
      ) : null}

      {testing && testTimeoutNotice ? (
        <p className="text-xs text-slate-500 dark:text-slate-400">
          Verificare în curs — Magento răspunde mai lent decât de obicei. Încă aștept…
        </p>
      ) : null}

      {!canCreate && testStatus === null ? (
        <label className="flex items-center gap-2 text-xs text-slate-500 dark:text-slate-400">
          <input
            type="checkbox"
            checked={forceAllowCreate}
            onChange={(e) => setForceAllowCreate(e.target.checked)}
            className="rounded border-slate-300"
          />
          Salvează fără să testez conexiunea mai întâi
        </label>
      ) : null}

      <div className="flex flex-wrap items-center gap-3 pt-2">
        <button type="submit" className="wm-btn-primary" disabled={busy || !canCreate}>
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
        <button type="button" onClick={onCancel} className="wm-btn-secondary" disabled={busy}>
          Anulează
        </button>
      </div>
    </form>
  );
}
