"use client";

import { format } from "date-fns";
import { Area, AreaChart, CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

type SpendPoint = {
  date: string;
  spend: number;
};

type PlatformPoint = {
  date: string;
  google_ads: number;
  meta_ads: number;
  tiktok_ads: number;
};

function safeNumber(value: unknown): number {
  return typeof value === "number" && Number.isFinite(value) ? value : 0;
}

function formatCurrency(value: number, currencyCode: string): string {
  return new Intl.NumberFormat(undefined, { style: "currency", currency: currencyCode, maximumFractionDigits: 2 }).format(value);
}

export function SubDashboardCharts({
  mode,
  spendByDay,
  spendByPlatformTimeline,
  currencyCode,
}: {
  mode: "total" | "platform";
  spendByDay: SpendPoint[];
  spendByPlatformTimeline: PlatformPoint[];
  currencyCode: string;
}) {
  if (mode === "total") {
    return (
      <div className="h-96 min-h-[24rem] w-full">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={spendByDay}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="date" tickFormatter={(value: string) => format(new Date(value), "dd MMM")} />
            <YAxis tickFormatter={(value: number) => formatCurrency(value, currencyCode)} width={100} />
            <Tooltip formatter={(value: number) => formatCurrency(safeNumber(value), currencyCode)} labelFormatter={(value: string) => format(new Date(value), "dd MMM yyyy")} />
            <Area type="monotone" dataKey="spend" stroke="#4f46e5" fill="#c7d2fe" strokeWidth={2} />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    );
  }

  return (
    <div className="h-96 min-h-[24rem] w-full">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={spendByPlatformTimeline}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="date" tickFormatter={(value: string) => format(new Date(value), "dd MMM")} />
          <YAxis tickFormatter={(value: number) => formatCurrency(value, currencyCode)} width={100} />
          <Tooltip formatter={(value: number) => formatCurrency(safeNumber(value), currencyCode)} labelFormatter={(value: string) => format(new Date(value), "dd MMM yyyy")} />
          <Line type="monotone" dataKey="google_ads" name="Google Ads" stroke="#22c55e" strokeWidth={3} dot={false} activeDot={{ r: 6 }} />
          <Line type="monotone" dataKey="meta_ads" name="Meta Ads" stroke="#2563eb" strokeWidth={3} dot={false} activeDot={{ r: 6 }} />
          <Line type="monotone" dataKey="tiktok_ads" name="TikTok Ads" stroke="#111827" strokeWidth={3} dot={false} activeDot={{ r: 6 }} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
