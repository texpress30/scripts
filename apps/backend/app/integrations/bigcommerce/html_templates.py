"""HTML templates for BigCommerce iFrame callbacks.

BigCommerce renders the auth / load / uninstall callback URLs inside an
iFrame in the merchant's control panel. Returning raw JSON — which is the
default for FastAPI routes that declare a Pydantic ``response_model`` —
leaves the merchant staring at a wall of ``{"success": true, ...}`` text.

These helpers build small, self-contained HTML pages with inline CSS so
the output renders cleanly inside the BC iFrame without needing the
Omarosa frontend stylesheets or any external network requests:

* :func:`render_install_success` — celebration page shown right after a
  successful token exchange.
* :func:`render_install_error` — friendly error page when the install
  flow fails (bad code, missing scope, server error).
* :func:`render_load_page` — mini-dashboard the merchant sees every time
  they click the Voxel app from the BigCommerce Apps sidebar.
* :func:`wants_json` — tiny ``Accept`` header sniffer so existing API
  clients (tests, cron, curl ``-H "Accept: application/json"``) still
  get the old JSON shape.

All templates:

* use system fonts (no webfont network calls)
* scope every selector to an ``.bc-page`` wrapper so they can't be
  bled onto by BC's own CSS
* link external destinations with ``target="_blank" rel="noopener"``
  because we're rendered inside an iFrame — navigating ``_top`` would
  yank the merchant out of the BC control panel and is strictly worse UX
* HTML-escape every caller-supplied string (store_hash, user_email,
  error message) to prevent XSS inside the iFrame
"""

from __future__ import annotations

from html import escape
from typing import Iterable


# The Omarosa admin base URL that the "Open Omarosa Agency" link
# surfaces to the merchant. Kept as a module-level constant so tests can
# monkey-patch it if needed. In practice every live deployment hits
# ``https://admin.omarosa.ro``.
OMAROSA_ADMIN_URL = "https://admin.omarosa.ro"


_BASE_CSS = """
* { box-sizing: border-box; }
body {
  margin: 0;
  padding: 24px 16px;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto,
    "Helvetica Neue", Arial, sans-serif;
  font-size: 15px;
  line-height: 1.55;
  color: #1e293b;
  background: #f8fafc;
  -webkit-font-smoothing: antialiased;
}
.bc-page {
  max-width: 560px;
  margin: 0 auto;
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  padding: 32px 28px;
  box-shadow: 0 1px 3px rgba(15, 23, 42, 0.05),
              0 1px 2px rgba(15, 23, 42, 0.03);
}
.bc-page h1 {
  margin: 16px 0 8px 0;
  font-size: 22px;
  font-weight: 600;
  color: #0f172a;
}
.bc-page p {
  margin: 0 0 12px 0;
  color: #475569;
}
.bc-page p:last-of-type { margin-bottom: 0; }
.bc-page strong { color: #0f172a; }
.bc-page .bc-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 600;
}
.bc-page .bc-badge-success {
  background: #d1fae5;
  color: #065f46;
}
.bc-page .bc-badge-error {
  background: #fee2e2;
  color: #991b1b;
}
.bc-page .bc-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 48px;
  height: 48px;
  border-radius: 50%;
}
.bc-page .bc-icon-success {
  background: #d1fae5;
  color: #065f46;
}
.bc-page .bc-icon-error {
  background: #fee2e2;
  color: #991b1b;
}
.bc-page .bc-icon svg { width: 28px; height: 28px; }
.bc-page .bc-cta {
  display: inline-block;
  margin-top: 20px;
  padding: 10px 18px;
  background: #4f46e5;
  color: #ffffff;
  text-decoration: none;
  border-radius: 8px;
  font-weight: 600;
  font-size: 14px;
}
.bc-page .bc-cta:hover { background: #4338ca; }
.bc-page .bc-cta-secondary {
  background: #ffffff;
  color: #4f46e5;
  border: 1px solid #c7d2fe;
}
.bc-page .bc-cta-secondary:hover { background: #eef2ff; }
.bc-page .bc-meta {
  margin-top: 24px;
  padding-top: 20px;
  border-top: 1px solid #e2e8f0;
  font-size: 13px;
  color: #64748b;
}
.bc-page .bc-meta dl { margin: 0; display: grid; grid-template-columns: auto 1fr; gap: 6px 12px; }
.bc-page .bc-meta dt { color: #94a3b8; font-weight: 500; }
.bc-page .bc-meta dd { margin: 0; color: #334155; font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 12px; word-break: break-all; }
.bc-page .bc-footer {
  margin-top: 20px;
  font-size: 12px;
  color: #94a3b8;
  text-align: center;
}
"""


