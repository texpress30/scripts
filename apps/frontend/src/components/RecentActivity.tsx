"use client";

import { Activity, ArrowUpRight, ArrowDownRight, Clock } from "lucide-react";

const activities = [
  {
    id: 1,
    action: "Budget crescut",
    detail: "Google Ads — Campaign Brand +20%",
    time: "Acum 2 ore",
    type: "positive" as const,
  },
  {
    id: 2,
    action: "ROAS scazut",
    detail: "Meta Ads — Retargeting Campaign",
    time: "Acum 5 ore",
    type: "negative" as const,
  },
  {
    id: 3,
    action: "Campanie noua",
    detail: "Google Ads — Performance Max",
    time: "Ieri",
    type: "neutral" as const,
  },
  {
    id: 4,
    action: "Conversii record",
    detail: "Meta Ads — Lookalike Audience",
    time: "Acum 2 zile",
    type: "positive" as const,
  },
];

export function RecentActivity() {
  return (
    <div className="mcc-card p-5">
      <div className="mb-4 flex items-center justify-between">
        <h3 className="text-sm font-semibold text-foreground">Activitate Recenta</h3>
        <button className="text-xs font-medium text-primary hover:underline">
          Vezi tot
        </button>
      </div>
      <div className="flex flex-col gap-3">
        {activities.map((item) => (
          <div
            key={item.id}
            className="flex items-start gap-3 rounded-lg p-2 transition-colors hover:bg-muted/50"
          >
            <div
              className={`mt-0.5 rounded-md p-1.5 ${
                item.type === "positive"
                  ? "bg-success/10"
                  : item.type === "negative"
                  ? "bg-destructive/10"
                  : "bg-muted"
              }`}
            >
              {item.type === "positive" ? (
                <ArrowUpRight className="h-3.5 w-3.5 text-success" />
              ) : item.type === "negative" ? (
                <ArrowDownRight className="h-3.5 w-3.5 text-destructive" />
              ) : (
                <Activity className="h-3.5 w-3.5 text-muted-foreground" />
              )}
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-foreground">{item.action}</p>
              <p className="text-xs text-muted-foreground truncate">{item.detail}</p>
            </div>
            <div className="flex items-center gap-1 text-xs text-muted-foreground shrink-0">
              <Clock className="h-3 w-3" />
              <span>{item.time}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
