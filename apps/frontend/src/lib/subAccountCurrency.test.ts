import { describe, expect, it } from "vitest";

import { formatCurrencyValue, formatWorksheetValueByKind, normalizeCurrencyCode } from "./subAccountCurrency";

describe("subAccountCurrency", () => {
  it("normalizes currency codes with safe fallback", () => {
    expect(normalizeCurrencyCode(" usd ")).toBe("USD");
    expect(normalizeCurrencyCode("xx", "eur")).toBe("EUR");
    expect(normalizeCurrencyCode(undefined, "bad")).toBe("BAD");
  });

  it("formats worksheet currency_display using row currency then display fallback", () => {
    expect(formatWorksheetValueByKind({ value: 100, valueKind: "currency_display", currencyCode: "USD", displayCurrency: "RON" })).toBe(
      formatCurrencyValue(100, "USD", "RON"),
    );
    expect(formatWorksheetValueByKind({ value: 100, valueKind: "currency_display", currencyCode: undefined, displayCurrency: "EUR" })).toBe(
      formatCurrencyValue(100, "EUR", "EUR"),
    );
  });

  it("keeps EUR rows and null placeholders safe", () => {
    expect(formatWorksheetValueByKind({ value: 100, valueKind: "currency_eur", displayCurrency: "USD" })).toBe(
      formatCurrencyValue(100, "EUR", "EUR"),
    );
    expect(formatWorksheetValueByKind({ value: null, valueKind: "currency_display", displayCurrency: "USD" })).toBe("—");
  });
});