_SUCCESS_ICON = (
    '<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" '
    'stroke-width="2.5" stroke="currentColor">'
    '<path stroke-linecap="round" stroke-linejoin="round" d="M4.5 12.75l6 6 9-13.5" />'
    "</svg>"
)

_ERROR_ICON = (
    '<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" '
    'stroke-width="2.5" stroke="currentColor">'
    '<path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />'
    "</svg>"
)


def _page(
    *,
    title: str,
    body: str,
) -> str:
    """Wrap ``body`` in a minimal HTML5 document with the shared stylesheet."""
    return f"""<!DOCTYPE html>
<html lang="ro">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>{escape(title)}</title>
<style>{_BASE_CSS}</style>
</head>
<body>
<div class="bc-page">
{body}
</div>
</body>
</html>
"""


def render_install_success(
    *,
    store_hash: str,
    scope: str | None = None,
) -> str:
    """Return the HTML shown after a successful ``auth/callback``."""
    safe_hash = escape(store_hash or "")
    scope_html = ""
    if scope:
        scope_html = (
            '<div class="bc-meta"><dl>'
            '<dt>Store hash</dt>'
            f'<dd>{safe_hash}</dd>'
            '<dt>Scope acordat</dt>'
            f'<dd>{escape(scope)}</dd>'
            '</dl></div>'
        )
    else:
        scope_html = (
            '<div class="bc-meta"><dl>'
            '<dt>Store hash</dt>'
            f'<dd>{safe_hash}</dd>'
            '</dl></div>'
        )

    body = f"""
<div class="bc-icon bc-icon-success">{_SUCCESS_ICON}</div>
<h1>Instalare reușită!</h1>
<p>
  Aplicația <strong>Voxel</strong> s-a conectat cu succes la magazinul tău
  BigCommerce. Credențialele OAuth au fost salvate în siguranță și sunt gata
  de folosire.
</p>
<p>
  <strong>Următorul pas:</strong> contactează agenția <strong>Omarosa</strong>
  pentru a finaliza configurarea feed-urilor și a porni sincronizarea
  produselor.
</p>
<a class="bc-cta" href="{escape(OMAROSA_ADMIN_URL)}" target="_blank" rel="noopener">
  Deschide Omarosa Agency →
</a>
{scope_html}
<p class="bc-footer">Poți închide această fereastră în siguranță.</p>
"""
    return _page(title="Voxel · Instalare reușită", body=body)


