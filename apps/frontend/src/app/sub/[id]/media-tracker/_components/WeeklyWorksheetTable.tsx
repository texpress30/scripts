import React, { useMemo, useRef, useState } from "react";

import { formatWorksheetValueByKind } from "@/lib/subAccountCurrency";

export type WorksheetWeek = { week_start: string; week_end: string; label?: string };
export type WorksheetRowValue = { week_start: string; week_end: string; value: number | null };
export type WorksheetRow = {
  row_key: string;
  label: string;
  history_value: number | null;
  value_kind?: string;
  currency_code?: string | null;
  source_kind?: string;
  is_manual_input_row?: boolean;
  dependencies?: string[];
  weekly_values: WorksheetRowValue[];
};
export type WorksheetSection = { key: string; label: string; rows: WorksheetRow[] };

const DASHED_COL = "border-r border-black border-dashed";
const MEDIA_BUYING_GREY_TEXT_CLASS = "text-[#bfbfbf]";

function formatWorksheetValue(
  value: number | null | undefined,
  valueKind: string | undefined,
  currencyCode: string | null | undefined,
  displayCurrency: string,
): string {
  return formatWorksheetValueByKind({
    value,
    valueKind,
    currencyCode,
    displayCurrency,
  });
}

function rowLabelClass(row: WorksheetRow): string {
  if (row.source_kind === "comparison") return "px-3 py-2 pr-6 text-right text-slate-500 italic";
  return "px-3 py-2 text-right text-slate-800";
}

function rowCellClass(row: WorksheetRow): string {
  if (row.source_kind === "comparison") return "px-3 py-2 text-right text-slate-500";
  return "px-3 py-2 text-right text-slate-700";
}

function isoWeekNumberFromWeekStart(weekStart: string): number {
  const [year, month, day] = weekStart.split("-").map(Number);
  const date = new Date(Date.UTC(year, (month || 1) - 1, day || 1));
  const dayNumber = date.getUTCDay() || 7;
  date.setUTCDate(date.getUTCDate() + 4 - dayNumber);
  const isoYearStart = new Date(Date.UTC(date.getUTCFullYear(), 0, 1));
  return Math.ceil((((date.getTime() - isoYearStart.getTime()) / 86400000) + 1) / 7);
}

function getManualFieldKey(row: WorksheetRow): string | null {
  if (!row.is_manual_input_row || row.source_kind !== "manual") return null;
  if (!Array.isArray(row.dependencies)) return null;
  const manualDep = row.dependencies.find((item) => String(item).startsWith("manual_metrics."));
  if (!manualDep) return null;
  return manualDep.replace("manual_metrics.", "").trim() || null;
}

function EditableWeeklyCell(
  {
    value,
    valueKind,
    currencyCode,
    displayCurrency,
    fieldKey,
    weekStart,
    onCommit,
  }: {
    value: number | null;
    valueKind: string | undefined;
    currencyCode: string | null | undefined;
    displayCurrency: string;
    fieldKey: string;
    weekStart: string;
    onCommit: (payload: { fieldKey: string; weekStart: string; value: number | null }) => Promise<void>;
  }
) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState<string>(value == null ? "" : String(value));
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string>("");
  const submittingRef = useRef(false);

  const displayValue = useMemo(() => formatWorksheetValue(value, valueKind, currencyCode, displayCurrency), [value, valueKind, currencyCode, displayCurrency]);

  const submit = async () => {
    if (submittingRef.current || saving) return;
    const normalized = draft.trim();
    const parsed = normalized === "" ? null : Number(normalized);
    if (normalized !== "" && !Number.isFinite(parsed)) {
      setError("Valoare invalidă");
      return;
    }

    submittingRef.current = true;
    setSaving(true);
    setError("");
    try {
      await onCommit({ fieldKey, weekStart, value: parsed });
      setEditing(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Nu am putut salva");
    } finally {
      submittingRef.current = false;
      setSaving(false);
    }
  };

  if (!editing) {
    return (
      <div className="space-y-1">
        <button
          type="button"
          className="w-full cursor-text rounded px-1 py-0.5 text-right transition-colors hover:bg-indigo-50"
          onClick={() => {
            setDraft(value == null ? "" : String(value));
            setError("");
            setEditing(true);
          }}
        >
          {displayValue}
        </button>
        {error ? <div className="text-xs text-rose-600">{error}</div> : null}
      </div>
    );
  }

  return (
    <div className="space-y-1">
      <input
        autoFocus
        value={draft}
        disabled={saving}
        inputMode="decimal"
        className="w-full rounded border border-indigo-300 bg-white px-2 py-1 text-right text-sm"
        onChange={(event) => {
          setDraft(event.target.value);
          if (error) setError("");
        }}
        onBlur={() => {
          void submit();
        }}
        onKeyDown={(event) => {
          if (event.key === "Enter") {
            event.preventDefault();
            void submit();
          }
          if (event.key === "Escape") {
            event.preventDefault();
            setDraft(value == null ? "" : String(value));
            setError("");
            setEditing(false);
          }
        }}
      />
      {saving ? <div className="text-xs text-slate-500">Saving...</div> : null}
      {error ? <div className="text-xs text-rose-600">{error}</div> : null}
    </div>
  );
}

