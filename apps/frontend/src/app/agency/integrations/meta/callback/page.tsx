"use client";

import React, { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";

import { AppShell } from "@/components/AppShell";
import { ProtectedPage } from "@/components/ProtectedPage";
import { apiRequest } from "@/lib/api";

type MetaExchangeResponse = {
  status?: string;
  provider?: string;
  message?: string;
};

function MetaOAuthCallbackBody() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const replace = router.replace;
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  const providerError = searchParams.get("error") ?? "";
  const errorReason = searchParams.get("error_reason") ?? "";
  const errorDescription = searchParams.get("error_description") ?? "";
  const code = searchParams.get("code") ?? "";
  const state = searchParams.get("state") ?? "";

  useEffect(() => {
    let ignore = false;

    async function run() {
      setLoading(true);
      setError("");
      setSuccess("");

      if (providerError) {
        const details = [providerError, errorReason, errorDescription].filter((item) => item.trim() !== "").join(" · ");
        if (!ignore) {
          setError(`Meta OAuth returned an error: ${details || providerError}`);
          setLoading(false);
        }
        return;
      }

      if (!code || !state) {
        if (!ignore) {
          setError("Missing code/state in Meta OAuth callback.");
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
          setSuccess(payload.message ?? "Meta OAuth connected successfully.");
          setLoading(false);
          window.setTimeout(() => {
            replace("/agency/integrations?meta_connected=1");
          }, 800);
        }
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
  }, [replace, providerError, errorReason, errorDescription, code, state]);

  return (
    <>
      {loading ? <p className="text-sm text-slate-600">Finalizăm conectarea Meta...</p> : null}
      {error ? <p className="text-sm text-red-600">{error}</p> : null}
      {success ? <p className="text-sm text-emerald-700">{success}</p> : null}
      {!loading && !error ? <p className="mt-2 text-xs text-slate-500">Redirecționăm către Agency Integrations...</p> : null}
    </>
  );
}

export default function MetaOAuthCallbackPage() {
  return (
    <ProtectedPage>
      <AppShell title="Meta OAuth Callback">
        <Suspense fallback={<p className="text-sm text-slate-600">Pregătim callback-ul Meta...</p>}>
          <MetaOAuthCallbackBody />
        </Suspense>
      </AppShell>
    </ProtectedPage>
  );
}
