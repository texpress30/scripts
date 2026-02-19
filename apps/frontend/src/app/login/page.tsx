"use client";

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
    <main className="mx-auto flex min-h-screen max-w-md items-center p-6">
      <form onSubmit={onSubmit} className="wm-card w-full p-6">
        <h1 className="mb-6 text-2xl font-semibold text-slate-900">Login</h1>

        <label className="mb-3 block">
          <span className="mb-1 block text-sm text-slate-600">Email</span>
          <input value={email} onChange={(e) => setEmail(e.target.value)} className="wm-input" required />
        </label>

        <label className="mb-3 block">
          <span className="mb-1 block text-sm text-slate-600">Parolă</span>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="wm-input"
            required
          />
        </label>

        <label className="mb-4 block">
          <span className="mb-1 block text-sm text-slate-600">Rol</span>
          <select value={role} onChange={(e) => setRole(e.target.value)} className="wm-input">
            <option value="agency_admin">Agency Admin</option>
            <option value="account_manager">Account Manager</option>
            <option value="client_viewer">Client Viewer</option>
          </select>
        </label>

        {error ? <p className="mb-3 text-sm text-red-600">{error}</p> : null}

        <button disabled={loading} className="wm-btn-primary w-full disabled:opacity-50">
          {loading ? "Se autentifică..." : "Intră în platformă"}
        </button>
      </form>
    </main>
  );
}
