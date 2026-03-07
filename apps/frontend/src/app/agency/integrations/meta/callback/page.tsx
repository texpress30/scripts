"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import React, { Suspense, useEffect, useState } from "react";

import { AppShell } from "@/components/AppShell";
import { ProtectedPage } from "@/components/ProtectedPage";
import { apiRequest } from "@/lib/api";

type MetaExchangeResponse = {
  status?: string;
  message?: string;
  token_source?: string;
  provider?: string;
};

function CallbackBody() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState<MetaExchangeResponse | null>(null);

  useEffect(() => {
    let ignore = false;

    async function run() {
      setLoading(true);
      setError("");
      setSuccess(null);

      const providerError = searchParams.get("error");
      const errorReason = searchParams.get("error_reason");
      const errorDescription = searchParams.get("error_description");
      if (providerError) {
        const parts = [providerError, errorReason, errorDescription].filter(Boolean);
        if (!ignore) {
          setError(`Meta OAuth error: ${parts.join(" | ")}`);
          setLoading(false);
        }
        return;
      }

      const code = (searchParams.get("code") || "").trim();
      const state = (searchParams.get("state") || "").trim();
      if (!code || !state) {
        if (!ignore) {
          setError("Callback invalid: lipsesc code/state pentru Meta OAuth exchange.");
          setLoading(false);
        }
        return;
      }

      try {
        const payload = await apiRequest<MetaExchangeResponse>("/integrations/meta-ads/oauth/exchange", {
          method: "POST",
          body: JSON.stringify({ code, state }),
        });
        if (ignore) return;
        setSuccess(payload);
        setLoading(false);
        window.setTimeout(() => {
          router.replace("/agency/integrations?meta_connected=1");
        }, 1000);
      } catch (err) {
        if (!ignore) {
          setError(err instanceof Error ? err.message : "Meta OAuth exchange failed");
          setLoading(false);
        }
      }
    }

    void run();
    return () => {
      ignore = true;
    };
  }, [router, searchParams]);

  return (
    <>
      {loading ? <p className="text-sm text-slate-600">Finalizăm conectarea Meta...</p> : null}
      {error ? <p className="text-sm text-red-600">{error}</p> : null}
      {success ? (
        <article className="wm-card p-4">
          <h2 className="text-base font-semibold text-slate-900">Meta conectat cu succes</h2>
          <p className="mt-2 text-sm text-emerald-700">{success.message || "Token-ul Meta a fost salvat automat."}</p>
          <p className="mt-2 text-xs text-slate-600">Token source: {success.token_source || "database"}</p>
          <p className="mt-1 text-xs text-slate-500">Redirecționare către Integrations...</p>
          <div className="mt-3">
            <Link href="/agency/integrations?meta_connected=1" className="text-sm text-indigo-600 hover:underline">
              Mergi acum la Integrations
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
        <Suspense fallback={<p className="text-sm text-slate-600">Pregătim callback-ul Meta OAuth...</p>}>
          <CallbackBody />
        </Suspense>
      </AppShell>
    </ProtectedPage>
  );
}
