import { NextRequest } from "next/server";

function getBackendBaseUrl(): string {
  const configured =
    process.env.BACKEND_API_URL ?? process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
  return configured.replace(/\/+$/, "");
}

function resolveRevalidateSeconds(joined: string): number | false {
  const p = joined.toLowerCase();
  if (p.startsWith("auth/")) return false;
  if (p.startsWith("feeds/")) return false;  // public feeds — always fresh
  if (p.includes("sync-runs/") || p.includes("sync-run")) return false;
  if (p.match(/^integrations\/[^/]+\/status/)) return 15;
  if (p.startsWith("dashboard/")) return false;
  if (p === "clients" || p.startsWith("clients/")) return false;
  if (p.startsWith("team/")) return 120;
  if (p.startsWith("company/")) return false;
  if (p.startsWith("storage")) return false;  // media library mutations + binary previews
  if (p.startsWith("user/")) return false;     // personal profile read/write
  return 30;
}

const HOP_BY_HOP_HEADERS = new Set([
  "connection",
  "keep-alive",
  "transfer-encoding",
  "te",
  "trailer",
  "upgrade",
  "proxy-authorization",
  "proxy-authenticate",
  "accept-encoding",
]);

function sanitizeRequestHeaders(incoming: Headers): Headers {
  const clean = new Headers();
  incoming.forEach((value, key) => {
    const lower = key.toLowerCase();
    if (HOP_BY_HOP_HEADERS.has(lower)) return;
    if (lower === "host") return;
    if (lower === "content-length") return;
    clean.set(key, value);
  });
  return clean;
}

async function proxy(req: NextRequest, path: string[]) {
  const backendBaseUrl = getBackendBaseUrl();
  const joined = path.join("/");
  const targetUrl = new URL(`${backendBaseUrl}/${joined}`);
  targetUrl.search = req.nextUrl.search;

  const headers = sanitizeRequestHeaders(req.headers);

  const method = req.method.toUpperCase();
  const hasBody = method !== "GET" && method !== "HEAD";
  const body = hasBody ? await req.arrayBuffer() : undefined;
  if (hasBody && body) {
    headers.set("content-length", String(body.byteLength));
  }

  const isRead = !hasBody;
  const ttl = isRead ? resolveRevalidateSeconds(joined) : false;
  const useCache = isRead && ttl !== false;

  let upstream: Response;
  try {
    upstream = await fetch(targetUrl.toString(), {
      method,
      headers,
      body,
      redirect: "manual",
      cache: useCache ? "force-cache" : "no-store",
      ...(useCache ? { next: { revalidate: ttl } } : {}),
    });
  } catch (err) {
    const message = err instanceof Error ? err.message : "Backend unavailable";
    return new Response(JSON.stringify({ detail: `Proxy error: ${message}` }), {
      status: 502,
      headers: { "Content-Type": "application/json" },
    });
  }

  const responseHeaders = new Headers(upstream.headers);
  responseHeaders.delete("content-encoding");
  responseHeaders.delete("content-length");

  return new Response(upstream.body, {
    status: upstream.status,
    statusText: upstream.statusText,
    headers: responseHeaders
  });
}

export async function GET(req: NextRequest, { params }: { params: { path: string[] } }) {
  return proxy(req, params.path);
}

export async function POST(req: NextRequest, { params }: { params: { path: string[] } }) {
  return proxy(req, params.path);
}

export async function PUT(req: NextRequest, { params }: { params: { path: string[] } }) {
  return proxy(req, params.path);
}

export async function PATCH(req: NextRequest, { params }: { params: { path: string[] } }) {
  return proxy(req, params.path);
}

export async function DELETE(req: NextRequest, { params }: { params: { path: string[] } }) {
  return proxy(req, params.path);
}

export async function OPTIONS(req: NextRequest, { params }: { params: { path: string[] } }) {
  return proxy(req, params.path);
}
