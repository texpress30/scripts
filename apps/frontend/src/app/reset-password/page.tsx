"use client";

import Link from "next/link";
import React, { FormEvent, useEffect, useState } from "react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ApiRequestError, confirmResetPassword } from "@/lib/api";

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

  useEffect(() => {
    if (typeof window === "undefined") return;
    const query = new URLSearchParams(window.location.search);
    setToken((query.get("token") || "").trim());
  }, []);

  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

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
      const response = await confirmResetPassword(token, newPassword);
      setSuccess(response.message || "Parola a fost resetată cu succes.");
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
            <CardTitle>Resetează parola</CardTitle>
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
            ) : (
              <form onSubmit={onSubmit} className="space-y-4">
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
                  {loading ? "Se salvează..." : "Resetează parola"}
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
