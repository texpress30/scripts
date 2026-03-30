"use client";

import { DayPicker, type DateRange } from "react-day-picker";
import "react-day-picker/dist/style.css";

export function DayRangePicker({
  selected,
  onSelect,
  defaultMonth,
}: {
  selected: DateRange;
  onSelect: (range: DateRange | undefined) => void;
  defaultMonth?: Date;
}) {
  return (
    <DayPicker
      mode="range"
      numberOfMonths={2}
      selected={selected}
      onSelect={onSelect}
      defaultMonth={defaultMonth}
    />
  );
}
