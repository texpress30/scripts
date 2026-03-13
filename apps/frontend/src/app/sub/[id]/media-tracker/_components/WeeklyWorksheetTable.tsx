import React from "react";

export type WorksheetWeek = { week_start: string; week_end: string; label?: string };
export type WorksheetRowValue = { week_start: string; week_end: string; value: number | null };
export type WorksheetRow = {
  row_key: string;
  label: string;
  history_value: number | null;
  value_kind?: string;
  source_kind?: string;
  weekly_values: WorksheetRowValue[];
};
export type WorksheetSection = { key: string; label: string; rows: WorksheetRow[] };

function formatWorksheetValue(value: number | null | undefined, valueKind: string | undefined): string {
  if (typeof value !== "number" || !Number.isFinite(value)) return "—";

  if (valueKind === "currency_ron") {
    return new Intl.NumberFormat(undefined, { style: "currency", currency: "RON", maximumFractionDigits: 2 }).format(value);
  }
  if (valueKind === "currency_eur") {
    return new Intl.NumberFormat(undefined, { style: "currency", currency: "EUR", maximumFractionDigits: 2 }).format(value);
  }
  if (valueKind === "integer") {
    return Math.trunc(value).toLocaleString();
  }
  if (valueKind === "percent_ratio") {
    return `${(value * 100).toFixed(2)}%`;
  }
  if (valueKind === "decimal") {
    return value.toLocaleString(undefined, { maximumFractionDigits: 4 });
  }

  return value.toLocaleString(undefined, { maximumFractionDigits: 4 });
}

function rowLabelClass(row: WorksheetRow): string {
  if (row.source_kind === "comparison") return "px-3 py-2 pl-6 text-slate-500 italic";
  return "px-3 py-2 text-slate-800";
}

function rowCellClass(row: WorksheetRow): string {
  if (row.source_kind === "comparison") return "px-3 py-2 text-right text-slate-500";
  return "px-3 py-2 text-right text-slate-700";
}

export function WeeklyWorksheetTable({ weeks, sections }: { weeks: WorksheetWeek[]; sections: WorksheetSection[] }) {
  return (
    <div className="overflow-auto rounded-lg border border-slate-200">
      <table className="min-w-full text-sm">
        <thead>
          <tr className="bg-slate-100">
            <th className="sticky left-0 z-20 min-w-56 border-b border-slate-200 bg-slate-100 px-3 py-2 text-left font-semibold text-slate-800">Săptămâna</th>
            <th className="min-w-32 border-b border-slate-200 px-3 py-2 text-right font-semibold text-slate-800">Istorie</th>
            {weeks.map((week, idx) => (
              <th key={`week-index:${week.week_start}`} className="min-w-32 border-b border-slate-200 px-3 py-2 text-right font-semibold text-slate-700">
                Săpt. {idx + 1}
              </th>
            ))}
          </tr>
          <tr className="bg-slate-50">
            <th className="sticky left-0 z-20 border-b border-slate-200 bg-slate-50 px-3 py-2 text-left font-medium text-slate-600">Data Începere</th>
            <th className="border-b border-slate-200 px-3 py-2 text-right text-slate-500">&nbsp;</th>
            {weeks.map((week) => (
              <th key={`week-start:${week.week_start}`} className="border-b border-slate-200 px-3 py-2 text-right font-medium text-slate-600">
                {week.week_start}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {sections.map((section) => (
            <React.Fragment key={section.key}>
              <tr className="bg-slate-200/70">
                <td colSpan={2 + weeks.length} className="px-3 py-2 text-left font-semibold text-slate-800">{section.label}</td>
              </tr>
              {section.rows.map((row) => (
                <tr key={`${section.key}:${row.row_key}`} className="border-t border-slate-100">
                  <td className={`sticky left-0 z-10 bg-white ${rowLabelClass(row)}`}>{row.label}</td>
                  <td className={rowCellClass(row)}>{formatWorksheetValue(row.history_value, row.value_kind)}</td>
                  {row.weekly_values.map((cell) => (
                    <td key={`${row.row_key}:${cell.week_start}`} className={rowCellClass(row)}>
                      {formatWorksheetValue(cell.value, row.value_kind)}
                    </td>
                  ))}
                </tr>
              ))}
            </React.Fragment>
          ))}
        </tbody>
      </table>
    </div>
  );
}
