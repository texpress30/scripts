"use client";

import { useParams } from "next/navigation";
import Link from "next/link";
import React, { useCallback, useEffect, useMemo, useState } from "react";

import { AppShell } from "@/components/AppShell";
import { ProtectedPage } from "@/components/ProtectedPage";
import { apiRequest } from "@/lib/api";
import { normalizeCurrencyCode } from "@/lib/subAccountCurrency";
import { SubReportingNav } from "@/app/sub/[id]/_components/SubReportingNav";

import { WeeklyWorksheetTable, type WorksheetSection, type WorksheetWeek } from "./_components/WeeklyWorksheetTable";
import { FinancialCharts, SalesCharts, type OverviewChartsPayload } from "./_components/OverviewCharts";

type ClientItem = { id: number; name: string };
type WorksheetGranularity = "month" | "quarter" | "year";
type WorksheetPayload = {
  weeks: WorksheetWeek[];
  sections: WorksheetSection[];
  display_currency?: string;
  display_currency_source?: string;
  eur_ron_rate?: number | null;
  eur_ron_rate_scope?: { granularity: string; period_start: string; period_end: string };
  resolved_period?: { period_start: string; period_end: string };
};
type EurRonRateUpdateResponse = WorksheetPayload;

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

function buildOverviewPath(clientId: number, granularity: WorksheetGranularity, anchorDate: string): string {
  const query = new URLSearchParams({ granularity, anchor_date: anchorDate }).toString();
  return `/clients/${clientId}/media-tracker/overview-charts?${query}`;
}

