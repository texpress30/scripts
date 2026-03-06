"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";

import { AppShell } from "@/components/AppShell";
import { ProtectedPage } from "@/components/ProtectedPage";
import { apiRequest } from "@/lib/api";

type ExchangeResponse = {
  status: string;
  accessible_customers: string[];
  refresh_token_source?: string;
  refresh_token_updated_at?: string | null;
  message?: string;
};

function OAuthCallbackBody() {
  const searchParams = useSearchParams();
  const [error, setError] = useState("");
  const [result, setResult] = useState<ExchangeResponse | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let ignore = false;
    async function exchange() {
      setLoading(true);
      setError("");
      try {
        const code = searchParams.get("code") ?? "";
        const state = searchParams.get("state") ?? "";
        const payload = await apiRequest<ExchangeResponse>("/integrations/google-ads/oauth/exchange", {
          method: "POST",
          body: JSON.stringify({ code, state }),
        });
        if (!ignore) setResult(payload);
      } catch (err) {
        if (!ignore) setError(err instanceof Error ? err.message : "Google OAuth exchange failed");
      } finally {
        if (!ignore) setLoading(false);
      }
    }

    void exchange();
    return () => {
      ignore = true;
    };
  }, [searchParams]);

  return (
    <>
      {loading ? <p className="text-sm text-slate-600">Finalizăm conectarea Google...</p> : null}
      {error ? <p className="text-sm text-red-600">{error}</p> : null}

      {result ? (
        <article className="wm-card p-4">
          <h2 className="text-base font-semibold text-slate-900">Google conectat cu succes</h2>
          <p className="mt-2 text-sm text-slate-700">Conturi MCC accesibile: {result.accessible_customers.length}</p>
          <p className="mt-2 text-sm text-emerald-700">{result.message ?? "Token-ul Google a fost salvat automat."}</p>
          <p className="mt-2 text-xs text-slate-600">Sursa token: {result.refresh_token_source ?? "database"}</p>
          <p className="mt-1 text-xs text-slate-600">Actualizat la: {result.refresh_token_updated_at ? new Date(result.refresh_token_updated_at).toLocaleString() : "-"}</p>
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

export default function GoogleOAuthCallbackPage() {
  return (
    <ProtectedPage>
      <AppShell title="Google OAuth Callback">
        <Suspense fallback={<p className="text-sm text-slate-600">Pregătim callback-ul OAuth...</p>}>
          <OAuthCallbackBody />
        </Suspense>
      </AppShell>
    </ProtectedPage>
  );
}
