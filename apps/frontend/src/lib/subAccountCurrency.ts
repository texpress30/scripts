export function normalizeCurrencyCode(value: string | null | undefined, fallback: string = "USD"): string {
  const code = String(value ?? "").trim().toUpperCase();
  if (/^[A-Z]{3}$/.test(code)) return code;
  const normalizedFallback = String(fallback).trim().toUpperCase();
  return /^[A-Z]{3}$/.test(normalizedFallback) ? normalizedFallback : "USD";
}

export function formatCurrencyValue(
  value: number | null | undefined,
  currencyCode: string | null | undefined,
  fallbackCurrencyCode: string = "USD",
): string {
  if (typeof value !== "number" || !Number.isFinite(value)) return "—";
  const code = normalizeCurrencyCode(currencyCode, fallbackCurrencyCode);
  return new Intl.NumberFormat(undefined, { style: "currency", currency: code, maximumFractionDigits: 2 }).format(value);
}

export function formatWorksheetValueByKind({
  value,
  valueKind,
  currencyCode,
  displayCurrency,
}: {
  value: number | null | undefined;
  valueKind: string | undefined;
  currencyCode?: string | null;
  displayCurrency?: string | null;
}): string {
  if (typeof value !== "number" || !Number.isFinite(value)) return "—";

  if (valueKind === "currency_display") {
    return formatCurrencyValue(value, currencyCode ?? displayCurrency, displayCurrency ?? "USD");
  }
  if (valueKind === "currency_eur") {
    return formatCurrencyValue(value, "EUR", "EUR");
  }
  if (valueKind === "currency_ron") {
    return formatCurrencyValue(value, "RON", "USD");
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