export function WeeklyWorksheetTable(
  {
    weeks,
    sections,
    displayCurrency,
    onManualCellCommit,
  }: {
    weeks: WorksheetWeek[];
    sections: WorksheetSection[];
    displayCurrency: string;
    onManualCellCommit?: (payload: { fieldKey: string; weekStart: string; value: number | null }) => Promise<void>;
  }
) {
  return (
    <div className="overflow-auto rounded-lg border border-slate-200">
      <table className="min-w-full text-sm">
        <thead>
          <tr className="bg-slate-100">
            <th className={`sticky left-0 z-20 min-w-56 border-b border-slate-200 bg-slate-100 px-3 py-2 text-left font-semibold text-slate-800 ${DASHED_COL}`}>Săptămâna</th>
            <th className={`min-w-32 border-b border-slate-200 px-3 py-2 text-right font-semibold ${MEDIA_BUYING_GREY_TEXT_CLASS} ${DASHED_COL}`}>Istorie</th>
            {weeks.map((week) => (
              <th key={`week-index:${week.week_start}`} className={`min-w-32 border-b border-slate-200 px-3 py-2 text-right font-semibold text-slate-700 ${DASHED_COL}`}>
                Săpt. {isoWeekNumberFromWeekStart(week.week_start)}
              </th>
            ))}
          </tr>
          <tr className="bg-slate-50">
            <th className={`sticky left-0 z-20 border-b border-slate-200 bg-slate-50 px-3 py-2 text-left font-medium text-slate-600 ${DASHED_COL}`}>Data Începere</th>
            <th className={`border-b border-slate-200 px-3 py-2 text-right text-slate-500 ${DASHED_COL}`}>&nbsp;</th>
            {weeks.map((week) => (
              <th key={`week-start:${week.week_start}`} className={`border-b border-slate-200 px-3 py-2 text-right font-medium text-slate-600 ${DASHED_COL}`}>
                {week.week_start}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {sections.map((section) => (
            <React.Fragment key={section.key}>
              <tr className="bg-slate-200/70">
                <td colSpan={2 + weeks.length} className={`px-3 py-2 text-left font-semibold text-slate-800 ${DASHED_COL}`}>{section.label}</td>
              </tr>
              {section.rows.map((row) => {
                const manualFieldKey = getManualFieldKey(row);
                return (
                  <tr key={`${section.key}:${row.row_key}`} className="border-t border-slate-100">
                    <td className={`sticky left-0 z-10 bg-white ${rowLabelClass(row)} ${DASHED_COL}`}>{row.label}</td>
                    <td data-testid={`history-${section.key}-${row.row_key}`} className={`${rowCellClass(row)} ${MEDIA_BUYING_GREY_TEXT_CLASS} ${DASHED_COL}`}>{formatWorksheetValue(row.history_value, row.value_kind, row.currency_code, displayCurrency)}</td>
                    {row.weekly_values.map((cell) => {
                      const editable = !!manualFieldKey && typeof onManualCellCommit === "function";
                      return (
                        <td key={`${row.row_key}:${cell.week_start}`} data-testid={`cell-${section.key}-${row.row_key}-${cell.week_start}`} className={`${rowCellClass(row)} ${DASHED_COL}`}>
                          {editable ? (
                            <EditableWeeklyCell
                              value={cell.value}
                              valueKind={row.value_kind}
                              currencyCode={row.currency_code}
                              displayCurrency={displayCurrency}
                              fieldKey={manualFieldKey}
                              weekStart={cell.week_start}
                              onCommit={onManualCellCommit}
                            />
                          ) : formatWorksheetValue(cell.value, row.value_kind, row.currency_code, displayCurrency)}
                        </td>
                      );
                    })}
                  </tr>
                );
              })}
            </React.Fragment>
          ))}
        </tbody>
      </table>
    </div>
  );
}
