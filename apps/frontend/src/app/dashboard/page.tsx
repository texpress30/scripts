"use client";

import { useEffect, useMemo, useState } from "react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  Legend,
} from "recharts";
import {
  DollarSign,
  MousePointerClick,
  Target,
  Sparkles,
  TrendingUp,
  TrendingDown,
  Clock,
  ArrowUpRight,
  Building2,
  BarChart3,
} from "lucide-react";

import { ProtectedPage } from "@/components/ProtectedPage";
import { AppShell } from "@/components/AppShell";
import { ClientCommandPalette } from "@/components/ClientCommandPalette";
import { apiRequest } from "@/lib/api";
import { cn } from "@/lib/utils";

type DashboardResponse = {
  client_id: number;
  totals: { spend: number; conversions: number; roas: number };
  platforms: {
    google_ads: { spend: number; conversions: number; roas?: number };
    meta_ads: { spend: number; conversions: number; roas?: number };
  };
};

type ClientItem = { id: number; name: string; owner_email: string };
type ClientsResponse = { items: ClientItem[] };

// --- Placeholder chart data for premium look ---
const spendChartData = [
  { date: "01 Ian", google: 2400, meta: 1800 },
  { date: "05 Ian", google: 3200, meta: 2200 },
  { date: "10 Ian", google: 3800, meta: 2600 },
  { date: "15 Ian", google: 4200, meta: 3100 },
  { date: "20 Ian", google: 4800, meta: 3400 },
  { date: "25 Ian", google: 5200, meta: 3200 },
  { date: "30 Ian", google: 5600, meta: 3600 },
];

const conversionChartData = [
  { date: "01 Ian", google: 24, meta: 18 },
  { date: "05 Ian", google: 32, meta: 22 },
  { date: "10 Ian", google: 38, meta: 30 },
  { date: "15 Ian", google: 42, meta: 35 },
  { date: "20 Ian", google: 48, meta: 28 },
  { date: "25 Ian", google: 45, meta: 38 },
  { date: "30 Ian", google: 52, meta: 40 },
];

const activityItems = [
  { icon: TrendingUp, color: "text-emerald-500", bg: "bg-emerald-50 dark:bg-emerald-950/40", title: "Budget crescut", desc: "Google Ads — Campaign Brand +20%", time: "Acum 2 ore" },
  { icon: TrendingDown, color: "text-rose-500", bg: "bg-rose-50 dark:bg-rose-950/40", title: "ROAS scazut", desc: "Meta Ads — Retargeting Campaign", time: "Acum 5 ore" },
  { icon: Sparkles, color: "text-indigo-500", bg: "bg-indigo-50 dark:bg-indigo-950/40", title: "Campanie noua", desc: "Google Ads — Performance Max", time: "Ieri" },
  { icon: TrendingUp, color: "text-emerald-500", bg: "bg-emerald-50 dark:bg-emerald-950/40", title: "Conversii record", desc: "Meta Ads — Lookalike Audience", time: "Acum 2 zile" },
];