export default function SubMediaTrackerPage() {
  const params = useParams<{ id: string }>();
  const clientId = Number(params.id);

  const [clientName, setClientName] = useState<string>(`Sub-account #${clientId}`);
  const [activeView, setActiveView] = useState<"sales" | "financial" | "worksheet">("sales");

  const [worksheetGranularity, setWorksheetGranularity] = useState<WorksheetGranularity>("month");
  const [worksheetAnchorDate, setWorksheetAnchorDate] = useState<string>(() => toIsoLocalDate(new Date()));
  const [worksheetData, setWorksheetData] = useState<WorksheetPayload | null>(null);
  const [worksheetLoading, setWorksheetLoading] = useState(false);
  const [worksheetError, setWorksheetError] = useState("");
  const [overviewData, setOverviewData] = useState<OverviewChartsPayload | null>(null);
  const [overviewLoading, setOverviewLoading] = useState(false);
  const [overviewError, setOverviewError] = useState("");
  const [eurRonDraft, setEurRonDraft] = useState("");
  const [eurRonSaving, setEurRonSaving] = useState(false);
  const [eurRonMessage, setEurRonMessage] = useState("");
  const [eurRonError, setEurRonError] = useState("");

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

  const loadOverview = useCallback(async () => {
    if (!Number.isFinite(clientId)) return;
    setOverviewLoading(true);
    setOverviewError("");
    try {
      const payload = await apiRequest<OverviewChartsPayload>(buildOverviewPath(clientId, worksheetGranularity, worksheetAnchorDate));
      setOverviewData(payload);
    } catch (err) {
      setOverviewData(null);
      setOverviewError(err instanceof Error ? err.message : "Nu am putut încărca graficele");
    } finally {
      setOverviewLoading(false);
    }
  }, [clientId, worksheetAnchorDate, worksheetGranularity]);

  useEffect(() => {
    if (activeView !== "worksheet") return;
    void loadWorksheet();
  }, [activeView, loadWorksheet]);

  useEffect(() => {
    if (activeView === "worksheet") return;
    void loadOverview();
  }, [activeView, loadOverview]);

  useEffect(() => {
    if (!worksheetData) {
      setEurRonDraft("");
      return;
    }
    setEurRonDraft(typeof worksheetData.eur_ron_rate === "number" && Number.isFinite(worksheetData.eur_ron_rate) ? String(worksheetData.eur_ron_rate) : "");
  }, [worksheetData?.eur_ron_rate]);

  const composedTitle = useMemo(() => `Media Tracker - ${clientName}`, [clientName]);
  const scopeLabel = useMemo(() => formatScopeLabel(worksheetAnchorDate, worksheetGranularity), [worksheetAnchorDate, worksheetGranularity]);
  const dataMonthKey = useMemo(() => worksheetAnchorDate.slice(0, 7), [worksheetAnchorDate]);

  const hasRows = !!worksheetData?.sections?.some((section) => section.rows.length > 0);
  const worksheetDisplayCurrency = normalizeCurrencyCode(worksheetData?.display_currency ?? overviewData?.display_currency, "USD");

  async function saveEurRonRate() {
    if (!Number.isFinite(clientId)) return;
    const normalized = eurRonDraft.trim();
    const parsed = Number(normalized);
    if (!normalized || !Number.isFinite(parsed) || parsed <= 0) {
      setEurRonError("Introdu un curs EUR/RON valid (număr pozitiv).");
      setEurRonMessage("");
      return;
    }

    setEurRonSaving(true);
    setEurRonError("");
    setEurRonMessage("");
    try {
      await apiRequest<EurRonRateUpdateResponse>(`/clients/${clientId}/media-tracker/worksheet/eur-ron-rate`, {
        method: "PUT",
        body: JSON.stringify({
          granularity: worksheetGranularity,
          anchor_date: worksheetAnchorDate,
          value: parsed,
        }),
      });
      await loadWorksheet();
      setEurRonMessage("Cursul EUR/RON a fost salvat.");
    } catch (err) {
      setEurRonError(err instanceof Error ? err.message : "Nu am putut salva cursul EUR/RON.");
    } finally {
      setEurRonSaving(false);
    }
  }

  async function saveEurRonRate() {
    if (!Number.isFinite(clientId)) return;
    const normalized = eurRonDraft.trim();
    const parsed = Number(normalized);
    if (!normalized || !Number.isFinite(parsed) || parsed <= 0) {
      setEurRonError("Introdu un curs EUR/RON valid (număr pozitiv).");
      setEurRonMessage("");
      return;
    }

    setEurRonSaving(true);
    setEurRonError("");
    setEurRonMessage("");
    try {
      await apiRequest<EurRonRateUpdateResponse>(`/clients/${clientId}/media-tracker/worksheet/eur-ron-rate`, {
        method: "PUT",
        body: JSON.stringify({
          granularity: worksheetGranularity,
          anchor_date: worksheetAnchorDate,
          value: parsed,
        }),
      });
      await loadWorksheet();
      setEurRonMessage("Cursul EUR/RON a fost salvat.");
    } catch (err) {
      setEurRonError(err instanceof Error ? err.message : "Nu am putut salva cursul EUR/RON.");
    } finally {
      setEurRonSaving(false);
    }
  }

  return (
    <ProtectedPage>
      <AppShell title={null}>
        <SubReportingNav clientId={clientId} />

        <section className="wm-card p-6">
          <h1 className="text-xl font-semibold text-slate-900">{composedTitle}</h1>
          <div className="mt-2 rounded-md border border-indigo-200 bg-indigo-50 px-3 py-2 text-sm text-indigo-900">
            <p>Valorile manuale se editează acum din pagina Data.</p>
            <Link href={`/sub/${clientId}/data?month=${dataMonthKey}`} className="mt-1 inline-block font-medium text-indigo-700 hover:text-indigo-800 hover:underline">
              Deschide pagina Data
            </Link>
          </div>

          <div className="mt-4 flex flex-wrap items-center gap-2">
            <button
              type="button"
              className={`rounded-md border px-3 py-1.5 text-sm ${activeView === "sales" ? "border-indigo-600 bg-indigo-50 text-indigo-700" : "border-slate-300 text-slate-700"}`}
              onClick={() => setActiveView("sales")}
            >
              Vânzări
            </button>
            <button
              type="button"
              className={`rounded-md border px-3 py-1.5 text-sm ${activeView === "financial" ? "border-indigo-600 bg-indigo-50 text-indigo-700" : "border-slate-300 text-slate-700"}`}
              onClick={() => setActiveView("financial")}
            >
              Financiare
            </button>
            <button
              type="button"
              className={`rounded-md border px-3 py-1.5 text-sm ${activeView === "worksheet" ? "border-indigo-600 bg-indigo-50 text-indigo-700" : "border-slate-300 text-slate-700"}`}
              onClick={() => setActiveView("worksheet")}
            >
              Fișă săptămânală
            </button>
          </div>

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
                    {item === "month" ? "Lună" : item === "quarter" ? "Trimestru" : "An"}
                  </button>
                ))}
              </div>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  className="rounded-md border border-slate-300 px-3 py-1.5 text-sm text-slate-700"
                  onClick={() => setWorksheetAnchorDate((prev) => shiftAnchorDate(prev, worksheetGranularity, -1))}
                >
                  Anterior
                </button>
                <span className="min-w-32 text-center text-sm font-medium text-slate-800">{scopeLabel}</span>
                <button
                  type="button"
                  className="rounded-md border border-slate-300 px-3 py-1.5 text-sm text-slate-700"
                  onClick={() => setWorksheetAnchorDate((prev) => shiftAnchorDate(prev, worksheetGranularity, 1))}
                >
                  Următor
                </button>
              </div>

              {activeView === "worksheet" ? (
                <div className="flex flex-wrap items-center gap-2 text-sm">
                  <span className="font-medium text-slate-700">Monedă: {worksheetDisplayCurrency}</span>
                  <span className="text-slate-300">|</span>
                  <span className="font-medium text-slate-700">EUR/RON</span>
                  <input
                    aria-label="Curs EUR/RON"
                    type="number"
                    step="0.0001"
                    min="0"
                    className="w-28 rounded border border-slate-300 px-2 py-1 text-slate-700"
                    value={eurRonDraft}
                    onChange={(event) => {
                      setEurRonDraft(event.target.value);
                      if (eurRonError) setEurRonError("");
                      if (eurRonMessage) setEurRonMessage("");
                    }}
                    disabled={eurRonSaving}
                  />
                  <button
                    type="button"
                    className="rounded border border-indigo-300 px-2 py-1 text-indigo-700 disabled:opacity-60"
                    onClick={() => void saveEurRonRate()}
                    disabled={eurRonSaving}
                  >
                    {eurRonSaving ? "Se salvează..." : "Salvează curs"}
                  </button>
                  <span className="text-xs text-slate-500">pentru {scopeLabel}</span>
                </div>
              ) : (
                <span className="text-sm text-slate-600">Monedă: {worksheetDisplayCurrency}</span>
              )}
            </div>

            {activeView === "sales" ? (
              <>
                {overviewLoading ? <div className="rounded-md border border-slate-200 bg-slate-50 p-4 text-sm text-slate-600">Se încarcă graficele de vânzări...</div> : null}
                {!overviewLoading && overviewError ? <div className="rounded-md border border-rose-200 bg-rose-50 p-4 text-sm text-rose-700">{overviewError}</div> : null}
                {!overviewLoading && !overviewError && overviewData ? <SalesCharts payload={overviewData} /> : null}
              </>
            ) : null}

            {activeView === "financial" ? (
              <>
                {overviewLoading ? <div className="rounded-md border border-slate-200 bg-slate-50 p-4 text-sm text-slate-600">Se încarcă graficele financiare...</div> : null}
                {!overviewLoading && overviewError ? <div className="rounded-md border border-rose-200 bg-rose-50 p-4 text-sm text-rose-700">{overviewError}</div> : null}
                {!overviewLoading && !overviewError && overviewData ? <FinancialCharts payload={overviewData} /> : null}
              </>
            ) : null}

            {activeView === "worksheet" ? (
              <>
                {eurRonMessage ? <div className="rounded-md border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-700">{eurRonMessage}</div> : null}
                {eurRonError ? <div className="rounded-md border border-rose-200 bg-rose-50 p-3 text-sm text-rose-700">{eurRonError}</div> : null}

                {worksheetLoading ? <div className="rounded-md border border-slate-200 bg-slate-50 p-4 text-sm text-slate-600">Se încarcă fișa săptămânală...</div> : null}
                {!worksheetLoading && worksheetError ? <div className="rounded-md border border-rose-200 bg-rose-50 p-4 text-sm text-rose-700">{worksheetError}</div> : null}
                {!worksheetLoading && !worksheetError && worksheetData && !hasRows ? <div className="rounded-md border border-slate-200 bg-slate-50 p-4 text-sm text-slate-600">Nu există rânduri pentru scope-ul selectat.</div> : null}

                {!worksheetLoading && !worksheetError && worksheetData && hasRows ? (
                  <WeeklyWorksheetTable weeks={worksheetData.weeks} sections={worksheetData.sections} displayCurrency={worksheetDisplayCurrency} />
                ) : null}
              </>
            ) : null}
          </div>
        </section>
      </AppShell>
    </ProtectedPage>
  );
}
