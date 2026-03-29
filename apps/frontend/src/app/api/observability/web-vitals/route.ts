import { NextRequest } from "next/server";

export async function POST(req: NextRequest) {
  try {
    const payload = (await req.json()) as Record<string, unknown>;
    const name = String(payload.name ?? "");
    const value = Number(payload.value ?? 0);
    const path = String(payload.path ?? "");
    if (name && Number.isFinite(value)) {
      // Centralized browser metric logging for baseline and regressions.
      console.info("web_vital", { name, value, path, id: payload.id ?? null, ts: payload.ts ?? null });
    }
  } catch {
    // ignore malformed payloads to avoid affecting UX
  }
  return new Response(null, { status: 204 });
}
