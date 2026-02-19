"use client";

import { useEffect, useState } from "react";
import { AppShell } from "@/components/AppShell";
import { NewDashboardOverview } from "@/components/NewDashboardOverview";
import { ProtectedPage } from "@/components/ProtectedPage";
import { ClientSelector } from "@/components/ClientSelector";
import { SpendAreaChart, ConversionsBarChart } from "@/components/PerformanceCharts";
import { RecentActivity } from "@/components/RecentActivity";
import { MetricCard } from "@/components/MetricCard";
import { apiRequest } from "@/lib/api";
import { DollarSign, MousePointerClick, Target } from "lucide-react";

type DashboardResponse = {
  client_id: number;
  totals: {
    spend: number;
    conversions: number;
    roas: number;
  };
  platforms: {
    google_ads: { spend: number; conversions: number; roas?: number };
    meta_ads: { spend: number; conversions: number; roas?: number };
  };
};

export default function DashboardPage() {
  const [clientId, setClientId] = useState(1);
  const [data, setData] = useState<DashboardResponse | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let ignore = false;
    async function load() {
      setError("");
      setLoading(true);
      try {
        const result = await apiRequest<DashboardResponse>(`/dashboard/${clientId}`);
        if (!ignore) setData(result);
      } catch (err) {
        if (!ignore) setError(err instanceof Error ? err.message : "Nu pot incarca dashboard");
      } finally {
        if (!ignore) setLoading(false);
      }
    }
    void load();
    return () => {
      ignore = true;
    };
  }, [clientId]);

  return (
    <ProtectedPage>
      <AppShell
        title="Dashboard"
        headerActions={
          <ClientSelector
            selectedClientId={clientId}
            onClientChange={setClientId}
          />
        }
      >
        {/* Page header description */}
        <div className="mb-6">
          <p className="text-sm text-muted-foreground">
            Monitorizare in timp real pentru Google Ads si Meta Ads. Selecteaza un client pentru a vedea performanta.
          </p>
        </div>

        {error && (
          <div className="mb-6 rounded-lg border border-destructive/20 bg-destructive/5 p-4">
            <p className="text-sm text-destructive">{error}</p>
          </div>
        )}

        {/* Loading skeleton */}
        {loading && !data && (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {[...Array(4)].map((_, i) => (
              <div key={i} className="mcc-card animate-pulse p-5">
                <div className="h-3 w-20 rounded bg-muted" />
                <div className="mt-3 h-7 w-24 rounded bg-muted" />
                <div className="mt-3 h-4 w-32 rounded bg-muted" />
              </div>
            ))}
          </div>
        )}

        {/* Data loaded */}
        {data && (
          <div className="flex flex-col gap-6 animate-fade-in">
            {/* Metrics overview */}
            <NewDashboardOverview
              totals={data.totals}
              google={data.platforms.google_ads}
              meta={data.platforms.meta_ads}
            />

            {/* Charts row */}
            <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
              <SpendAreaChart />
              <ConversionsBarChart />
            </div>

            {/* Activity feed */}
            <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
              <div className="lg:col-span-2">
                <RecentActivity />
              </div>
              <div className="mcc-card flex flex-col gap-4 p-5">
                <h3 className="text-sm font-semibold text-foreground">Sumar Rapid</h3>
                <div className="flex flex-col gap-3">
                  <SummaryRow
                    label="Cost per Conversie"
                    value={
                      data.totals.conversions > 0
                        ? `$${(data.totals.spend / data.totals.conversions).toFixed(2)}`
                        : "—"
                    }
                  />
                  <SummaryRow
                    label="Google Spend %"
                    value={
                      data.totals.spend > 0
                        ? `${((data.platforms.google_ads.spend / data.totals.spend) * 100).toFixed(0)}%`
                        : "—"
                    }
                  />
                  <SummaryRow
                    label="Meta Spend %"
                    value={
                      data.totals.spend > 0
                        ? `${((data.platforms.meta_ads.spend / data.totals.spend) * 100).toFixed(0)}%`
                        : "—"
                    }
                  />
                  <SummaryRow
                    label="Platforma Top"
                    value={
                      data.platforms.google_ads.conversions >= data.platforms.meta_ads.conversions
                        ? "Google"
                        : "Meta"
                    }
                  />
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Fallback when no data and not loading */}
        {!loading && !data && !error && (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            <MetricCard title="Spend" value="—" icon={DollarSign} />
            <MetricCard title="Conversii" value="—" icon={MousePointerClick} />
            <MetricCard title="ROAS" value="—" icon={Target} />
          </div>
        )}
      </AppShell>
    </ProtectedPage>
  );
}

function SummaryRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between rounded-lg bg-muted/50 px-3 py-2">
      <span className="text-xs text-muted-foreground">{label}</span>
      <span className="text-sm font-semibold text-foreground">{value}</span>
    </div>
  );
}
