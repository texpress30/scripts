"use client";

import { FormEvent, useCallback, useEffect, useRef, useState } from "react";
import {
  CheckCircle,
  ExternalLink,
  Loader2,
  RefreshCw,
  ShoppingBag,
  XCircle,
} from "lucide-react";

import {
  fetchAvailableShopifyStores,
  testShopifyConnectionByShopDomain,
  type ShopifyAvailableStore,
  type ShopifyPreClaimTestResponse,
} from "@/lib/hooks/useShopifySource";

/**
 * Dedicated Shopify claim form for wizard Step 3.
 *
 * Mirrors ``BigCommerceClaimForm`` — the merchant installs VOXEL from
 * the Shopify App Store, our OAuth callback stores the access token
 * encrypted-at-rest keyed by ``shop_domain`` without creating a
 * feed_sources row. The agency user lands here, picks one of the
 * installed-but-unbound shops, and binds it to a subaccount.
 *
 * UX states:
 *
 * 1. **Loading** — fetching ``GET /stores/available``.
 * 2. **Empty** — no shops installed yet → inline guide explaining how
 *    the merchant installs VOXEL from the Shopify App Store, with an
 *    auto-poll every 15 seconds so the list refreshes without F5.
 * 3. **Shops listed** — radio-button cards, one per available shop.
 *    Selecting a card auto-populates the source name input. The user
 *    can then run "Testează conexiunea" (pre-claim probe) before
 *    clicking "Revendică și creează sursă".
 * 4. **Manual fallback** — a small link underneath the list lets the
 *    agency admin fall back to the legacy Shop-URL form for edge cases
 *    (merchant without App Store access, re-authorisation, etc.).
 *
 * Errors surface inline (not via ``window.alert``) so the wizard parent
 * can render its own banner above. The component never persists
 * anything itself — the parent's ``onClaim`` callback owns the
 * ``POST /sources/claim`` round-trip.
 */

const AUTO_REFRESH_INTERVAL_MS = 15_000;
const SHOPIFY_APP_STORE_URL = "https://apps.shopify.com/omarosa-agency";

export type ShopifyClaimFormData = {
  shop_domain: string;
  source_name: string;
};

