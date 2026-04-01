"use client";

import { FormEvent, useState } from "react";
import { ExternalLink, Loader2, CheckCircle, XCircle } from "lucide-react";

type ShopifyFormData = {
  name: string;
  shop_url: string;
  api_key: string;
  api_secret: string;
};

export function ShopifySourceForm({
  onSubmit,
  onTestConnection,
  onCancel,
  busy,
}: {
  onSubmit: (data: ShopifyFormData) => void;
  onTestConnection: (data: Pick<ShopifyFormData, "shop_url" | "api_key" | "api_secret">) => Promise<{ success: boolean; message: string }>;
  onCancel: () => void;
  busy: boolean;
}) {
  const [name, setName] = useState("");
  const [shopUrl, setShopUrl] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [apiSecret, setApiSecret] = useState("");
  const [errors, setErrors] = useState<Partial<Record<keyof ShopifyFormData, string>>>({});
  const [testStatus, setTestStatus] = useState<{ success: boolean; message: string } | null>(null);
  const [testing, setTesting] = useState(false);

  function validate(): boolean {
    const next: typeof errors = {};
    if (!name.trim()) next.name = "Numele sursei este obligatoriu.";
    if (!shopUrl.trim()) {
      next.shop_url = "URL-ul magazinului este obligatoriu.";
    } else if (!shopUrl.includes(".myshopify.com") && !shopUrl.includes("shopify")) {
      next.shop_url = "Introdu un URL Shopify valid (ex: my-store.myshopify.com).";
    }
    if (!apiKey.trim()) next.api_key = "API Key este obligatoriu.";
    if (!apiSecret.trim()) next.api_secret = "API Secret este obligatoriu.";
    setErrors(next);
    return Object.keys(next).length === 0;
  }

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!validate()) return;
    onSubmit({ name: name.trim(), shop_url: shopUrl.trim(), api_key: apiKey.trim(), api_secret: apiSecret.trim() });
  }

  async function handleTestConnection() {
    const next: typeof errors = {};
    if (!shopUrl.trim()) next.shop_url = "URL-ul magazinului este obligatoriu.";
    if (!apiKey.trim()) next.api_key = "API Key este obligatoriu.";
    if (!apiSecret.trim()) next.api_secret = "API Secret este obligatoriu.";
    if (Object.keys(next).length > 0) { setErrors(next); return; }
    setTesting(true);
    setTestStatus(null);
    try {
      const result = await onTestConnection({ shop_url: shopUrl.trim(), api_key: apiKey.trim(), api_secret: apiSecret.trim() });
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
        <label htmlFor="sh-name" className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">Source Name</label>
        <input id="sh-name" value={name} onChange={(e) => setName(e.target.value)} placeholder="Ex: Main Shopify Store" className="wm-input" />
        {errors.name ? <p className="mt-1 text-xs text-red-600">{errors.name}</p> : null}
      </div>
      <div>
        <label htmlFor="sh-url" className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">Shop URL</label>
        <input id="sh-url" value={shopUrl} onChange={(e) => setShopUrl(e.target.value)} placeholder="my-store.myshopify.com" className="wm-input" />
        {errors.shop_url ? <p className="mt-1 text-xs text-red-600">{errors.shop_url}</p> : null}
      </div>
      <div>
        <label htmlFor="sh-key" className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">API Key</label>
        <input id="sh-key" value={apiKey} onChange={(e) => setApiKey(e.target.value)} placeholder="shpat_xxxxxxxxxx" className="wm-input" />
        {errors.api_key ? <p className="mt-1 text-xs text-red-600">{errors.api_key}</p> : null}
      </div>
      <div>
        <label htmlFor="sh-secret" className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">API Secret</label>
        <input id="sh-secret" type="password" value={apiSecret} onChange={(e) => setApiSecret(e.target.value)} placeholder="••••••••" className="wm-input" />
        {errors.api_secret ? <p className="mt-1 text-xs text-red-600">{errors.api_secret}</p> : null}
      </div>
      <div className="flex items-center gap-2 text-xs text-slate-500 dark:text-slate-400">
        <ExternalLink className="h-3.5 w-3.5" />
        <a href="https://shopify.dev/docs/apps/auth/admin-app-access-tokens" target="_blank" rel="noopener noreferrer" className="text-indigo-600 hover:underline dark:text-indigo-400">How to get Shopify API credentials</a>
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
