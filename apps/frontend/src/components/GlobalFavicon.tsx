"use client";

import { useEffect, useMemo, useState } from "react";

export const DEFAULT_FAVICON_HREF = "/icon.svg";
const MANAGED_ATTR = "data-global-favicon-managed";

function withVersion(href: string, refreshKey: number): string {
  const value = String(href || "").trim();
  if (!value) return DEFAULT_FAVICON_HREF;
  const separator = value.includes("?") ? "&" : "?";
  return `${value}${separator}v=${refreshKey}`;
}

export function resolveAgencyFaviconHref(agencyLogoUrl: string | null | undefined, refreshKey: number): string {
  const logoUrl = String(agencyLogoUrl || "").trim();
  if (!logoUrl) return DEFAULT_FAVICON_HREF;
  return withVersion(logoUrl, refreshKey);
}

function isShortcutIconLink(link: HTMLLinkElement): boolean {
  return link.rel.toLowerCase().trim() === "shortcut icon";
}

function isIconLink(link: HTMLLinkElement): boolean {
  const rel = link.rel.toLowerCase();
  if (isShortcutIconLink(link)) return true;
  return rel.split(/\s+/).includes("icon");
}

function ensureManagedLink(head: HTMLHeadElement, rel: "icon" | "shortcut icon"): HTMLLinkElement {
  const existing = head.querySelector(`link[${MANAGED_ATTR}=\"true\"][rel=\"${rel}\"]`) as HTMLLinkElement | null;
  if (existing) return existing;
  const existingUnmanaged = head.querySelector(`link[rel=\"${rel}\"]`) as HTMLLinkElement | null;
  if (existingUnmanaged) {
    existingUnmanaged.setAttribute(MANAGED_ATTR, "true");
    return existingUnmanaged;
  }
  const link = document.createElement("link");
  link.setAttribute(MANAGED_ATTR, "true");
  link.rel = rel;
  head.appendChild(link);
  return link;
}

export function applyGlobalFavicon(href: string): void {
  const head = document.head;
  const links = Array.from(head.querySelectorAll("link")).filter((node): node is HTMLLinkElement => node instanceof HTMLLinkElement && isIconLink(node));

  for (const link of links) {
    link.href = href;
    link.setAttribute(MANAGED_ATTR, "true");
  }

  const iconLink = ensureManagedLink(head, "icon");
  iconLink.href = href;

  const shortcutLink = ensureManagedLink(head, "shortcut icon");
  shortcutLink.href = href;
}

export function GlobalFavicon({ agencyLogoUrl, refreshKey = 0 }: { agencyLogoUrl?: string | null; refreshKey?: number }) {
  const [faviconHref, setFaviconHref] = useState(DEFAULT_FAVICON_HREF);
  const resolvedLogoHref = useMemo(() => resolveAgencyFaviconHref(agencyLogoUrl, refreshKey), [agencyLogoUrl, refreshKey]);

  useEffect(() => {
    let ignore = false;
    if (resolvedLogoHref === DEFAULT_FAVICON_HREF) {
      setFaviconHref(DEFAULT_FAVICON_HREF);
      return;
    }

    const preview = new Image();
    preview.onload = () => {
      if (!ignore) setFaviconHref(resolvedLogoHref);
    };
    preview.onerror = () => {
      if (!ignore) setFaviconHref(DEFAULT_FAVICON_HREF);
    };
    preview.src = resolvedLogoHref;

    return () => {
      ignore = true;
    };
  }, [resolvedLogoHref]);

  useEffect(() => {
    applyGlobalFavicon(faviconHref);
  }, [faviconHref]);

  return null;
}
