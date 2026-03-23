"use client";

import { useEffect, useMemo, useState } from "react";

export const DEFAULT_FAVICON_HREF = "/icon.svg";
const FAVICON_LINK_ID = "global-agency-favicon";

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
    const head = document.head;
    let link = document.getElementById(FAVICON_LINK_ID) as HTMLLinkElement | null;
    if (!link) {
      link = document.createElement("link");
      link.id = FAVICON_LINK_ID;
      link.rel = "icon";
      head.appendChild(link);
    }
    link.href = faviconHref;
  }, [faviconHref]);

  return null;
}
