"use client";

import { FormEvent, useState } from "react";
import { Loader2, CheckCircle, XCircle } from "lucide-react";
import type { FeedSourceType } from "@/lib/types/feed-management";

const PLATFORM_LABELS: Record<string, { urlPlaceholder: string; urlLabel: string }> = {
  woocommerce: { urlPlaceholder: "https://my-shop.com", urlLabel: "Store URL (WordPress site)" },
  magento: { urlPlaceholder: "https://magento.example.com", urlLabel: "Magento Base URL" },
  bigcommerce: { urlPlaceholder: "https://store-xxxxx.mybigcommerce.com", urlLabel: "Store URL" },
};

type EcommerceFormData = {
  name: string;
  store_url: string;
  api_key: string;
  api_secret: string;
};

export function GenericEcommerceForm({
  sourceType,
  onSubmit,
  onTestConnection,
  onCancel,
  busy,
}: {
  sourceType: FeedSourceType;
  onSubmit: (data: EcommerceFormData) => void;
  onTestConnection: (data: Pick<EcommerceFormData, "store_url" | "api_key" | "api_secret">) => Promise<{ success: boolean; message: string }>;
  onCancel: () => void;
  busy: boolean;
}) {
  const [name, setName] = useState("");
  const [storeUrl, setStoreUrl] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [apiSecret, setApiSecret] = useState("");
  const [errors, setErrors] = useState<Partial<Record<keyof EcommerceFormData, string>>>({});
  const [testStatus, setTestStatus] = useState<{ success: boolean; message: string } | null>(null);
  const [testing, setTesting] = useState(false);

  const labels = PLATFORM_LABELS[sourceType] ?? PLATFORM_LABELS.woocommerce;

  function validate(): boolean {
    const next: typeof errors = {};
    if (!name.trim()) next.name = "Numele sursei este obligatoriu.";
    if (!storeUrl.trim()) {
      next.store_url = "URL-ul magazinului este obligatoriu.";
    } else {
      try { new URL(storeUrl); } catch { next.store_url = "URL-ul nu este valid."; }
    }
    if (!apiKey.trim()) next.api_key = "API Key / Consumer Key este obligatoriu.";
    if (!apiSecret.trim()) next.api_secret = "API Secret / Consumer Secret este obligatoriu.";
    setErrors(next);
    return Object.keys(next).length === 0;
  }

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!validate()) return;
    onSubmit({ name: name.trim(), store_url: storeUrl.trim(), api_key: apiKey.trim(), api_secret: apiSecret.trim() });
  }

  async function handleTestConnection() {
    const next: typeof errors = {};
    if (!storeUrl.trim()) next.store_url = "URL-ul magazinului este obligatoriu.";
    if (!apiKey.trim()) next.api_key = "API Key este obligatoriu.";
    if (!apiSecret.trim()) next.api_secret = "API Secret este obligatoriu.";
    if (Object.keys(next).length > 0) { setErrors(next); return; }
    setTesting(true);
    setTestStatus(null);
    try {
      const result = await onTestConnection({ store_url: storeUrl.trim(), api_key: apiKey.trim(), api_secret: apiSecret.trim() });
      setTestStatus(result);
    } catch {
      setTestStatus({ success: false, message: "Eroare la testarea conexiunii." });
    } finally {
      setTesting(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-5">
      <div>
        <label htmlFor="ge-name" className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">Source Name</label>
        <input id="ge-name" value={name} onChange={(e) => setName(e.target.value)} placeholder="Ex: WooCommerce EU Store" className="wm-input" />
        {errors.name ? <p className="mt-1 text-xs text-red-600">{errors.name}</p> : null}
      </div>
      <div>
        <label htmlFor="ge-url" className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">{labels.urlLabel}</label>
        <input id="ge-url" value={storeUrl} onChange={(e) => setStoreUrl(e.target.value)} placeholder={labels.urlPlaceholder} className="wm-input" />
        {errors.store_url ? <p className="mt-1 text-xs text-red-600">{errors.store_url}</p> : null}
      </div>
      <div>
        <label htmlFor="ge-key" className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">API Key / Consumer Key</label>
        <input id="ge-key" value={apiKey} onChange={(e) => setApiKey(e.target.value)} placeholder="ck_xxxxxxxxxx" className="wm-input" />
        {errors.api_key ? <p className="mt-1 text-xs text-red-600">{errors.api_key}</p> : null}
      </div>
      <div>
        <label htmlFor="ge-secret" className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">API Secret / Consumer Secret</label>
        <input id="ge-secret" type="password" value={apiSecret} onChange={(e) => setApiSecret(e.target.value)} placeholder="••••••••" className="wm-input" />
        {errors.api_secret ? <p className="mt-1 text-xs text-red-600">{errors.api_secret}</p> : null}
      </div>
      {testStatus ? (
        <div className={`flex items-center gap-2 rounded-lg p-3 text-sm ${testStatus.success ? "bg-emerald-50 text-emerald-700 dark:bg-emerald-900/20 dark:text-emerald-400" : "bg-red-50 text-red-700 dark:bg-red-900/20 dark:text-red-400"}`}>
          {testStatus.success ? <CheckCircle className="h-4 w-4" /> : <XCircle className="h-4 w-4" />}
          {testStatus.message}
        </div>
      ) : null}
      <div className="flex items-center gap-3 pt-2">
        <button type="submit" className="wm-btn-primary" disabled={busy}>
          {busy ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
          {busy ? "Se creează..." : "Creează sursă"}
        </button>
        <button type="button" onClick={() => void handleTestConnection()} className="wm-btn-secondary" disabled={testing || busy}>
          {testing ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
          {testing ? "Se testează..." : "Test Connection"}
        </button>
        <button type="button" onClick={onCancel} className="wm-btn-secondary" disabled={busy}>Anulează</button>
      </div>
    </form>
  );
}
