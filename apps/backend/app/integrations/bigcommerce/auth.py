"""BigCommerce OAuth 2.0 helpers: signed-payload-JWT verification + token exchange.

Two responsibilities live here:

1. :func:`verify_signed_payload_jwt` — BigCommerce's ``load``, ``uninstall``
   and ``remove_user`` callbacks arrive with a ``signed_payload_jwt`` query
   parameter. The JWT is a standard HS256 token whose secret IS the app's
   ``client_secret``. We verify the signature, ``exp``/``nbf`` validity,
   ``aud`` == client_id, ``iss`` == "bc", and return the decoded payload.
   Implementation is intentionally stdlib-only (``hmac``, ``hashlib``,
   ``base64``, ``json``) — PyJWT is NOT installed in this project, and we
   already verify HMAC signatures by hand for Shopify webhooks.

2. :func:`exchange_code_for_token` — turns the short-lived ``code`` delivered
   to the ``auth_callback`` into a permanent per-store ``access_token`` by
   POSTing to ``https://login.bigcommerce.com/oauth2/token``. We use stdlib
   ``urllib.request`` to mirror the Shopify OAuth service and avoid pulling
   ``httpx`` into a hot install-path.

Every raised exception is a :class:`BigCommerceAuthError` so callers can
distinguish auth failures from unrelated bugs.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import time
from typing import Any
from urllib import error, parse, request

from app.integrations.bigcommerce import config as bc_config
from app.integrations.bigcommerce.exceptions import (
    BigCommerceAuthError as _BCAuthErrorBase,
)


logger = logging.getLogger(__name__)


class BigCommerceAuthError(_BCAuthErrorBase):
    """Raised for any BigCommerce OAuth / JWT verification failure.

    Subclasses :class:`app.integrations.bigcommerce.exceptions.BigCommerceAuthError`
    so that ``except`` clauses catching the canonical exception type also
    catch OAuth-flow failures. The OAuth flow needs a few extra fields
    (``http_status``, ``provider_error``, ``retryable``) that don't make
    sense on the generic API client, so they live as instance attrs here.
    """

    def __init__(
        self,
        message: str,
        *,
        http_status: int | None = None,
        provider_error: str | None = None,
        retryable: bool | None = None,
    ) -> None:
        super().__init__(message, status_code=http_status)
        self.http_status = int(http_status) if http_status is not None else None
        self.provider_error = provider_error
        self.retryable = retryable


# ---------------------------------------------------------------------------
# JWT verification (stdlib HS256)
# ---------------------------------------------------------------------------


def _b64url_decode(segment: str) -> bytes:
    """Decode a single base64url segment, tolerating missing padding."""
    padding = "=" * (-len(segment) % 4)
    try:
        return base64.urlsafe_b64decode(segment + padding)
    except (ValueError, base64.binascii.Error) as exc:
        raise BigCommerceAuthError("Invalid base64url segment in JWT") from exc


def verify_signed_payload_jwt(
    signed_payload_jwt: str,
    client_secret: str,
    *,
    client_id: str | None = None,
    leeway_seconds: int = 60,
    now: int | None = None,
) -> dict[str, Any]:
    """Verify a BigCommerce ``signed_payload_jwt`` (HS256) and return the claims.

    Checks performed:

    * Token is three dot-separated base64url segments.
    * Header ``alg`` is ``HS256`` and ``typ`` is ``JWT``.
    * Signature matches ``HMAC-SHA256(client_secret, header + "." + payload)``
      (timing-safe comparison).
    * ``iss`` == ``"bc"``.
    * ``aud`` matches the configured client id (defaults to
      ``bc_config.BC_CLIENT_ID``).
    * ``exp`` has not passed (``leeway_seconds`` window tolerated).
    * ``nbf`` has been reached (``leeway_seconds`` window tolerated).

    Raises :class:`BigCommerceAuthError` on any failure.
    """
    if not signed_payload_jwt or not isinstance(signed_payload_jwt, str):
        raise BigCommerceAuthError("signed_payload_jwt is required")
    if not client_secret:
        raise BigCommerceAuthError("client_secret is required to verify the JWT")

    parts = signed_payload_jwt.split(".")
    if len(parts) != 3:
        raise BigCommerceAuthError(
            f"Invalid JWT format: expected 3 segments, got {len(parts)}"
        )
    header_b64, payload_b64, signature_b64 = parts

    # Signature verification (timing-safe).
    signing_input = f"{header_b64}.{payload_b64}".encode("ascii")
    expected_sig = hmac.new(
        client_secret.encode("utf-8"),
        signing_input,
        hashlib.sha256,
    ).digest()
    received_sig = _b64url_decode(signature_b64)
    if not hmac.compare_digest(expected_sig, received_sig):
        raise BigCommerceAuthError("JWT signature mismatch")

    # Decode header + payload (only after signature checks out).
    try:
        header = json.loads(_b64url_decode(header_b64).decode("utf-8"))
        payload = json.loads(_b64url_decode(payload_b64).decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise BigCommerceAuthError("JWT header/payload is not valid JSON") from exc

    if not isinstance(header, dict) or not isinstance(payload, dict):
        raise BigCommerceAuthError("JWT header/payload must be JSON objects")

    if header.get("alg") != "HS256":
        raise BigCommerceAuthError(
            f"Unsupported JWT alg: {header.get('alg')!r} (expected HS256)"
        )
    if header.get("typ") not in (None, "JWT"):
        raise BigCommerceAuthError(
            f"Unsupported JWT typ: {header.get('typ')!r} (expected JWT)"
        )

    # Issuer check — BigCommerce always sets ``iss: "bc"``.
    if payload.get("iss") != "bc":
        raise BigCommerceAuthError(
            f"Unexpected JWT issuer: {payload.get('iss')!r} (expected 'bc')"
        )

    # Audience must match the configured client id.
    expected_aud = client_id if client_id is not None else bc_config.BC_CLIENT_ID
    if not expected_aud:
        raise BigCommerceAuthError("No client_id configured to verify JWT audience")
    if payload.get("aud") != expected_aud:
        raise BigCommerceAuthError(
            f"JWT audience mismatch: got={payload.get('aud')!r} expected={expected_aud!r}"
        )

    current_ts = int(now if now is not None else time.time())

    exp = payload.get("exp")
    if not isinstance(exp, (int, float)):
        raise BigCommerceAuthError("JWT missing or invalid 'exp' claim")
    if current_ts > int(exp) + int(leeway_seconds):
        raise BigCommerceAuthError(
            f"JWT is expired: exp={int(exp)} now={current_ts}"
        )

    nbf = payload.get("nbf")
    if nbf is not None:
        if not isinstance(nbf, (int, float)):
            raise BigCommerceAuthError("JWT has invalid 'nbf' claim")
        if current_ts + int(leeway_seconds) < int(nbf):
            raise BigCommerceAuthError(
                f"JWT is not yet valid: nbf={int(nbf)} now={current_ts}"
            )

    return payload


# ---------------------------------------------------------------------------
# Authorization code exchange
# ---------------------------------------------------------------------------


def extract_store_hash(context: str) -> str:
    """Parse ``"stores/abc123"`` into ``"abc123"``.

    Accepts the raw context value delivered by BigCommerce in OAuth callbacks
    and JWT ``sub`` claims. Raises ``ValueError`` on any unexpected shape.
    """
    if not context or not isinstance(context, str):
        raise ValueError(f"Invalid BigCommerce context: {context!r}")
    cleaned = context.strip()
    if not cleaned.startswith("stores/"):
        raise ValueError(
            f"Invalid BigCommerce context (expected 'stores/<hash>'): {context!r}"
        )
    raw_hash = cleaned[len("stores/"):]
    return bc_config.validate_store_hash(raw_hash)


def _http_post_form(url: str, body: dict[str, str]) -> dict[str, Any]:
    """POST a form-urlencoded body and return the decoded JSON response.

    Mirrors the Shopify service's ``_http_post_json`` but uses
    ``application/x-www-form-urlencoded`` because that's what the BigCommerce
    token endpoint accepts. Pure stdlib — no httpx dependency.
    """
    encoded = parse.urlencode(body).encode("utf-8")
    req = request.Request(
        url=url,
        data=encoded,
        method="POST",
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        },
    )
    try:
        with request.urlopen(req, timeout=20) as response:
            raw = response.read().decode("utf-8")
    except error.HTTPError as exc:
        body_text = ""
        try:
            body_text = exc.read().decode("utf-8", errors="replace")
        except Exception:  # noqa: BLE001
            body_text = ""

        provider_error: str | None = None
        try:
            parsed_err = json.loads(body_text) if body_text else {}
            if isinstance(parsed_err, dict):
                provider_error = (
                    parsed_err.get("error_description")
                    or parsed_err.get("error")
                    or parsed_err.get("title")
                    or None
                )
        except json.JSONDecodeError:
            provider_error = None

        if exc.code == 400:
            raise BigCommerceAuthError(
                "BigCommerce rejected the OAuth code (invalid or expired).",
                http_status=400,
                provider_error=str(provider_error) if provider_error else None,
                retryable=False,
            ) from exc
        if exc.code in (401, 403):
            raise BigCommerceAuthError(
                "BigCommerce rejected the OAuth credentials.",
                http_status=exc.code,
                provider_error=str(provider_error) if provider_error else None,
                retryable=False,
            ) from exc
        raise BigCommerceAuthError(
            f"BigCommerce OAuth exchange failed: status={exc.code}",
            http_status=exc.code,
            provider_error=str(provider_error) if provider_error else None,
            retryable=exc.code >= 500,
        ) from exc
    except (error.URLError, TimeoutError) as exc:
        raise BigCommerceAuthError(
            "Could not reach BigCommerce",
            http_status=502,
            retryable=True,
        ) from exc

    try:
        parsed = json.loads(raw) if raw else {}
    except json.JSONDecodeError as exc:
        raise BigCommerceAuthError("BigCommerce returned invalid JSON") from exc
    if not isinstance(parsed, dict):
        raise BigCommerceAuthError("BigCommerce response shape is invalid")
    return parsed


def exchange_code_for_token(
    *,
    code: str,
    scope: str,
    context: str,
    redirect_uri: str | None = None,
    client_id: str | None = None,
    client_secret: str | None = None,
) -> dict[str, Any]:
    """Exchange an authorization ``code`` for a permanent BigCommerce access token.

    Returns the raw BigCommerce response dict which contains at least::

        {
            "access_token": "…",
            "scope": "store_v2_products_read_only …",
            "user": {"id": 9876543, "email": "user@example.com"},
            "context": "stores/abc123",
            "account_uuid": "…",
        }
    """
    if not code:
        raise BigCommerceAuthError("code is required for token exchange")
    if not context:
        raise BigCommerceAuthError("context is required for token exchange")

    resolved_client_id = client_id or bc_config.BC_CLIENT_ID
    resolved_client_secret = client_secret or bc_config.BC_CLIENT_SECRET
    resolved_redirect_uri = redirect_uri or bc_config.BC_REDIRECT_URI

    if not (resolved_client_id and resolved_client_secret and resolved_redirect_uri):
        raise BigCommerceAuthError(
            "BigCommerce OAuth is not configured; cannot exchange authorization code"
        )

    payload = _http_post_form(
        bc_config.BC_TOKEN_URL,
        {
            "client_id": resolved_client_id,
            "client_secret": resolved_client_secret,
            "code": code,
            "scope": scope or "",
            "grant_type": "authorization_code",
            "redirect_uri": resolved_redirect_uri,
            "context": context,
        },
    )

    access_token = str(payload.get("access_token") or "").strip()
    if not access_token:
        raise BigCommerceAuthError(
            "BigCommerce OAuth callback did not return an access token"
        )

    logger.info(
        "bigcommerce_token_exchange_ok context=%s scope=%s token=%s",
        payload.get("context"),
        payload.get("scope"),
        f"{access_token[:6]}***" if access_token else "",
    )
    return payload
