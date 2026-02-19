"use client";

import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";
import { Activity, Lock, Mail, Shield } from "lucide-react";
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
        body: JSON.stringify({ email, password, role }),
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
    <main className="flex min-h-screen items-center justify-center bg-background p-4">
      <div className="w-full max-w-sm">
        {/* Logo */}
        <div className="mb-8 flex flex-col items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary shadow-lg shadow-primary/20">
            <Activity className="h-5 w-5 text-primary-foreground" />
          </div>
          <div className="text-center">
            <h1 className="text-xl font-semibold text-foreground">MCC Command Center</h1>
            <p className="mt-1 text-sm text-muted-foreground">Autentificare in platforma</p>
          </div>
        </div>

        {/* Login form */}
        <form onSubmit={onSubmit} className="mcc-card p-6">
          <div className="flex flex-col gap-4">
            <label className="flex flex-col gap-1.5">
              <span className="text-sm font-medium text-foreground">Email</span>
              <div className="relative">
                <Mail className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="mcc-input pl-10"
                  required
                />
              </div>
            </label>

            <label className="flex flex-col gap-1.5">
              <span className="text-sm font-medium text-foreground">Parola</span>
              <div className="relative">
                <Lock className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="mcc-input pl-10"
                  required
                />
              </div>
            </label>

            <label className="flex flex-col gap-1.5">
              <span className="text-sm font-medium text-foreground">Rol</span>
              <div className="relative">
                <Shield className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <select
                  value={role}
                  onChange={(e) => setRole(e.target.value)}
                  className="mcc-input appearance-none pl-10"
                >
                  <option value="agency_admin">Agency Admin</option>
                  <option value="account_manager">Account Manager</option>
                  <option value="client_viewer">Client Viewer</option>
                </select>
              </div>
            </label>

            {error && (
              <div className="rounded-lg border border-destructive/20 bg-destructive/5 p-3">
                <p className="text-sm text-destructive">{error}</p>
              </div>
            )}

            <button
              disabled={loading}
              className="mcc-btn-primary mt-2 h-10 w-full"
            >
              {loading ? (
                <span className="flex items-center gap-2">
                  <span className="h-4 w-4 animate-spin rounded-full border-2 border-primary-foreground border-t-transparent" />
                  Se autentifica...
                </span>
              ) : (
                "Intra in platforma"
              )}
            </button>
          </div>
        </form>

        {/* Footer */}
        <p className="mt-4 text-center text-xs text-muted-foreground">
          {"Platforma de management pentru agentii de marketing"}
        </p>
      </div>
    </main>
  );
}
