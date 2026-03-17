"use client";

import Link from "next/link";
import React, { FormEvent, useState } from "react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ApiRequestError, forgotPassword } from "@/lib/api";

const GENERIC_SUCCESS = "Dacă există un cont pentru această adresă, am trimis instrucțiunile de resetare.";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setError("");
    setSuccess("");
    setLoading(true);

    try {
      const response = await forgotPassword(email.trim());
      setSuccess(response.message || GENERIC_SUCCESS);
    } catch (err) {
      if (err instanceof ApiRequestError && err.status === 503) {
        setError("Reset password este indisponibil momentan. Te rugăm încearcă din nou puțin mai târziu.");
      } else {
        setError(err instanceof Error ? err.message : "Nu am putut trimite cererea de resetare.");
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
            <CardTitle>Ai uitat parola?</CardTitle>
          </CardHeader>
          <CardContent>
            <form onSubmit={onSubmit} className="space-y-4">
              <label className="block">
                <span className="mb-1 block text-sm font-medium text-slate-700">Email</span>
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="h-10 w-full rounded-md border border-slate-300 px-3 text-sm outline-none"
                  placeholder="nume@companie.ro"
                  required
                />
              </label>

              {success ? <p className="text-sm text-emerald-700">{success}</p> : null}
              {error ? <p className="text-sm text-red-600">{error}</p> : null}

              <button
                disabled={loading}
                className="h-10 w-full rounded-md bg-indigo-600 text-sm font-medium text-white hover:bg-indigo-500 disabled:opacity-50"
              >
                {loading ? "Se trimite..." : "Trimite link de resetare"}
              </button>
            </form>

            <div className="mt-4 text-sm">
              <Link href="/login" className="text-indigo-600 hover:text-indigo-500">
                Înapoi la login
              </Link>
            </div>
          </CardContent>
        </Card>
      </div>
    </main>
  );
}
