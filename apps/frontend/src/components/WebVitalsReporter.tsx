"use client";

import { useEffect } from "react";

type WebVitalPayload = {
  name: "LCP" | "CLS" | "INP";
  value: number;
  id: string;
};

function postMetric(metric: WebVitalPayload): void {
  const payload = JSON.stringify({
    ...metric,
    path: typeof window !== "undefined" ? window.location.pathname : "",
    ts: Date.now(),
  });
  if (typeof navigator !== "undefined" && typeof navigator.sendBeacon === "function") {
    navigator.sendBeacon("/api/observability/web-vitals", payload);
    return;
  }
  void fetch("/api/observability/web-vitals", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: payload,
    keepalive: true,
  });
}

export function WebVitalsReporter() {
  useEffect(() => {
    if (typeof window === "undefined" || typeof PerformanceObserver === "undefined") return;

    const observers: PerformanceObserver[] = [];

    try {
      const lcpObserver = new PerformanceObserver((list) => {
        const entries = list.getEntries();
        const last = entries[entries.length - 1];
        if (!last) return;
        postMetric({ name: "LCP", value: last.startTime, id: String(last.startTime) });
      });
      lcpObserver.observe({ type: "largest-contentful-paint", buffered: true });
      observers.push(lcpObserver);
    } catch {}

    try {
      let clsValue = 0;
      const clsObserver = new PerformanceObserver((list) => {
        for (const entry of list.getEntries() as Array<PerformanceEntry & { value?: number; hadRecentInput?: boolean }>) {
          if (!entry.hadRecentInput) clsValue += entry.value ?? 0;
        }
        postMetric({ name: "CLS", value: clsValue, id: "cls" });
      });
      clsObserver.observe({ type: "layout-shift", buffered: true });
      observers.push(clsObserver);
    } catch {}

    try {
      const inpObserver = new PerformanceObserver((list) => {
        for (const entry of list.getEntries() as Array<PerformanceEntry & { duration?: number; interactionId?: number }>) {
          postMetric({
            name: "INP",
            value: entry.duration ?? 0,
            id: String(entry.interactionId ?? entry.startTime),
          });
        }
      });
      inpObserver.observe({ type: "event", buffered: true, durationThreshold: 40 } as PerformanceObserverInit);
      observers.push(inpObserver);
    } catch {}

    return () => {
      for (const observer of observers) observer.disconnect();
    };
  }, []);

  return null;
}
