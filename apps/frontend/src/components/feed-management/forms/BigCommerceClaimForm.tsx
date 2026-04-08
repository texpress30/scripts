"use client";

import { FormEvent, useCallback, useEffect, useRef, useState } from "react";
import {
  CheckCircle,
  ExternalLink,
  Loader2,
  RefreshCw,
  Store,
  XCircle,
} from "lucide-react";

import {
  fetchAvailableBigCommerceStores,
  testBigCommerceConnectionByStoreHash,
  type BigCommerceAvailableStore,
  type BigCommerceTestConnectionResponse,
} from "@/lib/hooks/useBigCommerceSource";

/**
 * Dedicated BigCommerce claim form for wizard Step 3.
 *
 * Unlike the Magento form (which collects four OAuth 1.0a credentials in a
 * dedicated input set), BigCommerce installs flow through the merchant's
 * BigCommerce App Marketplace. By the time the agency user lands on this
 * step, the access token has already been stored encrypted-at-rest by the
 * OAuth callback (Task 1) — all we have to do is **claim** one of the
 * unbound stores by binding it to a subaccount + giving it a friendly
 * name and catalog metadata.
 *
 * UX states:
 *
 * 1. **Loading** — fetching ``GET /stores/available``.
 * 2. **Empty** — no stores installed yet → render an inline guide
 *    explaining how the merchant installs the Omarosa app from the BC App
 *    Marketplace, plus a "Reîncarcă" button that re-polls the endpoint.
 * 3. **Stores listed** — radio-button cards, one per available store.
 *    Selecting a card auto-populates the source name input. The user can
 *    then run "Testează conexiunea" (pre-claim probe) before clicking
 *    "Revendică şi creează sursă".
 * 4. **Test result** — success/error banner with store name + currency.
 *
 * Errors are surfaced inline (not via window.alert) so the wizard parent
 * can render its own banner above. The component never persists anything
 * itself — the parent's ``onClaim`` callback is responsible for the
 * actual ``POST /sources/claim`` round-trip.
 */

const AUTO_REFRESH_INTERVAL_MS = 15_000;

export type BigCommerceClaimFormData = {
  store_hash: string;
  source_name: string;
};

