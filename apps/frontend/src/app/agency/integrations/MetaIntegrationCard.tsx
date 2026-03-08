"use client";

import React, { useEffect, useState } from "react";
import { apiRequest } from "@/lib/api";

type MetaStatusResponse = {
  provider?: string;
  status?: string;
  message?: string;
  mode?: string;
  ad_accounts_count?: number;
  business_count?: number;
  token_source?: string;
  has_usable_token?: boolean;
  last_sync_at?: string;
};

function statusBadgeTone(status: string): string {
  const normalized = status.trim().toLowerCase();
  if (normalized === "connected") return "bg-emerald-100 text-emerald-700";
  if (normalized === "error") return "bg-red-100 text-red-700";
  if (normalized === "disabled") return "bg-slate-100 text-slate-600";
  return "bg-amber-100 text-amber-700";
}

function formatDate(value?: string): string {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString();
}

export function MetaIntegrationCard() {
  const [status, setStatus] = useState<MetaStatusResponse | null>(null);

  useEffect(() => {
    async function loadStatus() {
      try {
        const payload = await apiRequest<MetaStatusResponse>("/integrations/meta-ads/status");
        setStatus(payload);
      } catch {
        // Keep card rendering even if endpoint is temporarily unavailable.
      }
    }

    void loadStatus();
  }, []);

  const normalizedStatus = String(status?.status ?? "pending");

  return (
    <article className="wm-card p-4">
      <div className="flex items-center justify-between">
        <h2 className="text-base font-semibold text-slate-900">Meta Ads</h2>
        <span className={`rounded-full px-3 py-1 text-xs font-medium ${statusBadgeTone(normalizedStatus)}`}>{normalizedStatus}</span>
      </div>
      <p className="mt-2 text-sm text-slate-600">{status?.message ?? "Meta status indisponibil momentan."}</p>
      <div className="mt-2 space-y-1 text-xs text-slate-500">
        <p>Token source: {status?.token_source ?? "-"}</p>
        <p>Businesses: {status?.business_count ?? 0}</p>
        <p>Ad accounts: {status?.ad_accounts_count ?? 0}</p>
        <p>Last sync: {formatDate(status?.last_sync_at)}</p>
      </div>
      <p className="mt-3 text-xs text-slate-500">Conectarea și importul Meta se fac din backend OAuth flow; apoi poți rula sync din Agency Accounts.</p>
    </article>
  );
}
