"use client";

import { TrendingUp, TrendingDown, Minus } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";

type MetricCardProps = {
  title: string;
  value: string;
  change?: number;
  changePeriod?: string;
  icon?: LucideIcon;
  format?: "currency" | "number" | "percentage";
  className?: string;
};

export function MetricCard({
  title,
  value,
  change,
  changePeriod = "vs. luna trecuta",
  icon: Icon,
  className,
}: MetricCardProps) {
  const isPositive = change !== undefined && change > 0;
  const isNegative = change !== undefined && change < 0;
  const isNeutral = change === undefined || change === 0;

  return (
    <article className={cn("mcc-card group relative overflow-hidden p-5", className)}>
      {/* Subtle accent gradient on hover */}
      <div className="absolute inset-0 bg-gradient-to-br from-primary/[0.02] to-transparent opacity-0 transition-opacity group-hover:opacity-100" />

      <div className="relative">
        <div className="flex items-center justify-between">
          <p className="text-[13px] font-medium text-muted-foreground">{title}</p>
          {Icon && (
            <div className="rounded-md bg-muted p-1.5">
              <Icon className="h-3.5 w-3.5 text-muted-foreground" />
            </div>
          )}
        </div>

        <p className="mt-2 text-2xl font-semibold tracking-tight text-foreground">
          {value}
        </p>

        {change !== undefined && (
          <div className="mt-2 flex items-center gap-1.5">
            <span
              className={cn(
                "inline-flex items-center gap-0.5 rounded-full px-1.5 py-0.5 text-xs font-medium",
                isPositive && "bg-success/10 text-success",
                isNegative && "bg-destructive/10 text-destructive",
                isNeutral && "bg-muted text-muted-foreground"
              )}
            >
              {isPositive && <TrendingUp className="h-3 w-3" />}
              {isNegative && <TrendingDown className="h-3 w-3" />}
              {isNeutral && <Minus className="h-3 w-3" />}
              {isPositive ? "+" : ""}
              {change.toFixed(1)}%
            </span>
            <span className="text-xs text-muted-foreground">{changePeriod}</span>
          </div>
        )}
      </div>
    </article>
  );
}