def render_install_error(
    *,
    error_message: str,
    store_hash: str | None = None,
) -> str:
    """Return the HTML shown when ``auth/callback`` fails mid-flow."""
    safe_message = escape(error_message or "Eroare necunoscută la instalare.")
    meta_html = ""
    if store_hash:
        meta_html = (
            '<div class="bc-meta"><dl>'
            '<dt>Store hash</dt>'
            f'<dd>{escape(store_hash)}</dd>'
            '</dl></div>'
        )

    body = f"""
<div class="bc-icon bc-icon-error">{_ERROR_ICON}</div>
<h1>Instalare eșuată</h1>
<p>
  Nu am putut finaliza conectarea aplicației <strong>Voxel</strong> la
  magazinul tău BigCommerce. Încearcă să reinstalezi aplicația din
  BigCommerce App Marketplace — dacă problema persistă, contactează
  suportul Omarosa Agency.
</p>
<p><strong>Detaliu tehnic:</strong></p>
<p><code style="display:block;padding:12px;background:#f1f5f9;border-radius:6px;font-size:13px;color:#991b1b;">{safe_message}</code></p>
<a class="bc-cta bc-cta-secondary" href="{escape(OMAROSA_ADMIN_URL)}" target="_blank" rel="noopener">
  Deschide Omarosa Agency
</a>
{meta_html}
"""
    return _page(title="Voxel · Instalare eșuată", body=body)


def render_load_page(
    *,
    store_hash: str,
    user_email: str | None = None,
    owner_email: str | None = None,
    connected: bool = True,
) -> str:
    """Return the mini-dashboard shown every time the merchant opens Voxel.

    Rendered in the BigCommerce Apps iFrame. Gives the merchant a quick
    status read + a launch link to the Omarosa admin where the real
    feed-management UI lives.
    """
    safe_hash = escape(store_hash or "")
    status_badge = (
        '<span class="bc-badge bc-badge-success">✓ Activ</span>'
        if connected
        else '<span class="bc-badge bc-badge-error">✗ Inactiv</span>'
    )

    user_rows: list[str] = []
    if user_email:
        user_rows.append(f"<dt>Utilizator curent</dt><dd>{escape(user_email)}</dd>")
    if owner_email and owner_email != user_email:
        user_rows.append(f"<dt>Owner magazin</dt><dd>{escape(owner_email)}</dd>")
    user_rows.append(f"<dt>Store hash</dt><dd>{safe_hash}</dd>")
    meta_html = (
        '<div class="bc-meta"><dl>'
        + "".join(user_rows)
        + '</dl></div>'
    )

    body = f"""
<div class="bc-icon bc-icon-success">{_SUCCESS_ICON}</div>
<h1>Voxel Feed Management</h1>
<p>Status conexiune: {status_badge}</p>
<p>
  Magazinul tău BigCommerce este conectat la platforma
  <strong>Omarosa Agency</strong>. De aici îți poți gestiona feed-urile
  de produse, le poți sincroniza cu canalele de marketing (Google, Meta,
  TikTok, Pinterest) și poți urmări performanța.
</p>
<p>
  Toate funcționalitățile avansate sunt disponibile în panoul Omarosa
  Agency. Dă click pe butonul de mai jos pentru a continua.
</p>
<a class="bc-cta" href="{escape(OMAROSA_ADMIN_URL)}" target="_blank" rel="noopener">
  Deschide Omarosa Agency →
</a>
{meta_html}
<p class="bc-footer">
  Ai nevoie de ajutor? Contactează echipa <strong>Omarosa</strong>.
</p>
"""
    return _page(title="Voxel · BigCommerce", body=body)


def wants_json(accept_header: str | None) -> bool:
    """Return True when the caller explicitly asked for JSON.

    BigCommerce itself sends browser-style ``Accept`` headers (which
    include ``text/html``), so the default is always HTML. API clients
    (tests, curl, cron) can opt into the old JSON shape by sending
    ``Accept: application/json``. We deliberately do NOT honour the
    relative quality values (``q=``) — a strict substring check keeps
    the logic obvious and the behaviour predictable.
    """
    if not accept_header:
        return False
    normalized = accept_header.lower()
    # If the client lists text/html anywhere it's a browser — hand it HTML.
    if "text/html" in normalized:
        return False
    return "application/json" in normalized


def _iter_accept_candidates(accept: str | None) -> Iterable[str]:  # pragma: no cover - tiny helper
    if not accept:
        return []
    return [item.strip() for item in accept.split(",") if item.strip()]
