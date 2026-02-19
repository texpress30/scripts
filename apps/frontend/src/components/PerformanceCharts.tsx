"use client";

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
} from "recharts";

// Mock time-series data for the area chart (placeholder for FastAPI integration)
const spendTimeSeries = [
  { date: "01 Ian", google: 4200, meta: 3100 },
  { date: "05 Ian", google: 4800, meta: 2900 },
  { date: "10 Ian", google: 5100, meta: 3400 },
  { date: "15 Ian", google: 4600, meta: 3800 },
  { date: "20 Ian", google: 5400, meta: 4100 },
  { date: "25 Ian", google: 5800, meta: 3700 },
  { date: "30 Ian", google: 6200, meta: 4300 },
];

const conversionTimeSeries = [
  { date: "01 Ian", google: 42, meta: 31 },
  { date: "05 Ian", google: 48, meta: 29 },
  { date: "10 Ian", google: 51, meta: 34 },
  { date: "15 Ian", google: 46, meta: 38 },
  { date: "20 Ian", google: 54, meta: 41 },
  { date: "25 Ian", google: 58, meta: 37 },
  { date: "30 Ian", google: 62, meta: 43 },
];

function CustomTooltip({ active, payload, label }: any) {
  if (!active || !payload) return null;
  return (
    <div className="rounded-lg border border-border bg-card px-3 py-2 shadow-lg">
      <p className="mb-1 text-xs font-medium text-muted-foreground">{label}</p>
      {payload.map((entry: any, i: number) => (
        <div key={i} className="flex items-center gap-2 text-sm">
          <span
            className="h-2 w-2 rounded-full"
            style={{ backgroundColor: entry.color }}
          />
          <span className="capitalize text-muted-foreground">{entry.dataKey}:</span>
          <span className="font-medium text-foreground">
            {typeof entry.value === "number"
              ? entry.value.toLocaleString()
              : entry.value}
          </span>
        </div>
      ))}
    </div>
  );
}

export function SpendAreaChart() {
  return (
    <div className="mcc-card p-5">
      <div className="mb-4 flex items-center justify-between">
        <div>
          <h3 className="text-sm font-semibold text-foreground">Spend per Canal</h3>
          <p className="text-xs text-muted-foreground">Google Ads vs Meta Ads — ultimele 30 zile</p>
        </div>
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1.5">
            <span className="h-2 w-2 rounded-full" style={{ backgroundColor: "hsl(239, 84%, 67%)" }} />
            <span className="text-xs text-muted-foreground">Google</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="h-2 w-2 rounded-full" style={{ backgroundColor: "hsl(160, 84%, 39%)" }} />
            <span className="text-xs text-muted-foreground">Meta</span>
          </div>
        </div>
      </div>
      <div className="h-64 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={spendTimeSeries} margin={{ top: 4, right: 4, left: -20, bottom: 0 }}>
            <defs>
              <linearGradient id="gradientGoogle" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="hsl(239, 84%, 67%)" stopOpacity={0.2} />
                <stop offset="100%" stopColor="hsl(239, 84%, 67%)" stopOpacity={0} />
              </linearGradient>
              <linearGradient id="gradientMeta" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="hsl(160, 84%, 39%)" stopOpacity={0.2} />
                <stop offset="100%" stopColor="hsl(160, 84%, 39%)" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" vertical={false} />
            <XAxis
              dataKey="date"
              tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }}
              axisLine={false}
              tickLine={false}
            />
            <YAxis
              tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }}
              axisLine={false}
              tickLine={false}
              tickFormatter={(v: number) => `$${(v / 1000).toFixed(0)}k`}
            />
            <Tooltip content={<CustomTooltip />} />
            <Area
              type="monotone"
              dataKey="google"
              stroke="hsl(239, 84%, 67%)"
              strokeWidth={2}
              fill="url(#gradientGoogle)"
            />
            <Area
              type="monotone"
              dataKey="meta"
              stroke="hsl(160, 84%, 39%)"
              strokeWidth={2}
              fill="url(#gradientMeta)"
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

export function ConversionsBarChart() {
  return (
    <div className="mcc-card p-5">
      <div className="mb-4 flex items-center justify-between">
        <div>
          <h3 className="text-sm font-semibold text-foreground">Conversii per Canal</h3>
          <p className="text-xs text-muted-foreground">Comparatie Google vs Meta — ultimele 30 zile</p>
        </div>
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1.5">
            <span className="h-2 w-2 rounded-full" style={{ backgroundColor: "hsl(239, 84%, 67%)" }} />
            <span className="text-xs text-muted-foreground">Google</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="h-2 w-2 rounded-full" style={{ backgroundColor: "hsl(160, 84%, 39%)" }} />
            <span className="text-xs text-muted-foreground">Meta</span>
          </div>
        </div>
      </div>
      <div className="h-64 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={conversionTimeSeries} margin={{ top: 4, right: 4, left: -20, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" vertical={false} />
            <XAxis
              dataKey="date"
              tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }}
              axisLine={false}
              tickLine={false}
            />
            <YAxis
              tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }}
              axisLine={false}
              tickLine={false}
            />
            <Tooltip content={<CustomTooltip />} />
            <Bar
              dataKey="google"
              fill="hsl(239, 84%, 67%)"
              radius={[4, 4, 0, 0]}
              barSize={16}
            />
            <Bar
              dataKey="meta"
              fill="hsl(160, 84%, 39%)"
              radius={[4, 4, 0, 0]}
              barSize={16}
            />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
