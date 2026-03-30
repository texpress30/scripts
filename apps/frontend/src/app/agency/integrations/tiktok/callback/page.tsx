"use client";

import React, { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";

import { AppShell } from "@/components/AppShell";
import { ProtectedPage } from "@/components/ProtectedPage";
import { apiRequest } from "@/lib/api";

type TikTokExchangeResponse = {
  status?: string;
  provider?: string;
  message?: string;
};

function TikTokOAuthCallbackBody() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const replace = router.replace;
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  const providerError = searchParams.get("error") ?? "";
  const errorReason = searchParams.get("error_reason") ?? "";
  const errorDescription = searchParams.get("error_description") ?? "";
  const code = searchParams.get("auth_code") ?? searchParams.get("code") ?? "";
  const urlState = searchParams.get("state") ?? "";
  const savedState = typeof window !== "undefined" ? sessionStorage.getItem("tiktok_oauth_state") ?? "" : "";
  // Prefer sessionStorage state (our HMAC token) over URL state — TikTok may
  // return its own state value that doesn't match our HMAC format.
  const state = savedState || urlState;

  // Debug: log all callback parameters for troubleshooting
  // eslint-disable-next-line no-console
  console.log("[TikTok Callback]", {
    urlState: urlState ? `${urlState.substring(0, 30)}... (len=${urlState.length})` : "(empty)",
    savedState: savedState ? `${savedState.substring(0, 30)}... (len=${savedState.length})` : "(empty)",
    stateUsed: state ? `${state.substring(0, 30)}... (len=${state.length})` : "(empty)",
    stateSource: savedState ? "sessionStorage" : urlState ? "url" : "none",
    codeParam: code ? `${code.substring(0, 10)}... (len=${code.length})` : "(empty)",
    fullUrl: typeof window !== "undefined" ? window.location.href.substring(0, 150) : "ssr",
  });

  useEffect(() => {
    let ignore = false;

    async function run() {
      setLoading(true);
      setError("");
      setSuccess("");

      if (providerError) {
        const details = [providerError, errorReason, errorDescription].filter((item) => item.trim() !== "").join(" · ");
        if (!ignore) {
          setError(`TikTok OAuth returned an error: ${details || providerError}`);
          setLoading(false);
        }
        return;
      }

      if (!code || !state) {
        if (!ignore) {
          setError(`Missing code/state in TikTok OAuth callback. code=${code ? "present" : "missing"}, state=${state ? "present" : "missing"}, urlState=${urlState ? "present" : "missing"}, savedState=${savedState ? "present" : "missing"}`);
          setLoading(false);
        }
        return;
      }

      try {
        const payload = await apiRequest<TikTokExchangeResponse>("/integrations/tiktok-ads/oauth/exchange", {
          method: "POST",
          body: JSON.stringify({ code, state }),
        });

        sessionStorage.removeItem("tiktok_oauth_state");
        if (!ignore) {
          setSuccess(payload.message ?? "TikTok OAuth connected successfully.");
          setLoading(false);
          window.setTimeout(() => {
            replace("/agency/integrations?tiktok_connected=1");
          }, 800);
        }
      } catch (err) {
        if (!ignore) {
          setError(err instanceof Error ? err.message : "TikTok OAuth exchange failed");
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
      {loading ? <p className="text-sm text-slate-600">Finalizăm conectarea TikTok...</p> : null}
      {error ? <p className="text-sm text-red-600">{error}</p> : null}
      {success ? <p className="text-sm text-emerald-700">{success}</p> : null}
      {!loading && !error ? <p className="mt-2 text-xs text-slate-500">Redirecționăm către Agency Integrations...</p> : null}
    </>
  );
}

export default function TikTokOAuthCallbackPage() {
  return (
    <ProtectedPage>
      <AppShell title="TikTok OAuth Callback">
        <Suspense fallback={<p className="text-sm text-slate-600">Pregătim callback-ul TikTok...</p>}>
          <TikTokOAuthCallbackBody />
        </Suspense>
      </AppShell>
    </ProtectedPage>
  );
}