export default function DashboardPage() {
  const [clientId, setClientId] = useState(1);
  const [clients, setClients] = useState<ClientItem[]>([]);
  const [data, setData] = useState<DashboardResponse | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let ignore = false;
    async function loadClients() {
      try {
        const result = await apiRequest<ClientsResponse>("/clients");
        if (!ignore) {
          setClients(result.items);
          if (result.items.length > 0 && !result.items.some((i) => i.id === clientId)) {
            setClientId(result.items[0].id);
          }
        }
      } catch {
        /* continue with defaults */
      }
    }
    void loadClients();
    return () => { ignore = true; };
  }, [clientId]);

  useEffect(() => {
    let ignore = false;
    async function loadDashboard() {
      setError("");
      try {
        const result = await apiRequest<DashboardResponse>(`/dashboard/${clientId}`);
        if (!ignore) setData(result);
      } catch (err) {
        if (!ignore) setError(err instanceof Error ? err.message : "Nu pot incarca dashboard");
      }
    }
    void loadDashboard();
    return () => { ignore = true; };
  }, [clientId]);

  const totals = data?.totals ?? { spend: 0, conversions: 0, roas: 0 };
  const google = data?.platforms.google_ads ?? { spend: 0, conversions: 0, roas: 0 };
  const meta = data?.platforms.meta_ads ?? { spend: 0, conversions: 0, roas: 0 };
  const topPlatform = google.spend >= meta.spend ? "Google Ads" : "Meta Ads";

  return (
    <ProtectedPage>
      <AppShell title="Dashboard">
        {/* Header row */}
        <div className="mb-6 flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
          <p className="text-sm text-slate-500 dark:text-slate-400">
            Monitorizare in timp real pentru Google Ads si Meta Ads. Selecteaza un client pentru a vedea performanta.
          </p>
          <ClientCommandPalette clients={clients} selectedClientId={clientId} onSelect={setClientId} />
        </div>

        {error && (
          <div className="mb-4 rounded-lg border border-rose-200 bg-rose-50 px-4 py-2.5 text-sm text-rose-600 dark:border-rose-800 dark:bg-rose-950/30 dark:text-rose-400">
            {error}
          </div>
        )}

        {/* Bento grid: 4 metric cards */}
        <div className="mb-6 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <MetricCard
            title="Spend Total"
            value={`$${totals.spend.toLocaleString()}`}
            trend={12.3}
            icon={DollarSign}
          />
          <MetricCard
            title="Conversii"
            value={totals.conversions.toLocaleString()}
            trend={8.1}
            icon={MousePointerClick}
          />
          <MetricCard
            title="ROAS Mediu"
            value={totals.roas.toFixed(2)}
            trend={-2.4}
            icon={Target}
          />
          <div className="mcc-card flex flex-col justify-between p-5">
            <div className="mb-3 flex items-center justify-between">
              <span className="text-xs font-medium uppercase tracking-wider text-slate-500 dark:text-slate-400">
                Recomandare AI
              </span>
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-indigo-50 dark:bg-indigo-950/40">
                <Sparkles className="h-4 w-4 text-indigo-600 dark:text-indigo-400" />
              </div>
            </div>
            <div>
              <p className="text-sm text-slate-600 dark:text-slate-300">
                {"Canal dominant: "}
                <span className="font-semibold text-indigo-600 dark:text-indigo-400">{topPlatform}</span>
              </p>
              <p className="mt-1 text-xs text-slate-400 dark:text-slate-500">
                Muta incremental spend catre canalul cu ROAS mai bun pentru performanta maxima.
              </p>
            </div>
          </div>
        </div>

        {/* Platform breakdown row */}
        <div className="mb-6 grid grid-cols-1 gap-4 md:grid-cols-2">
          <PlatformCard
            name="Google Ads"
            color="bg-indigo-500"
            spend={google.spend}
            conversions={google.conversions}
            roas={google.roas}
          />
          <PlatformCard
            name="Meta Ads"
            color="bg-emerald-500"
            spend={meta.spend}
            conversions={meta.conversions}
            roas={meta.roas}
          />
        </div>

        {/* Charts row */}
        <div className="mb-6 grid grid-cols-1 gap-4 lg:grid-cols-5">
          {/* Spend area chart - wider */}
          <div className="mcc-card p-5 lg:col-span-3">
            <div className="mb-4 flex items-center justify-between">
              <div>
                <h3 className="text-sm font-semibold text-slate-900 dark:text-slate-100">Spend per Canal</h3>
                <p className="text-xs text-slate-400 dark:text-slate-500">Google Ads vs Meta Ads — ultimele 30 zile</p>
              </div>
              <div className="flex items-center gap-4">
                <div className="flex items-center gap-1.5">
                  <span className="h-2 w-2 rounded-full bg-indigo-500" />
                  <span className="text-xs text-slate-500 dark:text-slate-400">Google</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <span className="h-2 w-2 rounded-full bg-emerald-500" />
                  <span className="text-xs text-slate-500 dark:text-slate-400">Meta</span>
                </div>
              </div>
            </div>
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={spendChartData}>
                  <defs>
                    <linearGradient id="googleGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#6366f1" stopOpacity={0.2} />
                      <stop offset="100%" stopColor="#6366f1" stopOpacity={0} />
                    </linearGradient>
                    <linearGradient id="metaGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#10b981" stopOpacity={0.15} />
                      <stop offset="100%" stopColor="#10b981" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" vertical={false} />
                  <XAxis dataKey="date" tick={{ fontSize: 11, fill: "#94a3b8" }} axisLine={false} tickLine={false} />
                  <YAxis tick={{ fontSize: 11, fill: "#94a3b8" }} axisLine={false} tickLine={false} tickFormatter={(v) => `$${(v / 1000).toFixed(0)}k`} />
                  <Tooltip
                    contentStyle={{ borderRadius: 12, border: "1px solid #e2e8f0", fontSize: 12, boxShadow: "0 4px 6px -1px rgb(0 0 0 / 0.06)" }}
                    formatter={(value: number) => [`$${value.toLocaleString()}`, ""]}
                  />
                  <Area type="monotone" dataKey="google" stroke="#6366f1" strokeWidth={2} fill="url(#googleGrad)" />
                  <Area type="monotone" dataKey="meta" stroke="#10b981" strokeWidth={2} fill="url(#metaGrad)" />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Conversions bar chart */}
          <div className="mcc-card p-5 lg:col-span-2">
            <div className="mb-4 flex items-center justify-between">
              <div>
                <h3 className="text-sm font-semibold text-slate-900 dark:text-slate-100">Conversii per Canal</h3>
                <p className="text-xs text-slate-400 dark:text-slate-500">Comparatie Google vs Meta — ultimele 30 zile</p>
              </div>
              <div className="flex items-center gap-4">
                <div className="flex items-center gap-1.5">
                  <span className="h-2 w-2 rounded-full bg-indigo-500" />
                  <span className="text-xs text-slate-500 dark:text-slate-400">Google</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <span className="h-2 w-2 rounded-full bg-emerald-500" />
                  <span className="text-xs text-slate-500 dark:text-slate-400">Meta</span>
                </div>
              </div>
            </div>
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={conversionChartData} barGap={2}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" vertical={false} />
                  <XAxis dataKey="date" tick={{ fontSize: 11, fill: "#94a3b8" }} axisLine={false} tickLine={false} />
                  <YAxis tick={{ fontSize: 11, fill: "#94a3b8" }} axisLine={false} tickLine={false} />
                  <Tooltip contentStyle={{ borderRadius: 12, border: "1px solid #e2e8f0", fontSize: 12, boxShadow: "0 4px 6px -1px rgb(0 0 0 / 0.06)" }} />
                  <Bar dataKey="google" fill="#6366f1" radius={[4, 4, 0, 0]} barSize={14} />
                  <Bar dataKey="meta" fill="#10b981" radius={[4, 4, 0, 0]} barSize={14} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>

        {/* Bottom row: Activity + Summary */}
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
          {/* Recent activity */}
          <div className="mcc-card p-5 lg:col-span-2">
            <div className="mb-4 flex items-center justify-between">
              <h3 className="text-sm font-semibold text-slate-900 dark:text-slate-100">Activitate Recenta</h3>
              <button className="text-xs font-medium text-indigo-600 transition hover:text-indigo-700 dark:text-indigo-400 dark:hover:text-indigo-300">
                Vezi tot
              </button>
            </div>
            <div className="space-y-3">
              {activityItems.map((item, i) => {
                const Icon = item.icon;
                return (
                  <div key={i} className="flex items-center gap-3 rounded-lg p-2 transition-colors hover:bg-slate-50 dark:hover:bg-slate-800/50">
                    <div className={cn("flex h-9 w-9 shrink-0 items-center justify-center rounded-lg", item.bg)}>
                      <Icon className={cn("h-4 w-4", item.color)} />
                    </div>
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-medium text-slate-900 dark:text-slate-100">{item.title}</p>
                      <p className="text-xs text-slate-500 dark:text-slate-400">{item.desc}</p>
                    </div>
                    <div className="flex shrink-0 items-center gap-1.5 text-xs text-slate-400 dark:text-slate-500">
                      <Clock className="h-3 w-3" />
                      {item.time}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Quick summary */}
          <div className="mcc-card p-5">
            <h3 className="mb-4 text-sm font-semibold text-slate-900 dark:text-slate-100">Sumar Rapid</h3>
            <div className="space-y-3">
              {[
                { label: "Cost per Conversie", value: totals.conversions > 0 ? `$${(totals.spend / totals.conversions).toFixed(2)}` : "—" },
                { label: "Google Spend %", value: totals.spend > 0 ? `${((google.spend / totals.spend) * 100).toFixed(0)}%` : "—" },
                { label: "Meta Spend %", value: totals.spend > 0 ? `${((meta.spend / totals.spend) * 100).toFixed(0)}%` : "—" },
                { label: "Platforma Top", value: topPlatform },
              ].map((row) => (
                <div key={row.label} className="flex items-center justify-between border-b border-slate-100 pb-2.5 last:border-0 dark:border-slate-800">
                  <span className="text-sm text-slate-500 dark:text-slate-400">{row.label}</span>
                  <span className="text-sm font-semibold text-slate-900 dark:text-slate-100">{row.value}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </AppShell>
    </ProtectedPage>
  );
}

/* ── Metric Card ── */
function MetricCard({
  title,
  value,
  trend,
  icon: Icon,
}: {
  title: string;
  value: string;
  trend: number;
  icon: React.ComponentType<{ className?: string }>;
}) {
  const isPositive = trend >= 0;
  return (
    <div className="mcc-card flex flex-col justify-between p-5">
      <div className="mb-3 flex items-center justify-between">
        <span className="text-xs font-medium uppercase tracking-wider text-slate-500 dark:text-slate-400">{title}</span>
        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-slate-100 dark:bg-slate-800">
          <Icon className="h-4 w-4 text-slate-500 dark:text-slate-400" />
        </div>
      </div>
      <p className="text-2xl font-bold text-slate-900 dark:text-slate-100">{value}</p>
      <div className="mt-2 flex items-center gap-1.5">
        <span
          className={cn(
            "inline-flex items-center gap-0.5 rounded-full px-2 py-0.5 text-xs font-medium",
            isPositive
              ? "bg-emerald-50 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-400"
              : "bg-rose-50 text-rose-700 dark:bg-rose-950/40 dark:text-rose-400"
          )}
        >
          {isPositive ? (
            <TrendingUp className="h-3 w-3" />
          ) : (
            <TrendingDown className="h-3 w-3" />
          )}
          {isPositive ? "+" : ""}
          {trend}%
        </span>
        <span className="text-xs text-slate-400 dark:text-slate-500">vs. luna trecuta</span>
      </div>
    </div>
  );
}

/* ── Platform Card ── */
function PlatformCard({
  name,
  color,
  spend,
  conversions,
  roas,
}: {
  name: string;
  color: string;
  spend: number;
  conversions: number;
  roas?: number;
}) {
  return (
    <div className="mcc-card p-5">
      <div className="mb-4 flex items-center gap-2.5">
        <span className={cn("h-2.5 w-2.5 rounded-full", color)} />
        <h3 className="text-sm font-semibold text-slate-900 dark:text-slate-100">{name}</h3>
      </div>
      <div className="grid grid-cols-3 gap-4">
        <div>
          <p className="text-xs text-slate-500 dark:text-slate-400">Spend</p>
          <p className="mt-0.5 text-lg font-bold text-slate-900 dark:text-slate-100">${spend.toLocaleString()}</p>
        </div>
        <div>
          <p className="text-xs text-slate-500 dark:text-slate-400">Conversii</p>
          <p className="mt-0.5 text-lg font-bold text-slate-900 dark:text-slate-100">{conversions.toLocaleString()}</p>
        </div>
        <div>
          <p className="text-xs text-slate-500 dark:text-slate-400">ROAS</p>
          <p className="mt-0.5 text-lg font-bold text-slate-900 dark:text-slate-100">{roas != null ? roas.toFixed(2) : "—"}</p>
        </div>
      </div>
    </div>
  );
}
