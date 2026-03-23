import React from "react";
import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { render, waitFor } from "@testing-library/react";

import { applyGlobalFavicon, DEFAULT_FAVICON_HREF, GlobalFavicon, resolveAgencyFaviconHref } from "./GlobalFavicon";

class SuccessfulImageMock {
  onload: (() => void) | null = null;
  onerror: (() => void) | null = null;

  set src(_value: string) {
    queueMicrotask(() => this.onload?.());
  }
}

class FailingImageMock {
  onload: (() => void) | null = null;
  onerror: (() => void) | null = null;

  set src(_value: string) {
    queueMicrotask(() => this.onerror?.());
  }
}

describe("GlobalFavicon", () => {
  const originalImage = global.Image;

  beforeEach(() => {
    document.head.querySelectorAll("link[data-global-favicon-managed=\"true\"]").forEach((node) => node.remove());
    vi.stubGlobal("Image", SuccessfulImageMock);
  });

  afterEach(() => {
    vi.stubGlobal("Image", originalImage);
    document.head.querySelectorAll("link[data-global-favicon-managed=\"true\"]").forEach((node) => node.remove());
  });

  function iconLinks() {
    return Array.from(document.head.querySelectorAll("link")).filter((node) => {
      const rel = (node.getAttribute("rel") || "").toLowerCase();
      return rel.split(/\s+/).includes("icon") || rel === "shortcut icon";
    }) as HTMLLinkElement[];
  }

  it("keeps default favicon when agency logo is missing", async () => {
    render(<GlobalFavicon agencyLogoUrl="" refreshKey={1} />);

    await waitFor(() => {
      const hrefs = iconLinks().map((link) => link.href);
      expect(hrefs.every((href) => href.includes(DEFAULT_FAVICON_HREF))).toBe(true);
    });
  });

  it("sets global favicon from agency logo url on effective icon links", async () => {
    render(<GlobalFavicon agencyLogoUrl="https://cdn.example/logo.png" refreshKey={3} />);

    await waitFor(() => {
      const hrefs = iconLinks().map((link) => link.href);
      expect(hrefs.length).toBeGreaterThanOrEqual(2);
      expect(hrefs.every((href) => href === "https://cdn.example/logo.png?v=3")).toBe(true);
    });
  });

  it("updates favicon when agency logo changes", async () => {
    const { rerender } = render(<GlobalFavicon agencyLogoUrl="https://cdn.example/old.png" refreshKey={1} />);

    await waitFor(() => {
      const hrefs = iconLinks().map((link) => link.href);
      expect(hrefs.every((href) => href === "https://cdn.example/old.png?v=1")).toBe(true);
    });

    rerender(<GlobalFavicon agencyLogoUrl="https://cdn.example/new.png" refreshKey={2} />);
    await waitFor(() => {
      const hrefs = iconLinks().map((link) => link.href);
      expect(hrefs.every((href) => href === "https://cdn.example/new.png?v=2")).toBe(true);
    });
  });

  it("reverts to default favicon when agency logo is removed", async () => {
    const { rerender } = render(<GlobalFavicon agencyLogoUrl="https://cdn.example/logo.png" refreshKey={1} />);
    rerender(<GlobalFavicon agencyLogoUrl="" refreshKey={2} />);

    await waitFor(() => {
      const hrefs = iconLinks().map((link) => link.href);
      expect(hrefs.every((href) => href.includes(DEFAULT_FAVICON_HREF))).toBe(true);
    });
  });

  it("keeps agency favicon while rerendering across pages", async () => {
    const { rerender } = render(
      <div data-testid="page-agency-dashboard">
        <GlobalFavicon agencyLogoUrl="https://cdn.example/logo.png" refreshKey={5} />
      </div>,
    );

    rerender(
      <div data-testid="page-subaccount-dashboard">
        <GlobalFavicon agencyLogoUrl="https://cdn.example/logo.png" refreshKey={5} />
      </div>,
    );

    await waitFor(() => {
      const hrefs = iconLinks().map((link) => link.href);
      expect(hrefs.every((href) => href === "https://cdn.example/logo.png?v=5")).toBe(true);
    });
  });

  it("refresh key updates favicon version for company-settings-updated flow", async () => {
    const { rerender } = render(<GlobalFavicon agencyLogoUrl="https://cdn.example/logo.png" refreshKey={10} />);

    rerender(<GlobalFavicon agencyLogoUrl="https://cdn.example/logo.png" refreshKey={11} />);
    await waitFor(() => {
      const hrefs = iconLinks().map((link) => link.href);
      expect(hrefs.every((href) => href === "https://cdn.example/logo.png?v=11")).toBe(true);
    });
  });

  it("falls back to default favicon when agency logo url fails to load", async () => {
    vi.stubGlobal("Image", FailingImageMock);
    render(<GlobalFavicon agencyLogoUrl="https://cdn.example/bad.png" refreshKey={1} />);

    await waitFor(() => {
      const hrefs = iconLinks().map((link) => link.href);
      expect(hrefs.every((href) => href.includes(DEFAULT_FAVICON_HREF))).toBe(true);
    });
  });
});

describe("resolveAgencyFaviconHref", () => {
  it("supports legacy/logo_media based logo_url and default fallback", () => {
    expect(resolveAgencyFaviconHref("https://cdn.example/logo.png", 7)).toBe("https://cdn.example/logo.png?v=7");
    expect(resolveAgencyFaviconHref("   ", 7)).toBe(DEFAULT_FAVICON_HREF);
  });
});

describe("applyGlobalFavicon", () => {
  it("updates existing rel=icon and rel=shortcut icon links instead of leaving stale values", () => {
    const icon = document.createElement("link");
    icon.rel = "icon";
    icon.href = "/old-icon.ico";
    const shortcutIcon = document.createElement("link");
    shortcutIcon.rel = "shortcut icon";
    shortcutIcon.href = "/old-shortcut.ico";
    document.head.appendChild(icon);
    document.head.appendChild(shortcutIcon);

    applyGlobalFavicon("https://cdn.example/new-favicon.png?v=4");

    expect(icon.href).toBe("https://cdn.example/new-favicon.png?v=4");
    expect(shortcutIcon.href).toBe("https://cdn.example/new-favicon.png?v=4");
    expect(icon.getAttribute("data-global-favicon-managed")).toBe("true");
    expect(shortcutIcon.getAttribute("data-global-favicon-managed")).toBe("true");
  });
});
