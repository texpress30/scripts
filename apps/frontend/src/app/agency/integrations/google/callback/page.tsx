"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";

import { AppShell } from "@/components/AppShell";
import { ProtectedPage } from "@/components/ProtectedPage";
import { apiRequest } from "@/lib/api";

type ExchangeResponse = {
  status: string;
  refresh_token: string;
  accessible_customers: string[];
  persist_instruction: string;
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
          <p className="mt-2 text-xs text-amber-700">{result.persist_instruction}</p>
          <pre className="mt-3 overflow-x-auto rounded bg-slate-900 p-3 text-xs text-slate-100">
{`GOOGLE_ADS_REFRESH_TOKEN=${result.refresh_token}`}
          </pre>
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
