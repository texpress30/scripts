"use client";

import Link from "next/link";
import React, { FormEvent, useEffect, useState } from "react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ApiRequestError, confirmResetPassword, getResetPasswordTokenContext, type ResetPasswordTokenContextApiResponse } from "@/lib/api";

function mapResetErrorMessage(error: ApiRequestError): string {
  const detail = error.message.toLowerCase();
  if (detail.includes("expirat")) return "Tokenul de resetare a expirat. Solicită un link nou.";
  if (detail.includes("folosit")) return "Tokenul a fost deja folosit. Solicită un link nou.";
  if (detail.includes("invalid")) return "Token invalid. Verifică linkul primit pe email.";
  if (detail.includes("parola")) return error.message;
  if (error.status === 503) return "Reset password este indisponibil momentan. Încearcă din nou mai târziu.";
  return error.message || "Nu am putut reseta parola.";
}

export default function ResetPasswordPage() {
  const [token, setToken] = useState("");
  const [tokenContext, setTokenContext] = useState<ResetPasswordTokenContextApiResponse | null>(null);
  const [contextLoading, setContextLoading] = useState(false);
  const [contextFetchFailed, setContextFetchFailed] = useState(false);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const query = new URLSearchParams(window.location.search);
    const queryToken = (query.get("token") || "").trim();
    setToken(queryToken);
    if (!queryToken) return;

    setContextLoading(true);
    setContextFetchFailed(false);
    void getResetPasswordTokenContext(queryToken)
      .then((payload) => setTokenContext(payload))
      .catch(() => {
        setContextFetchFailed(true);
        setTokenContext(null);
      })
      .finally(() => setContextLoading(false));
  }, []);

  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const isInviteFlow = tokenContext?.valid === true && tokenContext.token_type === "invite_user";
  const isKnownInvalidToken = Boolean(token) && tokenContext?.valid === false;
  const heading = isInviteFlow ? "Setează parola contului" : "Resetează parola";
  const ctaLabel = isInviteFlow ? "Setează parola" : "Resetează parola";
  const description = isInviteFlow
    ? "Finalizează activarea contului setând parola inițială."
    : "Introdu parola nouă pentru a finaliza resetarea.";
  const invalidTokenMessage = tokenContext?.reason === "token_expired"
    ? "Linkul de activare/resetare a expirat. Solicită un link nou."
    : tokenContext?.reason === "token_consumed"
      ? "Linkul a fost deja folosit. Solicită un link nou."
      : "Link invalid. Verifică emailul primit sau solicită un link nou.";

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setError("");
    setSuccess("");

    if (!token) {
      setError("Tokenul de resetare lipsește din link.");
      return;
    }
    if (newPassword.trim().length < 8) {
      setError("Parola nouă trebuie să aibă cel puțin 8 caractere.");
      return;
    }
    if (newPassword !== confirmPassword) {
      setError("Parolele nu coincid.");
      return;
    }

    setLoading(true);
    try {
      await confirmResetPassword(token, newPassword);
      setSuccess(
        isInviteFlow
          ? "Contul a fost activat, parola a fost setată și te poți autentifica."
          : "Parola a fost resetată cu succes. Te poți autentifica.",
      );
      setNewPassword("");
      setConfirmPassword("");
    } catch (err) {
      if (err instanceof ApiRequestError) {
        setError(mapResetErrorMessage(err));
      } else {
        setError(err instanceof Error ? err.message : "Nu am putut reseta parola.");
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-slate-100 px-4 py-10">
      <div className="w-full max-w-md">
        <Card className="border-slate-200 bg-white shadow-xl">
          <CardHeader>
            <CardTitle>{heading}</CardTitle>
          </CardHeader>
          <CardContent>
            {!token ? (
              <div className="space-y-3 text-sm">
                <p className="text-red-600">Tokenul de resetare lipsește din link.</p>
                <div className="flex gap-4">
                  <Link href="/forgot-password" className="text-indigo-600 hover:text-indigo-500">
                    Solicită link nou
                  </Link>
                  <Link href="/login" className="text-indigo-600 hover:text-indigo-500">
                    Înapoi la login
                  </Link>
                </div>
              </div>
            ) : isKnownInvalidToken ? (
              <div className="space-y-3 text-sm">
                <p className="text-red-600">{invalidTokenMessage}</p>
                <div className="flex gap-4">
                  <Link href="/forgot-password" className="text-indigo-600 hover:text-indigo-500">
                    Solicită link nou
                  </Link>
                  <Link href="/login" className="text-indigo-600 hover:text-indigo-500">
                    Înapoi la login
                  </Link>
                </div>
              </div>
            ) : (
              <form onSubmit={onSubmit} className="space-y-4">
                <p className="text-sm text-slate-600">{description}</p>
                {contextLoading ? <p className="text-xs text-slate-500">Verificăm linkul...</p> : null}
                {contextFetchFailed ? <p className="text-xs text-amber-700">Nu am putut verifica tipul linkului acum; poți continua în siguranță.</p> : null}
                <label className="block">
                  <span className="mb-1 block text-sm font-medium text-slate-700">Parolă nouă</span>
                  <input
                    type="password"
                    value={newPassword}
                    onChange={(e) => setNewPassword(e.target.value)}
                    className="h-10 w-full rounded-md border border-slate-300 px-3 text-sm outline-none"
                    required
                  />
                </label>

                <label className="block">
                  <span className="mb-1 block text-sm font-medium text-slate-700">Confirmă parola nouă</span>
                  <input
                    type="password"
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                    className="h-10 w-full rounded-md border border-slate-300 px-3 text-sm outline-none"
                    required
                  />
                </label>

                {success ? <p className="text-sm text-emerald-700">{success}</p> : null}
                {error ? <p className="text-sm text-red-600">{error}</p> : null}

                <button
                  disabled={loading}
                  className="h-10 w-full rounded-md bg-indigo-600 text-sm font-medium text-white hover:bg-indigo-500 disabled:opacity-50"
                >
                  {loading ? "Se salvează..." : ctaLabel}
                </button>

                <div className="text-sm">
                  <Link href="/login?reset=success" className="text-indigo-600 hover:text-indigo-500">
                    Înapoi la login
                  </Link>
                </div>
              </form>
            )}
          </CardContent>
        </Card>
      </div>
    </main>
  );
}
