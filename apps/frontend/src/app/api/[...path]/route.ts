import { NextRequest } from "next/server";

function getBackendBaseUrl(): string {
  const configured =
    process.env.BACKEND_API_URL ?? process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
  return configured.replace(/\/+$/, "");
}

function resolveRevalidateSeconds(joined: string): number | false {
  const p = joined.toLowerCase();
  if (p.startsWith("auth/")) return false;
  if (p.includes("sync-runs/") || p.includes("sync-run")) return false;
  if (p.match(/^integrations\/[^/]+\/status/)) return 15;
  if (p.startsWith("dashboard/")) return 30;
  if (p === "clients" || p.startsWith("clients/")) return false;
  if (p.startsWith("team/")) return 120;
  if (p.startsWith("company/")) return false;
  return 30;
}

async function proxy(req: NextRequest, path: string[]) {
  const backendBaseUrl = getBackendBaseUrl();
  const joined = path.join("/");
  const targetUrl = new URL(`${backendBaseUrl}/${joined}`);
  targetUrl.search = req.nextUrl.search;

  const headers = new Headers(req.headers);
  headers.delete("host");

  const method = req.method.toUpperCase();
  const body = method === "GET" || method === "HEAD" ? undefined : await req.arrayBuffer();
  const isRead = method === "GET" || method === "HEAD";

  const ttl = isRead ? resolveRevalidateSeconds(joined) : false;
  const useCache = isRead && ttl !== false;

  const upstream = await fetch(targetUrl.toString(), {
    method,
    headers,
    body,
    redirect: "manual",
    cache: useCache ? "force-cache" : "no-store",
    ...(useCache ? { next: { revalidate: ttl } } : {}),
  });

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
