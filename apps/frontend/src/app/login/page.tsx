"use client";

import { Activity, Lock, Mail, Shield } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import React, { FormEvent, useEffect, useState } from "react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { apiRequest } from "@/lib/api";
import { getSessionAccessContextFromToken } from "@/lib/session";

type LoginResponse = {
  access_token: string;
  token_type: string;
};

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("admin@example.com");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState("agency_admin");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [resetSuccess, setResetSuccess] = useState(false);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const query = new URLSearchParams(window.location.search);
    setResetSuccess(query.get("reset") === "success");
  }, []);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      const data = await apiRequest<LoginResponse>("/auth/login", {
        method: "POST",
        body: JSON.stringify({ email, password, role }),
      });

      localStorage.setItem("mcc_token", data.access_token);
      localStorage.setItem("mcc_user", email);

      const context = getSessionAccessContextFromToken(data.access_token);
      const shouldUseSubaccountRoute =
        context.role === "subaccount_admin" ||
        context.role === "subaccount_user" ||
        context.role === "subaccount_viewer" ||
        context.role === "account_manager" ||
        context.role === "client_viewer";

      if (shouldUseSubaccountRoute && context.allowed_subaccount_ids.length === 1) {
        router.push(`/sub/${context.allowed_subaccount_ids[0]}/dashboard`);
      } else if (shouldUseSubaccountRoute && context.primary_subaccount_id !== null) {
        router.push(`/sub/${context.primary_subaccount_id}/dashboard`);
      } else {
        router.push("/agency/dashboard");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-slate-100 px-4 py-10">
      <div className="w-full max-w-md">
        <div className="mb-6 text-center">
          <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-xl bg-indigo-600 text-white shadow-lg shadow-indigo-600/30">
            <Activity className="h-6 w-6" />
          </div>
          <h1 className="text-2xl font-bold text-slate-900">MCC Command Center</h1>
          <p className="mt-1 text-sm text-slate-600">Intră în platformă</p>
        </div>

        <Card className="border-slate-200 bg-white shadow-xl">
          <CardHeader>
            <CardTitle>Autentificare</CardTitle>
          </CardHeader>
          <CardContent>
            <form onSubmit={onSubmit} className="space-y-4">
              <label className="block">
                <span className="mb-1 block text-sm font-medium text-slate-700">Email</span>
                <div className="flex items-center gap-2 rounded-md border border-slate-300 bg-white px-3">
                  <Mail className="h-4 w-4 text-slate-400" />
                  <input
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    className="h-10 w-full bg-transparent text-sm outline-none"
                    required
                  />
                </div>
              </label>

              <label className="block">
                <span className="mb-1 block text-sm font-medium text-slate-700">Parola</span>
                <div className="flex items-center gap-2 rounded-md border border-slate-300 bg-white px-3">
                  <Lock className="h-4 w-4 text-slate-400" />
                  <input
                    type="password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    className="h-10 w-full bg-transparent text-sm outline-none"
                    required
                  />
                </div>
              </label>

              <label className="block">
                <span className="mb-1 block text-sm font-medium text-slate-700">Rol</span>
                <div className="flex items-center gap-2 rounded-md border border-slate-300 bg-white px-3">
                  <Shield className="h-4 w-4 text-slate-400" />
                  <select value={role} onChange={(e) => setRole(e.target.value)} className="h-10 w-full bg-transparent text-sm outline-none">
                    <option value="agency_admin">Agency Admin</option>
                    <option value="agency_member">Agency Member</option>
                    <option value="agency_viewer">Agency Viewer</option>
                    <option value="subaccount_admin">Subaccount Admin</option>
                    <option value="subaccount_user">Subaccount User</option>
                    <option value="subaccount_viewer">Subaccount Viewer</option>
                  </select>
                </div>
              </label>

              <div className="flex justify-end">
                <Link href="/forgot-password" className="text-sm text-indigo-600 hover:text-indigo-500">
                  Ai uitat parola?
                </Link>
              </div>

              {resetSuccess ? <p className="text-sm text-emerald-700">Parola a fost resetată. Te poți autentifica.</p> : null}

              {error ? <p className="text-sm text-red-600">{error}</p> : null}

              <button
                disabled={loading}
                className="h-10 w-full rounded-md bg-indigo-600 text-sm font-medium text-white hover:bg-indigo-500 disabled:opacity-50"
              >
                {loading ? "Se autentifică..." : "Intră în platformă"}
              </button>
            </form>
          </CardContent>
        </Card>
      </div>
    </main>
  );
}
