"use client";

import React from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";

import { AppShell } from "@/components/AppShell";
import { ProtectedPage } from "@/components/ProtectedPage";
import { apiRequest } from "@/lib/api";

type MetaExchangeResponse = {
  status?: string;
  message?: string;
  token_source?: string;
  token_updated_at?: string | null;
  token_expires_at?: string | null;
  oauth_configured?: boolean;
};

function formatDate(value?: string | null): string {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString();
}

function MetaOAuthCallbackBody() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const [error, setError] = useState("");
  const [result, setResult] = useState<MetaExchangeResponse | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let ignore = false;

    async function exchange() {
      setLoading(true);
      setError("");

      const providerError = searchParams.get("error") ?? "";
      const providerErrorReason = searchParams.get("error_reason") ?? "";
      const providerErrorDescription = searchParams.get("error_description") ?? "";
      if (providerError) {
        const messageParts = [providerError, providerErrorReason, providerErrorDescription].filter((item) => item.trim() !== "");
        if (!ignore) {
          setError(`Meta OAuth error: ${messageParts.join(" - ") || "authorization_failed"}`);
          setLoading(false);
        }
        return;
      }

      const code = searchParams.get("code") ?? "";
      const state = searchParams.get("state") ?? "";
      if (!code || !state) {
        if (!ignore) {
          setError("Meta OAuth callback invalid: lipsesc parametrii code/state.");
          setLoading(false);
        }
        return;
      }

      try {
        const payload = await apiRequest<MetaExchangeResponse>("/integrations/meta-ads/oauth/exchange", {
          method: "POST",
          body: JSON.stringify({ code, state }),
        });
        if (!ignore) {
          setResult(payload);
        }
      } catch (err) {
        if (!ignore) {
          setError(err instanceof Error ? err.message : "Meta OAuth exchange failed");
        }
      } finally {
        if (!ignore) {
          setLoading(false);
        }
      }
    }

    void exchange();
    return () => {
      ignore = true;
    };
  }, [searchParams]);

  useEffect(() => {
    if (!result) return;
    const timer = setTimeout(() => {
      router.replace("/agency/integrations?meta_connected=1");
    }, 1500);
    return () => clearTimeout(timer);
  }, [result, router]);

  return (
    <>
      {loading ? <p className="text-sm text-slate-600">Finalizăm conectarea Meta Ads...</p> : null}
      {error ? <p className="text-sm text-red-600">{error}</p> : null}

      {result ? (
        <article className="wm-card p-4">
          <h2 className="text-base font-semibold text-slate-900">Meta Ads conectat cu succes</h2>
          <p className="mt-2 text-sm text-emerald-700">{result.message ?? "Token-ul Meta a fost salvat securizat."}</p>
          <p className="mt-2 text-xs text-slate-600">Sursa token: {result.token_source ?? "database"}</p>
          <p className="mt-1 text-xs text-slate-600">Actualizat la: {formatDate(result.token_updated_at)}</p>
          <p className="mt-1 text-xs text-slate-600">Expirare token: {formatDate(result.token_expires_at)}</p>
          <div className="mt-4">
            <Link href="/agency/integrations" className="text-sm text-indigo-600 hover:underline">
              Înapoi la Integrations
            </Link>
          </div>
        </article>
      ) : null}
    </>
  );
}

export default function MetaOAuthCallbackPage() {
  return (
    <ProtectedPage>
      <AppShell title="Meta OAuth Callback">
        <Suspense fallback={<p className="text-sm text-slate-600">Pregătim callback-ul OAuth...</p>}>
          <MetaOAuthCallbackBody />
        </Suspense>
      </AppShell>
    </ProtectedPage>
  );
}
