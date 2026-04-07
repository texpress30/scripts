"use client";

import React, { Suspense, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Loader2 } from "lucide-react";

import { AppShell } from "@/components/AppShell";
import { ProtectedPage } from "@/components/ProtectedPage";
import { apiRequest } from "@/lib/api";

type CompleteOAuthResponse = {
  id: string;
  connection_status: string;
  shop_domain: string | null;
};

type StoredContext = {
  source_id: string;
  client_id: number;
  shop_domain?: string;
  state?: string | null;
  return_path?: string;
};

const STORAGE_KEY = "shopify_oauth_context";
const DEFAULT_RETURN_PATH = "/agency/feed-management/sources";

function readStoredContext(): StoredContext | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as StoredContext;
    if (!parsed.source_id || !parsed.client_id) return null;
    return parsed;
  } catch {
    return null;
  }
}

function clearStoredContext() {
  if (typeof window === "undefined") return;
  sessionStorage.removeItem(STORAGE_KEY);
}

function ShopifyOAuthCallbackBody() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const replace = router.replace;
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [sessionExpired, setSessionExpired] = useState(false);

  const providerError = searchParams.get("error") ?? "";
  const errorDescription = searchParams.get("error_description") ?? "";
  const code = searchParams.get("code") ?? "";
  const shop = searchParams.get("shop") ?? "";
  const urlState = searchParams.get("state") ?? "";

  useEffect(() => {
    let ignore = false;

    async function run() {
      setLoading(true);
      setError("");
      setSuccess("");
      setSessionExpired(false);

      if (providerError) {
        const details = [providerError, errorDescription].filter((item) => item.trim() !== "").join(" · ");
        if (!ignore) {
          setError(`Shopify OAuth a returnat o eroare: ${details || providerError}`);
          setLoading(false);
        }
        return;
      }

      if (!code || !shop || !urlState) {
        if (!ignore) {
          setError("Parametrii OAuth lipsesc din callback (code/shop/state).");
          setLoading(false);
        }
        return;
      }

      const ctx = readStoredContext();
      if (!ctx) {
        if (!ignore) {
          setSessionExpired(true);
          setError("Sesiune expirată — reia procesul de la Add New Source.");
          setLoading(false);
        }
        return;
      }

      try {
        const response = await apiRequest<CompleteOAuthResponse>(
          `/subaccount/${ctx.client_id}/feed-sources/${ctx.source_id}/complete-oauth`,
          {
            method: "POST",
            body: JSON.stringify({ code, state: urlState, shop }),
          },
        );

        clearStoredContext();
        if (!ignore) {
          setSuccess(
            response.connection_status === "connected"
              ? "Conectarea la Shopify a fost finalizată cu succes."
              : "Conectarea s-a finalizat.",
          );
          setLoading(false);
          const returnPath = ctx.return_path ?? DEFAULT_RETURN_PATH;
          window.setTimeout(() => {
            replace(`${returnPath}?shopify_connected=1`);
          }, 800);
        }
      } catch (err) {
        if (!ignore) {
          setError(err instanceof Error ? err.message : "Schimbul de token Shopify a eșuat.");
          setLoading(false);
        }
      }
    }

    void run();

    return () => {
      ignore = true;
    };
  }, [replace, providerError, errorDescription, code, shop, urlState]);

  return (
    <div className="max-w-xl">
      {loading ? (
        <div className="flex items-center gap-2 text-sm text-slate-600 dark:text-slate-300">
          <Loader2 className="h-4 w-4 animate-spin" />
          Finalizăm conectarea Shopify...
        </div>
      ) : null}

      {success ? (
        <div className="rounded-lg border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-700 dark:border-emerald-800 dark:bg-emerald-900/20 dark:text-emerald-400">
          {success}
          <p className="mt-1 text-xs text-emerald-600 dark:text-emerald-400">
            Te redirecționăm către lista de surse...
          </p>
        </div>
      ) : null}

      {error ? (
        <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700 dark:border-red-800 dark:bg-red-900/20 dark:text-red-400">
          <p className="font-medium">Conectarea a eșuat</p>
          <p className="mt-1">{error}</p>
          <div className="mt-3 flex gap-2">
            {sessionExpired ? (
              <Link href="/agency/feed-management/sources/new" className="wm-btn-primary">
                Reia procesul
              </Link>
            ) : (
              <Link href="/agency/feed-management/sources/new" className="wm-btn-secondary">
                Încearcă din nou
              </Link>
            )}
            <Link href="/agency/feed-management/sources" className="wm-btn-secondary">
              Înapoi la surse
            </Link>
          </div>
        </div>
      ) : null}
    </div>
  );
}

export default function ShopifyOAuthCallbackPage() {
  return (
    <ProtectedPage>
      <AppShell title="Shopify OAuth Callback">
        <Suspense fallback={<p className="text-sm text-slate-600">Pregătim callback-ul Shopify...</p>}>
          <ShopifyOAuthCallbackBody />
        </Suspense>
      </AppShell>
    </ProtectedPage>
  );
}
