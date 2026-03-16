import React from "react";
import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";

import { WeeklyWorksheetTable } from "./WeeklyWorksheetTable";

describe("WeeklyWorksheetTable label alignment", () => {
  it("aligns normal and comparison row labels to the right while keeping comparison styling", () => {
    render(
      <WeeklyWorksheetTable
        displayCurrency="RON"
        weeks={[{ week_start: "2026-03-02", week_end: "2026-03-08" }]}
        sections={[
          {
            key: "meta_spend",
            label: "Meta Spend",
            rows: [
              {
                row_key: "cost",
                label: "Cost",
                history_value: 100,
                source_kind: "computed",
                value_kind: "currency_display",
                currency_code: "RON",
                weekly_values: [{ week_start: "2026-03-02", week_end: "2026-03-08", value: 10 }],
              },
              {
                row_key: "cost_wow_pct",
                label: "%",
                history_value: null,
                source_kind: "comparison",
                value_kind: "percent_ratio",
                weekly_values: [{ week_start: "2026-03-02", week_end: "2026-03-08", value: null }],
              },
            ],
          },
        ]}
      />
    );

    const normalLabelCell = screen.getByText("Cost").closest("td");
    const comparisonLabelCell = screen.getByText("%").closest("td");

    expect(normalLabelCell).toBeTruthy();
    expect(normalLabelCell?.className).toContain("text-right");
    expect(normalLabelCell?.className).toContain("sticky");

    expect(comparisonLabelCell).toBeTruthy();
    expect(comparisonLabelCell?.className).toContain("text-right");
    expect(comparisonLabelCell?.className).toContain("italic");
    expect(comparisonLabelCell?.className).toContain("text-slate-500");
    expect(comparisonLabelCell?.className).toContain("pr-6");
    expect(comparisonLabelCell?.className).not.toContain("pl-6");
  });
});
