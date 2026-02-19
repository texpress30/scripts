"use client";

import { DollarSign, MousePointerClick, Target, Zap } from "lucide-react";
import { MetricCard } from "@/components/MetricCard";

type Platform = { spend: number; conversions: number; roas?: number };

type DashboardTotals = {
  spend: number;
  conversions: number;
  roas: number;
};

export function NewDashboardOverview({
  totals,
  google,
  meta,
}: {
  totals: DashboardTotals;
  google: Platform;
  meta: Platform;
}) {
  const topPlatform = google.spend >= meta.spend ? "Google Ads" : "Meta Ads";

  return (
    <div className="flex flex-col gap-4">
      {/* Bento Grid Metrics Row */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <MetricCard
          title="Spend Total"
          value={`$${totals.spend.toLocaleString()}`}
          change={12.3}
          changePeriod="vs. luna trecuta"
          icon={DollarSign}
        />
        <MetricCard
          title="Conversii"
          value={totals.conversions.toLocaleString()}
          change={8.1}
          changePeriod="vs. luna trecuta"
          icon={MousePointerClick}
        />
        <MetricCard
          title="ROAS Mediu"
          value={totals.roas.toFixed(2)}
          change={totals.roas > 1 ? 5.2 : -2.4}
          changePeriod="vs. luna trecuta"
          icon={Target}
        />

        {/* Recommendation card as fourth bento item */}
        <article className="mcc-card relative overflow-hidden p-5">
          <div className="absolute inset-0 bg-gradient-to-br from-primary/5 to-transparent" />
          <div className="relative">
            <div className="flex items-center justify-between">
              <p className="text-[13px] font-medium text-muted-foreground">
                Recomandare AI
              </p>
              <div className="rounded-md bg-primary/10 p-1.5">
                <Zap className="h-3.5 w-3.5 text-primary" />
              </div>
            </div>
            <p className="mt-2 text-sm font-medium text-foreground">
              Canal dominant: <span className="text-primary">{topPlatform}</span>
            </p>
            <p className="mt-1.5 text-xs leading-relaxed text-muted-foreground">
              Muta incremental spend catre canalul cu ROAS mai bun pentru performanta maxima.
            </p>
          </div>
        </article>
      </div>

      {/* Platform Breakdown */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <PlatformCard
          name="Google Ads"
          spend={google.spend}
          conversions={google.conversions}
          roas={google.roas}
          color="hsl(239, 84%, 67%)"
        />
        <PlatformCard
          name="Meta Ads"
          spend={meta.spend}
          conversions={meta.conversions}
          roas={meta.roas}
          color="hsl(160, 84%, 39%)"
        />
      </div>
    </div>
  );
}

function PlatformCard({
  name,
  spend,
  conversions,
  roas,
  color,
}: {
  name: string;
  spend: number;
  conversions: number;
  roas?: number;
  color: string;
}) {
  return (
    <div className="mcc-card p-5">
      <div className="mb-3 flex items-center gap-2">
        <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: color }} />
        <h3 className="text-sm font-semibold text-foreground">{name}</h3>
      </div>
      <div className="grid grid-cols-3 gap-4">
        <div>
          <p className="text-xs text-muted-foreground">Spend</p>
          <p className="mt-0.5 text-lg font-semibold text-foreground">
            ${spend.toLocaleString()}
          </p>
        </div>
        <div>
          <p className="text-xs text-muted-foreground">Conversii</p>
          <p className="mt-0.5 text-lg font-semibold text-foreground">
            {conversions.toLocaleString()}
          </p>
        </div>
        <div>
          <p className="text-xs text-muted-foreground">ROAS</p>
          <p className="mt-0.5 text-lg font-semibold text-foreground">
            {roas !== undefined ? roas.toFixed(2) : "—"}
          </p>
        </div>
      </div>
    </div>
  );
}
