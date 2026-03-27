"use client";

import React from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  Radar,
  RadarChart,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
} from "recharts";

type OverviewPoint = Record<string, string | number>;

type OverviewChartsPayload = {
  display_currency?: string;
  custom_labels?: {
    custom_label_1?: string;
    custom_label_2?: string;
    custom_label_3?: string;
    custom_label_4?: string;
    custom_label_5?: string;
  };
  sales?: {
    total_sales_trend?: OverviewPoint[];
    channel_sales_composition?: OverviewPoint[];
    sales_efficiency_scatter?: OverviewPoint[];
  };
  financial?: {
    cost_efficiency?: OverviewPoint[];
    spend_vs_revenue_mix?: OverviewPoint[];
    conversion_funnel?: OverviewPoint[];
    profitability?: OverviewPoint[];
    channel_performance?: OverviewPoint[];
  };
};

function ChartCard({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="rounded-lg border border-slate-200 bg-white p-4" aria-label={title}>
      <h3 className="mb-3 text-sm font-semibold text-slate-900">{title}</h3>
      <div className="h-96 w-full">{children}</div>
    </section>
  );
}

function colorForChannel(channel: string): string {
  if (channel === "google") return "#2563eb";
  if (channel === "meta") return "#7c3aed";
  if (channel === "tiktok") return "#0f766e";
  return "#64748b";
}

export function SalesCharts({ payload }: { payload: OverviewChartsPayload }) {
  const sales = payload.sales || {};
  const conversion = payload.financial?.conversion_funnel || [];
  const salesFlowData = conversion.map((item) => ({
    ...item,
    applications: Number(item.custom_value_1_count || 0),
    approved: Number(item.custom_value_2_count || 0),
    sales_count: Number(item.sales || 0),
    approval_to_sales_ratio: Number(item.sales || 0) > 0 ? Number(item.custom_value_2_count || 0) / Number(item.sales || 1) : 0,
  }));
  return (
    <div className="mt-4 grid grid-cols-1 gap-4 xl:grid-cols-2">
      <ChartCard title="Trendul Vânzărilor Totale">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={sales.total_sales_trend || []}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} />
            <XAxis dataKey="label" />
            <YAxis />
            <Tooltip />
            <Line type="monotone" dataKey="revenue_total" stroke="#2563eb" dot={false} isAnimationActive={false} name="Venit total" />
          </LineChart>
        </ResponsiveContainer>
      </ChartCard>

      <ChartCard title="Compoziția Vânzărilor pe Canale">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={sales.channel_sales_composition || []}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} />
            <XAxis dataKey="label" />
            <YAxis />
            <Tooltip />
            <Legend />
            <Bar dataKey="google" stackId="sales" fill={colorForChannel("google")} name="Google" />
            <Bar dataKey="meta" stackId="sales" fill={colorForChannel("meta")} name="Meta" />
            <Bar dataKey="tiktok" stackId="sales" fill={colorForChannel("tiktok")} name="TikTok" />
          </BarChart>
        </ResponsiveContainer>
      </ChartCard>

      <ChartCard title="Eficiența Vânzărilor">
        <ResponsiveContainer width="100%" height="100%">
          <ScatterChart>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis type="number" dataKey="cost" name="Cost" />
            <YAxis type="number" dataKey="sold_value" name="Valoare vândută" />
            <Tooltip cursor={{ strokeDasharray: "3 3" }} />
            {(["google", "meta", "tiktok"] as const).map((channel) => (
              <Scatter
                key={channel}
                data={(sales.sales_efficiency_scatter || []).filter((item) => item.channel === channel)}
                fill={colorForChannel(channel)}
                name={channel === "google" ? "Google" : channel === "meta" ? "Meta" : "TikTok"}
              />
            ))}
          </ScatterChart>
        </ResponsiveContainer>
      </ChartCard>

      <ChartCard title="Aplicații / Aplicații Aprobate / Vânzări">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={salesFlowData}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} />
            <XAxis dataKey="label" />
            <YAxis />
            <Tooltip />
            <Legend />
            <Line type="monotone" dataKey="applications" stroke="#2563eb" dot={false} isAnimationActive={false} name={payload.custom_labels?.custom_label_1 || "Aplicații"} />
            <Line type="monotone" dataKey="approved" stroke="#7c3aed" dot={false} isAnimationActive={false} name={payload.custom_labels?.custom_label_2 || "Aplicații Aprobate"} />
            <Line type="monotone" dataKey="sales_count" stroke="#0f766e" dot={false} isAnimationActive={false} name="Vânzări" />
          </LineChart>
        </ResponsiveContainer>
      </ChartCard>

      <ChartCard title="Aprobări / Vânzări">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={salesFlowData}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} />
            <XAxis dataKey="label" />
            <YAxis />
            <Tooltip />
            <Legend />
            <Bar dataKey="approval_to_sales_ratio" fill="#334155" name="Aprobări / Vânzări" />
          </BarChart>
        </ResponsiveContainer>
      </ChartCard>
    </div>
  );
}

