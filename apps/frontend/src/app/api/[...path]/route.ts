import { NextRequest } from "next/server";

function getBackendBaseUrl(): string {
  const configured =
    process.env.BACKEND_API_URL ?? process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
  return configured.replace(/\/+$/, "");
}

async function proxy(req: NextRequest, path: string[]) {
  const backendBaseUrl = getBackendBaseUrl();
  const targetUrl = new URL(`${backendBaseUrl}/${path.join("/")}`);
  targetUrl.search = req.nextUrl.search;

  const headers = new Headers(req.headers);
  headers.delete("host");

  const method = req.method.toUpperCase();
  const body = method === "GET" || method === "HEAD" ? undefined : await req.arrayBuffer();
  const isRead = method === "GET" || method === "HEAD";

  const upstream = await fetch(targetUrl.toString(), {
    method,
    headers,
    body,
    redirect: "manual",
    cache: isRead ? "force-cache" : "no-store",
    ...(isRead ? { next: { revalidate: 30 } } : {}),
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
