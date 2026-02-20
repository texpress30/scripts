const TRUE_VALUES = new Set(["1", "true", "yes", "on"]);

export function isTikTokIntegrationEnabled(): boolean {
  const value = process.env.NEXT_PUBLIC_FF_TIKTOK_INTEGRATION ?? "";
  return TRUE_VALUES.has(value.trim().toLowerCase());
}