export function ShopifyClaimForm({
  onClaim,
  onFallbackManual,
  onCancel,
  busy,
}: {
  onClaim: (data: ShopifyClaimFormData) => void;
  /** Called when the user clicks the "Conectează manual" link to
   *  switch back to the legacy Shop-URL form. Optional — if omitted
   *  the fallback link is hidden. */
  onFallbackManual?: () => void;
  onCancel: () => void;
  busy: boolean;
}) {
  const [stores, setStores] = useState<ShopifyAvailableStore[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [selectedShop, setSelectedShop] = useState<string | null>(null);
  const [sourceName, setSourceName] = useState("");
  const [touchedName, setTouchedName] = useState(false);
  const [nameError, setNameError] = useState<string | null>(null);
  const [testing, setTesting] = useState(false);
  const [testStatus, setTestStatus] =
    useState<ShopifyPreClaimTestResponse | null>(null);

  const refreshTimerRef = useRef<number | null>(null);
  const isMountedRef = useRef(true);

  const refresh = useCallback(async () => {
    setLoading(true);
    setLoadError(null);
    try {
      const data = await fetchAvailableShopifyStores();
      if (!isMountedRef.current) return;
      setStores(data.stores);
      // Drop selection if the previously-selected shop has been claimed
      // by another tab while we were polling.
      if (
        selectedShop !== null &&
        !data.stores.some((s) => s.shop_domain === selectedShop)
      ) {
        setSelectedShop(null);
        setTestStatus(null);
      }
    } catch (err) {
      if (!isMountedRef.current) return;
      setLoadError(
        err instanceof Error
          ? err.message
          : "Nu s-a putut încărca lista de magazine Shopify.",
      );
    } finally {
      if (isMountedRef.current) setLoading(false);
    }
  }, [selectedShop]);

  // Initial load.
  useEffect(() => {
    isMountedRef.current = true;
    void refresh();
    return () => {
      isMountedRef.current = false;
      if (refreshTimerRef.current !== null) {
        window.clearInterval(refreshTimerRef.current);
        refreshTimerRef.current = null;
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Auto-refresh while the empty state is showing — the merchant may
  // install the app at any moment, and this is a less jarring UX than
  // forcing the user to F5.
  useEffect(() => {
    if (refreshTimerRef.current !== null) {
      window.clearInterval(refreshTimerRef.current);
      refreshTimerRef.current = null;
    }
    if (!loading && stores.length === 0 && !loadError) {
      refreshTimerRef.current = window.setInterval(() => {
        void refresh();
      }, AUTO_REFRESH_INTERVAL_MS);
    }
    return () => {
      if (refreshTimerRef.current !== null) {
        window.clearInterval(refreshTimerRef.current);
        refreshTimerRef.current = null;
      }
    };
  }, [loading, stores.length, loadError, refresh]);

  function handleSelect(shop: string) {
    setSelectedShop(shop);
    setTestStatus(null);
    setNameError(null);
    if (!touchedName || sourceName.trim() === "") {
      setSourceName(`Shopify store ${shop}`);
      setTouchedName(false);
    }
  }

  function handleNameChange(value: string) {
    setSourceName(value);
    setTouchedName(true);
    if (value.trim()) setNameError(null);
  }

  async function handleTestConnection() {
    if (!selectedShop) return;
    setTesting(true);
    setTestStatus(null);
    try {
      const result = await testShopifyConnectionByShopDomain(selectedShop);
      setTestStatus(result);
    } catch (err) {
      setTestStatus({
        success: false,
        store_name: null,
        domain: null,
        currency: null,
        error:
          err instanceof Error
            ? err.message
            : "Eroare la testarea conexiunii Shopify.",
      });
    } finally {
      setTesting(false);
    }
  }

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!selectedShop) return;
    const trimmed = sourceName.trim();
    if (!trimmed) {
      setNameError("Numele sursei este obligatoriu.");
      return;
    }
    onClaim({ shop_domain: selectedShop, source_name: trimmed });
  }

  const canSubmit = selectedShop !== null && !busy;

  return (
    <form onSubmit={handleSubmit} className="space-y-5">
      <div>
        <h3 className="text-sm font-medium text-slate-900 dark:text-slate-100">
          Selectează magazinul Shopify
        </h3>
        <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
          Sunt afișate doar magazinele care au instalat aplicația Omarosa
          Agency din Shopify App Store și nu sunt încă revendicate de nici
          un sub-cont.
        </p>
      </div>

      {loading ? (
        <ShopifyLoadingState />
      ) : loadError ? (
        <ShopifyErrorState message={loadError} onRetry={() => void refresh()} />
      ) : stores.length === 0 ? (
        <ShopifyEmptyState onRetry={() => void refresh()} />
      ) : (
        <ShopifyStoreList
          stores={stores}
          selectedShop={selectedShop}
          onSelect={handleSelect}
          onRetry={() => void refresh()}
        />
      )}

      {selectedShop !== null ? (
        <>
          <div>
            <label
              htmlFor="shopify-source-name"
              className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300"
            >
              Nume sursă
            </label>
            <input
              id="shopify-source-name"
              value={sourceName}
              onChange={(e) => handleNameChange(e.target.value)}
              placeholder="Ex: Main Shopify Store"
              className="wm-input"
              autoComplete="off"
            />
            {nameError ? (
              <p className="mt-1 text-xs text-red-600">{nameError}</p>
            ) : (
              <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
                Numele afișat în lista de surse — îl poți schimba ulterior.
              </p>
            )}
          </div>

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
                <p className="font-medium">
                  {testStatus.success
                    ? `Conectat: ${testStatus.store_name ?? "Shopify store"}`
                    : (testStatus.error ?? "Nu s-a putut valida conexiunea.")}
                </p>
                {testStatus.success ? (
                  <p className="mt-0.5 text-xs opacity-80">
                    {testStatus.domain ? <span>{testStatus.domain}</span> : null}
                    {testStatus.domain && testStatus.currency ? " · " : null}
                    {testStatus.currency ? <span>{testStatus.currency}</span> : null}
                  </p>
                ) : null}
              </div>
            </div>
          ) : null}
        </>
      ) : null}

      <div className="flex flex-wrap items-center gap-3 pt-2">
        <button
          type="submit"
          className="wm-btn-primary gap-2"
          style={{ backgroundColor: canSubmit ? "#95BF47" : undefined, borderColor: "#95BF47" }}
          disabled={!canSubmit}
        >
          {busy ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
          {busy ? "Se revendică..." : "Revendică și creează sursă"}
        </button>
        <button
          type="button"
          onClick={() => void handleTestConnection()}
          className="wm-btn-secondary"
          disabled={selectedShop === null || testing || busy}
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

      {onFallbackManual ? (
        <div className="border-t border-slate-200 pt-3 dark:border-slate-700">
          <button
            type="button"
            onClick={onFallbackManual}
            className="text-xs text-slate-500 underline-offset-2 hover:text-slate-700 hover:underline dark:text-slate-400 dark:hover:text-slate-200"
            disabled={busy}
          >
            Magazinul nu apare? Conectează manual →
          </button>
        </div>
      ) : null}
    </form>
  );
}

// ---------------------------------------------------------------------------
// State subcomponents
// ---------------------------------------------------------------------------

function ShopifyLoadingState() {
  return (
    <div
      role="status"
      aria-live="polite"
      className="flex items-center gap-3 rounded-lg border border-slate-200 bg-slate-50 p-4 text-sm text-slate-600 dark:border-slate-700 dark:bg-slate-900/40 dark:text-slate-300"
    >
      <Loader2 className="h-4 w-4 animate-spin" />
      Se încarcă magazinele Shopify disponibile…
    </div>
  );
}

function ShopifyErrorState({
  message,
  onRetry,
}: {
  message: string;
  onRetry: () => void;
}) {
  return (
    <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700 dark:border-red-800 dark:bg-red-900/20 dark:text-red-400">
      <div className="flex items-start gap-2">
        <XCircle className="mt-0.5 h-4 w-4 flex-shrink-0" />
        <div className="flex-1">
          <p className="font-medium">Nu s-au putut încărca magazinele.</p>
          <p className="mt-0.5 text-xs opacity-90">{message}</p>
          <button
            type="button"
            onClick={onRetry}
            className="mt-2 inline-flex items-center gap-1 rounded border border-red-200 px-2 py-1 text-xs font-medium hover:bg-red-100 dark:border-red-800 dark:hover:bg-red-900/40"
          >
            <RefreshCw className="h-3 w-3" />
            Reîncearcă
          </button>
        </div>
      </div>
    </div>
  );
}

function ShopifyEmptyState({ onRetry }: { onRetry: () => void }) {
  return (
    <div
      data-testid="shopify-empty-state"
      className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800 dark:border-amber-800 dark:bg-amber-900/20 dark:text-amber-200"
    >
      <p className="font-medium">
        Nu există magazine Shopify disponibile pentru revendicare.
      </p>
      <p className="mt-1 text-xs opacity-90">
        Clientul trebuie să instaleze aplicația Omarosa Agency din Shopify
        App Store. După instalare, magazinul va apărea automat în lista de
        mai jos (verificăm la fiecare 15 secunde).
      </p>
      <div className="mt-3 flex flex-wrap gap-2">
        <a
          href={SHOPIFY_APP_STORE_URL}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-1 rounded border border-amber-300 bg-white/40 px-2 py-1 text-xs font-medium hover:bg-white dark:border-amber-700 dark:bg-amber-950/40 dark:hover:bg-amber-900/60"
        >
          <ExternalLink className="h-3 w-3" />
          Deschide Shopify App Store
        </a>
        <button
          type="button"
          onClick={onRetry}
          className="inline-flex items-center gap-1 rounded border border-amber-300 bg-white/40 px-2 py-1 text-xs font-medium hover:bg-white dark:border-amber-700 dark:bg-amber-950/40 dark:hover:bg-amber-900/60"
        >
          <RefreshCw className="h-3 w-3" />
          Reîncarcă acum
        </button>
      </div>
      <details className="mt-3 text-xs">
        <summary className="flex cursor-pointer items-center gap-1 hover:opacity-80">
          <ExternalLink className="h-3.5 w-3.5" />
          Cum instalează clientul aplicația
        </summary>
        <ol className="mt-2 list-decimal space-y-1 pl-5 leading-relaxed">
          <li>
            Clientul deschide{" "}
            <strong>Shopify Admin → Apps → Shopify App Store</strong>.
          </li>
          <li>
            Caută <strong>„Omarosa Agency"</strong> sau folosește linkul
            direct de mai sus.
          </li>
          <li>
            Click pe <strong>Install</strong> și acceptă permisiunile.
          </li>
          <li>
            Revii aici — magazinul va apărea automat în maxim 15 secunde.
          </li>
        </ol>
      </details>
    </div>
  );
}

function ShopifyStoreList({
  stores,
  selectedShop,
  onSelect,
  onRetry,
}: {
  stores: ShopifyAvailableStore[];
  selectedShop: string | null;
  onSelect: (shop: string) => void;
  onRetry: () => void;
}) {
  return (
    <div>
      <div className="mb-2 flex items-center justify-between">
        <p className="text-xs text-slate-500 dark:text-slate-400">
          {stores.length}{" "}
          {stores.length === 1 ? "magazin disponibil" : "magazine disponibile"}
        </p>
        <button
          type="button"
          onClick={onRetry}
          className="inline-flex items-center gap-1 text-xs text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-300"
        >
          <RefreshCw className="h-3 w-3" />
          Reîncarcă
        </button>
      </div>
      <div
        role="radiogroup"
        aria-label="Magazine Shopify disponibile"
        className="space-y-2"
      >
        {stores.map((store) => {
          const isSelected = store.shop_domain === selectedShop;
          return (
            <label
              key={store.shop_domain}
              className={`flex cursor-pointer items-start gap-3 rounded-lg border p-3 transition ${
                isSelected
                  ? "border-indigo-500 bg-indigo-50 ring-2 ring-indigo-500/20 dark:border-indigo-400 dark:bg-indigo-950/30 dark:ring-indigo-400/20"
                  : "border-slate-200 bg-white hover:border-slate-300 hover:bg-slate-50 dark:border-slate-700 dark:bg-slate-900 dark:hover:border-slate-600 dark:hover:bg-slate-800"
              }`}
            >
              <input
                type="radio"
                name="shopify-shop-domain"
                value={store.shop_domain}
                checked={isSelected}
                onChange={() => onSelect(store.shop_domain)}
                className="mt-1 h-4 w-4 text-indigo-600"
              />
              <ShoppingBag className="mt-0.5 h-5 w-5 flex-shrink-0 text-green-600 dark:text-green-400" />
              <div className="min-w-0 flex-1">
                <p className="font-medium text-slate-900 dark:text-slate-100">
                  {store.shop_domain}
                </p>
                <p className="mt-0.5 text-xs text-slate-500 dark:text-slate-400">
                  {store.installed_at
                    ? `Instalat ${formatInstalledAt(store.installed_at)}`
                    : "Instalat"}
                </p>
                {store.scope ? (
                  <p
                    className="mt-0.5 truncate text-xs text-slate-400 dark:text-slate-500"
                    title={store.scope}
                  >
                    {store.scope}
                  </p>
                ) : null}
              </div>
            </label>
          );
        })}
      </div>
    </div>
  );
}

function formatInstalledAt(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString();
}