export function BigCommerceClaimForm({
  onClaim,
  onCancel,
  busy,
}: {
  onClaim: (data: BigCommerceClaimFormData) => void;
  onCancel: () => void;
  busy: boolean;
}) {
  const [stores, setStores] = useState<BigCommerceAvailableStore[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [selectedHash, setSelectedHash] = useState<string | null>(null);
  const [sourceName, setSourceName] = useState("");
  const [touchedName, setTouchedName] = useState(false);
  const [nameError, setNameError] = useState<string | null>(null);
  const [testing, setTesting] = useState(false);
  const [testStatus, setTestStatus] =
    useState<BigCommerceTestConnectionResponse | null>(null);

  const refreshTimerRef = useRef<number | null>(null);
  const isMountedRef = useRef(true);

  const refresh = useCallback(async () => {
    setLoading(true);
    setLoadError(null);
    try {
      const data = await fetchAvailableBigCommerceStores();
      if (!isMountedRef.current) return;
      setStores(data.stores);
      // Drop selection if the previously-selected store has been claimed
      // by another tab while we were polling.
      if (
        selectedHash !== null &&
        !data.stores.some((s) => s.store_hash === selectedHash)
      ) {
        setSelectedHash(null);
        setTestStatus(null);
      }
    } catch (err) {
      if (!isMountedRef.current) return;
      setLoadError(
        err instanceof Error
          ? err.message
          : "Nu s-a putut încărca lista de magazine BigCommerce.",
      );
    } finally {
      if (isMountedRef.current) setLoading(false);
    }
  }, [selectedHash]);

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

  function handleSelect(hash: string) {
    setSelectedHash(hash);
    setTestStatus(null);
    setNameError(null);
    if (!touchedName || sourceName.trim() === "") {
      setSourceName(`BigCommerce store ${hash}`);
      setTouchedName(false);
    }
  }

  function handleNameChange(value: string) {
    setSourceName(value);
    setTouchedName(true);
    if (value.trim()) setNameError(null);
  }

  async function handleTestConnection() {
    if (!selectedHash) return;
    setTesting(true);
    setTestStatus(null);
    try {
      const result = await testBigCommerceConnectionByStoreHash(selectedHash);
      setTestStatus(result);
    } catch (err) {
      setTestStatus({
        success: false,
        store_name: null,
        domain: null,
        secure_url: null,
        currency: null,
        error:
          err instanceof Error
            ? err.message
            : "Eroare la testarea conexiunii BigCommerce.",
      });
    } finally {
      setTesting(false);
    }
  }

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!selectedHash) return;
    const trimmed = sourceName.trim();
    if (!trimmed) {
      setNameError("Numele sursei este obligatoriu.");
      return;
    }
    onClaim({ store_hash: selectedHash, source_name: trimmed });
  }

  const canSubmit = selectedHash !== null && !busy;

  return (
    <form onSubmit={handleSubmit} className="space-y-5">
      <div>
        <h3 className="text-sm font-medium text-slate-900 dark:text-slate-100">
          Selectează magazinul BigCommerce
        </h3>
        <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
          Sunt afișate doar magazinele care au instalat aplicația Omarosa
          Agency din BigCommerce App Marketplace și nu sunt încă revendicate
          de nici un sub-cont.
        </p>
      </div>

      {loading ? (
        <BigCommerceLoadingState />
      ) : loadError ? (
        <BigCommerceErrorState message={loadError} onRetry={() => void refresh()} />
      ) : stores.length === 0 ? (
        <BigCommerceEmptyState onRetry={() => void refresh()} />
      ) : (
        <BigCommerceStoreList
          stores={stores}
          selectedHash={selectedHash}
          onSelect={handleSelect}
          onRetry={() => void refresh()}
        />
      )}

      {selectedHash !== null ? (
        <>
          <div>
            <label
              htmlFor="bc-source-name"
              className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300"
            >
              Nume sursă
            </label>
            <input
              id="bc-source-name"
              value={sourceName}
              onChange={(e) => handleNameChange(e.target.value)}
              placeholder="Ex: Main BigCommerce Store"
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
                    ? `Conectat: ${testStatus.store_name ?? "BigCommerce store"}`
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
          className="wm-btn-primary"
          disabled={!canSubmit}
        >
          {busy ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
          {busy ? "Se revendică..." : "Revendică şi creează sursă"}
        </button>
        <button
          type="button"
          onClick={() => void handleTestConnection()}
          className="wm-btn-secondary"
          disabled={selectedHash === null || testing || busy}
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

// ---------------------------------------------------------------------------
// State subcomponents
// ---------------------------------------------------------------------------

function BigCommerceLoadingState() {
  return (
    <div
      role="status"
      aria-live="polite"
      className="flex items-center gap-3 rounded-lg border border-slate-200 bg-slate-50 p-4 text-sm text-slate-600 dark:border-slate-700 dark:bg-slate-900/40 dark:text-slate-300"
    >
      <Loader2 className="h-4 w-4 animate-spin" />
      Se încarcă magazinele BigCommerce disponibile…
    </div>
  );
}

function BigCommerceErrorState({
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

function BigCommerceEmptyState({ onRetry }: { onRetry: () => void }) {
  return (
    <div
      data-testid="bc-empty-state"
      className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800 dark:border-amber-800 dark:bg-amber-900/20 dark:text-amber-200"
    >
      <p className="font-medium">
        Nu există magazine BigCommerce disponibile pentru revendicare.
      </p>
      <p className="mt-1 text-xs opacity-90">
        Clientul trebuie să instaleze aplicația Omarosa Agency din
        BigCommerce App Marketplace. După instalare, magazinul va apărea
        automat în lista de mai jos (verificăm la fiecare 15 secunde).
      </p>
      <details className="mt-3 text-xs">
        <summary className="flex cursor-pointer items-center gap-1 hover:opacity-80">
          <ExternalLink className="h-3.5 w-3.5" />
          Cum instalează clientul aplicația
        </summary>
        <ol className="mt-2 list-decimal space-y-1 pl-5 leading-relaxed">
          <li>
            Clientul deschide{" "}
            <strong>BigCommerce Admin → Apps → Marketplace</strong>.
          </li>
          <li>
            Caută <strong>„Omarosa Agency"</strong> sau accesează linkul direct
            către aplicația noastră.
          </li>
          <li>
            Click pe <strong>Install</strong> și acceptă permisiunile.
          </li>
          <li>
            Revii aici — magazinul va apărea automat în maxim 15 secunde.
          </li>
        </ol>
      </details>
      <button
        type="button"
        onClick={onRetry}
        className="mt-3 inline-flex items-center gap-1 rounded border border-amber-300 bg-white/40 px-2 py-1 text-xs font-medium hover:bg-white dark:border-amber-700 dark:bg-amber-950/40 dark:hover:bg-amber-900/60"
      >
        <RefreshCw className="h-3 w-3" />
        Reîncarcă acum
      </button>
    </div>
  );
}

function BigCommerceStoreList({
  stores,
  selectedHash,
  onSelect,
  onRetry,
}: {
  stores: BigCommerceAvailableStore[];
  selectedHash: string | null;
  onSelect: (hash: string) => void;
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
        aria-label="Magazine BigCommerce disponibile"
        className="space-y-2"
      >
        {stores.map((store) => {
          const isSelected = store.store_hash === selectedHash;
          return (
            <label
              key={store.store_hash}
              className={`flex cursor-pointer items-start gap-3 rounded-lg border p-3 transition ${
                isSelected
                  ? "border-indigo-500 bg-indigo-50 ring-2 ring-indigo-500/20 dark:border-indigo-400 dark:bg-indigo-950/30 dark:ring-indigo-400/20"
                  : "border-slate-200 bg-white hover:border-slate-300 hover:bg-slate-50 dark:border-slate-700 dark:bg-slate-900 dark:hover:border-slate-600 dark:hover:bg-slate-800"
              }`}
            >
              <input
                type="radio"
                name="bc-store-hash"
                value={store.store_hash}
                checked={isSelected}
                onChange={() => onSelect(store.store_hash)}
                className="mt-1 h-4 w-4 text-indigo-600"
              />
              <Store className="mt-0.5 h-5 w-5 flex-shrink-0 text-blue-600 dark:text-blue-400" />
              <div className="min-w-0 flex-1">
                <p className="font-medium text-slate-900 dark:text-slate-100">
                  stores/{store.store_hash}
                </p>
                <p className="mt-0.5 text-xs text-slate-500 dark:text-slate-400">
                  {store.user_email
                    ? `Instalat de ${store.user_email}`
                    : "Instalat de utilizator necunoscut"}
                  {store.installed_at
                    ? ` · ${formatInstalledAt(store.installed_at)}`
                    : null}
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
