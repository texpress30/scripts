"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import React, { useCallback, useEffect, useMemo, useState } from "react";

import { AppShell } from "@/components/AppShell";
import { ProtectedPage } from "@/components/ProtectedPage";
import { apiRequest } from "@/lib/api";

import { WeeklyWorksheetTable, type WorksheetSection, type WorksheetWeek } from "./_components/WeeklyWorksheetTable";

type ClientItem = { id: number; name: string };
type WorksheetGranularity = "month" | "quarter" | "year";
type WorksheetPayload = {
  weeks: WorksheetWeek[];
  sections: WorksheetSection[];
  resolved_period?: { period_start: string; period_end: string };
};

function toIsoLocalDate(value: Date): string {
  const year = value.getFullYear();
  const month = String(value.getMonth() + 1).padStart(2, "0");
  const day = String(value.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function parseIsoLocalDate(value: string): Date {
  const [year, month, day] = value.split("-").map(Number);
  return new Date(year, (month || 1) - 1, day || 1);
}

function shiftAnchorDate(anchorDate: string, granularity: WorksheetGranularity, direction: -1 | 1): string {
  const base = parseIsoLocalDate(anchorDate);
  const next = new Date(base.getFullYear(), base.getMonth(), base.getDate());
  if (granularity === "month") next.setMonth(next.getMonth() + direction);
  if (granularity === "quarter") next.setMonth(next.getMonth() + (3 * direction));
  if (granularity === "year") next.setFullYear(next.getFullYear() + direction);
  return toIsoLocalDate(next);
}

function formatScopeLabel(anchorDate: string, granularity: WorksheetGranularity): string {
  const date = parseIsoLocalDate(anchorDate);
  if (granularity === "year") return String(date.getFullYear());
  if (granularity === "quarter") {
    const quarter = Math.floor(date.getMonth() / 3) + 1;
    return `Q${quarter} ${date.getFullYear()}`;
  }
  return new Intl.DateTimeFormat(undefined, { month: "long", year: "numeric" }).format(date);
}

function isWorksheetPayload(value: unknown): value is WorksheetPayload {
  if (!value || typeof value !== "object") return false;
  const candidate = value as Record<string, unknown>;
  if (!Array.isArray(candidate.weeks) || !Array.isArray(candidate.sections)) return false;
  return true;
}

function buildWorksheetPath(clientId: number, granularity: WorksheetGranularity, anchorDate: string): string {
  const query = new URLSearchParams({ granularity, anchor_date: anchorDate }).toString();
  return `/clients/${clientId}/media-tracker/worksheet-foundation?${query}`;
}

export default function SubMediaTrackerPage() {
  const params = useParams<{ id: string }>();
  const clientId = Number(params.id);

  const [clientName, setClientName] = useState<string>(`Sub-account #${clientId}`);
  const [activeView, setActiveView] = useState<"overview" | "worksheet">("overview");

  const [worksheetGranularity, setWorksheetGranularity] = useState<WorksheetGranularity>("month");
  const [worksheetAnchorDate, setWorksheetAnchorDate] = useState<string>(() => toIsoLocalDate(new Date()));
  const [worksheetData, setWorksheetData] = useState<WorksheetPayload | null>(null);
  const [worksheetLoading, setWorksheetLoading] = useState(false);
  const [worksheetError, setWorksheetError] = useState("");

  useEffect(() => {
    let ignore = false;

    async function loadClientName() {
      try {
        const result = await apiRequest<{ items: ClientItem[] }>("/clients");
        const match = result.items.find((item) => item.id === clientId);
        if (!ignore && match?.name) setClientName(match.name);
      } catch {
        if (!ignore) setClientName(`Sub-account #${clientId}`);
      }
    }

    if (Number.isFinite(clientId)) void loadClientName();

    return () => {
      ignore = true;
    };
  }, [clientId]);

  const loadWorksheet = useCallback(async () => {
    if (!Number.isFinite(clientId)) return;
    setWorksheetLoading(true);
    setWorksheetError("");
    try {
      const payload = await apiRequest<WorksheetPayload>(
        buildWorksheetPath(clientId, worksheetGranularity, worksheetAnchorDate)
      );
      if (!isWorksheetPayload(payload)) throw new Error("Răspuns worksheet invalid");
      setWorksheetData(payload);
    } catch (err) {
      setWorksheetData(null);
      setWorksheetError(err instanceof Error ? err.message : "Nu am putut încărca worksheet-ul");
    } finally {
      setWorksheetLoading(false);
    }
  }, [clientId, worksheetAnchorDate, worksheetGranularity]);

  useEffect(() => {
    if (activeView !== "worksheet") return;
    void loadWorksheet();
  }, [activeView, loadWorksheet]);


  const saveManualCell = useCallback(async ({ fieldKey, weekStart, value }: { fieldKey: string; weekStart: string; value: number | null }) => {
    if (!Number.isFinite(clientId)) throw new Error("Client invalid");
    const payload = await apiRequest<WorksheetPayload>(
      `/clients/${clientId}/media-tracker/worksheet/manual-values`,
      {
        method: "PUT",
        body: JSON.stringify({
          granularity: worksheetGranularity,
          anchor_date: worksheetAnchorDate,
          entries: [{ week_start: weekStart, field_key: fieldKey, value }],
        }),
      }
    );
    if (!isWorksheetPayload(payload)) throw new Error("Răspuns worksheet invalid");
    setWorksheetData(payload);
    setWorksheetError("");
  }, [clientId, worksheetAnchorDate, worksheetGranularity]);

  const composedTitle = useMemo(() => `Media Tracker - ${clientName}`, [clientName]);
  const scopeLabel = useMemo(() => formatScopeLabel(worksheetAnchorDate, worksheetGranularity), [worksheetAnchorDate, worksheetGranularity]);

  const hasRows = !!worksheetData?.sections?.some((section) => section.rows.length > 0);

  return (
    <ProtectedPage>
      <AppShell title={null}>
        <div className="mb-4 flex items-center gap-4 text-sm">
          <Link href={`/sub/${clientId}/media-buying`} className="text-indigo-600 transition-colors hover:text-indigo-700 hover:underline">Media Buying</Link>
          <Link href={`/sub/${clientId}/media-tracker`} className="text-indigo-600 transition-colors hover:text-indigo-700 hover:underline">Media Tracker</Link>
        </div>

        <section className="wm-card p-6">
          <h1 className="text-xl font-semibold text-slate-900">{composedTitle}</h1>

          <div className="mt-4 flex flex-wrap items-center gap-2">
            <button
              type="button"
              className={`rounded-md border px-3 py-1.5 text-sm ${activeView === "overview" ? "border-indigo-600 bg-indigo-50 text-indigo-700" : "border-slate-300 text-slate-700"}`}
              onClick={() => setActiveView("overview")}
            >
              Overview
            </button>
            <button
              type="button"
              className={`rounded-md border px-3 py-1.5 text-sm ${activeView === "worksheet" ? "border-indigo-600 bg-indigo-50 text-indigo-700" : "border-slate-300 text-slate-700"}`}
              onClick={() => setActiveView("worksheet")}
            >
              Weekly Worksheet
            </button>
          </div>

          {activeView === "overview" ? (
            <div className="mt-4 rounded-lg border border-dashed border-slate-300 bg-slate-50 p-6 text-sm text-slate-600">Coming Soon</div>
          ) : (
            <div className="mt-4 space-y-4">
              <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-slate-200 bg-white p-3">
                <div className="flex items-center gap-2">
                  {(["month", "quarter", "year"] as WorksheetGranularity[]).map((item) => (
                    <button
                      key={item}
                      type="button"
                      className={`rounded-md border px-3 py-1.5 text-sm capitalize ${worksheetGranularity === item ? "border-indigo-600 bg-indigo-50 text-indigo-700" : "border-slate-300 text-slate-700"}`}
                      onClick={() => setWorksheetGranularity(item)}
                    >
                      {item}
                    </button>
                  ))}
                </div>
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    className="rounded-md border border-slate-300 px-3 py-1.5 text-sm text-slate-700"
                    onClick={() => setWorksheetAnchorDate((prev) => shiftAnchorDate(prev, worksheetGranularity, -1))}
                  >
                    Previous
                  </button>
                  <span className="min-w-32 text-center text-sm font-medium text-slate-800">{scopeLabel}</span>
                  <button
                    type="button"
                    className="rounded-md border border-slate-300 px-3 py-1.5 text-sm text-slate-700"
                    onClick={() => setWorksheetAnchorDate((prev) => shiftAnchorDate(prev, worksheetGranularity, 1))}
                  >
                    Next
                  </button>
                </div>
              </div>

              {worksheetLoading ? <div className="rounded-md border border-slate-200 bg-slate-50 p-4 text-sm text-slate-600">Loading worksheet...</div> : null}
              {!worksheetLoading && worksheetError ? <div className="rounded-md border border-rose-200 bg-rose-50 p-4 text-sm text-rose-700">{worksheetError}</div> : null}
              {!worksheetLoading && !worksheetError && worksheetData && !hasRows ? <div className="rounded-md border border-slate-200 bg-slate-50 p-4 text-sm text-slate-600">No worksheet rows for selected scope.</div> : null}

              {!worksheetLoading && !worksheetError && worksheetData && hasRows ? (
                <WeeklyWorksheetTable weeks={worksheetData.weeks} sections={worksheetData.sections} onManualCellCommit={saveManualCell} />
              ) : null}
            </div>
          )}
        </section>
      </AppShell>
    </ProtectedPage>
  );
}
