"use client";

import { FormEvent, useMemo, useState } from "react";
import { ExternalLink, Loader2, ShoppingBag } from "lucide-react";

export type ShopifyConnectFormData = {
  name: string;
  shop_domain: string;
};

function normalizeShopDomain(input: string): string {
  let value = input.trim().toLowerCase();
  if (!value) return "";
  // Strip protocol
  value = value.replace(/^https?:\/\//, "");
  // Strip trailing slash
  value = value.replace(/\/+$/, "");
  // Auto-append .myshopify.com if user gave only the handle
  if (value && !value.includes(".")) {
    value = `${value}.myshopify.com`;
  }
  return value;
}

function isValidShopDomain(value: string): boolean {
  return /^[a-z0-9][a-z0-9-]*\.myshopify\.com$/.test(value);
}

export function ShopifySourceForm({
  onConnect,
  onCancel,
  busy,
}: {
  onConnect: (data: ShopifyConnectFormData) => void;
  onCancel: () => void;
  busy: boolean;
}) {
  const [name, setName] = useState("");
  const [shopUrl, setShopUrl] = useState("");
  const [errors, setErrors] = useState<Partial<Record<"name" | "shop_domain", string>>>({});

  const normalizedShop = useMemo(() => normalizeShopDomain(shopUrl), [shopUrl]);
  const formIsValid = name.trim().length >= 2 && isValidShopDomain(normalizedShop);

  function validate(): boolean {
    const next: typeof errors = {};
    const trimmedName = name.trim();
    if (!trimmedName) {
      next.name = "Numele sursei este obligatoriu.";
    } else if (trimmedName.length < 2) {
      next.name = "Numele trebuie să aibă cel puțin 2 caractere.";
    }
    if (!shopUrl.trim()) {
      next.shop_domain = "URL-ul magazinului este obligatoriu.";
    } else if (!isValidShopDomain(normalizedShop)) {
      next.shop_domain = "Introdu un URL Shopify valid (ex: my-store.myshopify.com).";
    }
    setErrors(next);
    return Object.keys(next).length === 0;
  }

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!validate()) return;
    onConnect({ name: name.trim(), shop_domain: normalizedShop });
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-5">
      <div>
        <label htmlFor="sh-name" className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">
          Source Name
        </label>
        <input
          id="sh-name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Ex: Main Shopify Store"
          className="wm-input"
          autoComplete="off"
        />
        {errors.name ? <p className="mt-1 text-xs text-red-600">{errors.name}</p> : null}
      </div>

      <div>
        <label htmlFor="sh-url" className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">
          Shop URL
        </label>
        <input
          id="sh-url"
          value={shopUrl}
          onChange={(e) => setShopUrl(e.target.value)}
          onBlur={() => {
            if (shopUrl.trim()) setShopUrl(normalizeShopDomain(shopUrl));
          }}
          placeholder="store-name.myshopify.com"
          className="wm-input"
          autoComplete="off"
          spellCheck={false}
        />
        {errors.shop_domain ? (
          <p className="mt-1 text-xs text-red-600">{errors.shop_domain}</p>
        ) : shopUrl && normalizedShop && normalizedShop !== shopUrl.trim().toLowerCase() ? (
          <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">Va fi folosit: {normalizedShop}</p>
        ) : null}
      </div>

      <details className="text-xs text-slate-500 dark:text-slate-400">
        <summary className="flex cursor-pointer items-center gap-1 hover:text-slate-700 dark:hover:text-slate-300">
          <ExternalLink className="h-3.5 w-3.5" />
          Cum funcționează conectarea?
        </summary>
        <p className="mt-2 max-w-prose leading-relaxed">
          Vei fi redirecționat la Shopify pentru a autoriza accesul la produsele magazinului tău. După aprobare, te vom
          aduce automat înapoi în platformă cu sursa conectată și gata de import.
        </p>
      </details>

      <div className="flex flex-wrap items-center gap-3 pt-2">
        <button
          type="submit"
          className="wm-btn-primary gap-2"
          style={{ backgroundColor: formIsValid && !busy ? "#95BF47" : undefined, borderColor: "#95BF47" }}
          disabled={busy || !formIsValid}
        >
          {busy ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <ShoppingBag className="h-4 w-4" />
          )}
          {busy ? "Se conectează..." : "Conectează la Shopify"}
        </button>
        <button type="button" onClick={onCancel} className="wm-btn-secondary" disabled={busy}>
          Anulează
        </button>
      </div>
    </form>
  );
}