export function FinancialCharts({ payload }: { payload: OverviewChartsPayload }) {
  const financial = payload.financial || {};
  const custom1 = payload.custom_labels?.custom_label_1 || "Custom Value 1";
  const custom2 = payload.custom_labels?.custom_label_2 || "Custom Value 2";

  return (
    <div className="mt-4 grid grid-cols-1 gap-4 xl:grid-cols-2">
      <ChartCard title="Analiza Eficienței Costurilor (CPA și nCAC)">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={financial.cost_efficiency || []}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} />
            <XAxis dataKey="label" />
            <YAxis />
            <Tooltip />
            <Legend />
            <Line dataKey="google_cpa" stroke="#2563eb" dot={false} isAnimationActive={false} name="Google CPA" />
            <Line dataKey="google_ncac" stroke="#1d4ed8" dot={false} isAnimationActive={false} name="Google nCAC" />
            <Line dataKey="meta_cpa" stroke="#7c3aed" dot={false} isAnimationActive={false} name="Meta CPA" />
            <Line dataKey="meta_ncac" stroke="#6d28d9" dot={false} isAnimationActive={false} name="Meta nCAC" />
            <Line dataKey="tiktok_cpa" stroke="#0f766e" dot={false} isAnimationActive={false} name="TikTok CPA" />
            <Line dataKey="tiktok_ncac" stroke="#0f766e" strokeDasharray="5 5" dot={false} isAnimationActive={false} name="TikTok nCAC" />
          </LineChart>
        </ResponsiveContainer>
      </ChartCard>

      <ChartCard title="Analiza Pâlniei de Conversie">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={financial.conversion_funnel || []}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} />
            <XAxis dataKey="label" />
            <YAxis />
            <Tooltip />
            <Legend />
            <Bar dataKey="leads" fill="#334155" name="Leads" />
            <Bar dataKey="custom_value_1_count" fill="#2563eb" name={custom1} />
            <Bar dataKey="custom_value_2_count" fill="#7c3aed" name={custom2} />
          </BarChart>
        </ResponsiveContainer>
      </ChartCard>

      <ChartCard title="Profitabilitatea">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={financial.profitability || []}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} />
            <XAxis dataKey="label" />
            <YAxis />
            <Tooltip />
            <Legend />
            <Bar dataKey="gross_profit" fill="#16a34a" name="Profit Brut" />
            <Line dataKey="cogs_taxes" stroke="#ea580c" dot={false} isAnimationActive={false} name="COGS + Taxe" />
          </BarChart>
        </ResponsiveContainer>
      </ChartCard>

      <ChartCard title="Analiza Performanței pe Canale">
        <ResponsiveContainer width="100%" height="100%">
          <RadarChart data={financial.channel_performance || []}>
            <PolarGrid />
            <PolarAngleAxis dataKey="channel" />
            <PolarRadiusAxis />
            <Tooltip />
            <Legend />
            <Radar dataKey="cpa" stroke="#2563eb" fill="#2563eb" fillOpacity={0.2} name="CPA" />
            <Radar dataKey="conversion_rate" stroke="#7c3aed" fill="#7c3aed" fillOpacity={0.2} name="Rată de conversie" />
            <Radar dataKey="sales_volume" stroke="#0f766e" fill="#0f766e" fillOpacity={0.2} name="Volum vânzări" />
          </RadarChart>
        </ResponsiveContainer>
      </ChartCard>

      <ChartCard title="Cost per Client Nou">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={financial.cost_efficiency || []}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} />
            <XAxis dataKey="label" />
            <YAxis />
            <Tooltip />
            <Legend />
            <Bar dataKey="google_ncac" fill="#2563eb" name="Google" />
            <Bar dataKey="meta_ncac" fill="#7c3aed" name="Meta" />
            <Bar dataKey="tiktok_ncac" fill="#0f766e" name="TikTok" />
          </BarChart>
        </ResponsiveContainer>
      </ChartCard>
    </div>
  );
}

export type { OverviewChartsPayload };
