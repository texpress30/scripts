"use client";

import { Mail, Lock, Shield, Activity } from "lucide-react";
import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";

import { apiRequest } from "@/lib/api";

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

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      const data = await apiRequest<LoginResponse>("/auth/login", {
        method: "POST",
        body: JSON.stringify({ email, password, role })
      });

      localStorage.setItem("mcc_token", data.access_token);
      localStorage.setItem("mcc_user", email);
      router.push("/dashboard");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="mx-auto flex min-h-screen max-w-6xl items-center px-6 py-16">
      <div className="mx-auto w-full max-w-xl">
        <div className="mb-8 text-center">
          <div className="mx-auto mb-5 flex h-14 w-14 items-center justify-center rounded-2xl bg-indigo-600 shadow-lg shadow-indigo-600/25">
            <Activity className="h-7 w-7 text-white" />
          </div>
          <h1 className="text-5xl font-bold tracking-tight text-slate-900">MCC Command Center</h1>
          <p className="mt-3 text-xl text-slate-600">Autentificare in platforma</p>
        </div>

        <form onSubmit={onSubmit} className="premium-card p-8">
          <label className="mb-4 block">
            <span className="mb-2 block text-lg font-semibold text-slate-900">Email</span>
            <div className="premium-input-wrapper">
              <Mail className="h-5 w-5 text-slate-500" />
              <input value={email} onChange={(e) => setEmail(e.target.value)} className="premium-input" required />
            </div>
          </label>

          <label className="mb-4 block">
            <span className="mb-2 block text-lg font-semibold text-slate-900">Parola</span>
            <div className="premium-input-wrapper">
              <Lock className="h-5 w-5 text-slate-500" />
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="premium-input"
                required
              />
            </div>
          </label>

          <label className="mb-5 block">
            <span className="mb-2 block text-lg font-semibold text-slate-900">Rol</span>
            <div className="premium-input-wrapper">
              <Shield className="h-5 w-5 text-slate-500" />
              <select value={role} onChange={(e) => setRole(e.target.value)} className="premium-input">
                <option value="agency_admin">Agency Admin</option>
                <option value="account_manager">Account Manager</option>
                <option value="client_viewer">Client Viewer</option>
              </select>
            </div>
          </label>

          {error ? <p className="mb-3 text-sm text-red-600">{error}</p> : null}

          <button disabled={loading} className="premium-btn-primary w-full justify-center disabled:opacity-50">
            {loading ? "Se autentifica..." : "Intra in platforma"}
          </button>
        </form>

        <p className="mt-6 text-center text-base text-slate-500">Platforma de management pentru agentii de marketing</p>
      </div>
    </main>
  );
}
