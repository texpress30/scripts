"""OAuth 1.0a (HMAC-SHA1) request signing for the Magento 2 REST API.

Magento 2's REST API accepts OAuth 1.0a "three-legged" tokens minted by
the merchant in ``System → Extensions → Integrations``. Each request
must carry an ``Authorization: OAuth …`` header whose signature is
computed per RFC 5849 §3.4.1 (HMAC-SHA1).

This module is intentionally dependency-free (stdlib only: ``hmac``,
``hashlib``, ``base64``, ``urllib.parse``). It exposes two public
helpers:

* :func:`generate_oauth_signature` — pure function that computes the
  base64 HMAC-SHA1 signature from the ``(method, url, params, secrets)``
  tuple. Useful for unit testing with deterministic nonce / timestamp.
* :func:`build_authorization_header` — end-to-end helper that mints a
  fresh nonce + timestamp (or accepts explicit ones for tests), runs
  the signature, and returns the ready-to-send header string.

RFC 3986 percent-encoding is done via ``urllib.parse.quote(s, safe="")``
which preserves ``A-Z a-z 0-9 - . _ ~`` and encodes everything else.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import time
import uuid
from urllib.parse import parse_qsl, quote, urlparse, urlunparse


OAUTH_SIGNATURE_METHOD = "HMAC-SHA1"
OAUTH_VERSION = "1.0"


def percent_encode(value: str) -> str:
    """RFC 3986 percent-encode a string.

    Unreserved characters (``A-Z``, ``a-z``, ``0-9``, ``-``, ``.``, ``_``,
    ``~``) pass through unchanged; everything else is ``%HH``-encoded.
    """
    return quote(str(value), safe="")


def generate_nonce() -> str:
    """Return a fresh per-request nonce (UUID4 hex, 32 lowercase chars)."""
    return uuid.uuid4().hex


def generate_timestamp() -> str:
    """Return the current Unix timestamp as a string."""
    return str(int(time.time()))


def _normalize_url(raw_url: str) -> tuple[str, dict[str, list[str]]]:
    """Split ``raw_url`` into its signature-base-string form + query params.

    Per RFC 5849 §3.4.1.2 the URL used in the base string must be the
    scheme + authority + path only — any query string is pulled out and
    merged into the parameters collection.
    """
    parsed = urlparse(raw_url)
    scheme = parsed.scheme.lower()
    netloc = parsed.netloc.lower()
    # Strip default ports (80/443) — RFC 5849 §3.4.1.2 requires they be omitted
    if ":" in netloc:
        host, _, port = netloc.partition(":")
        if (scheme == "http" and port == "80") or (scheme == "https" and port == "443"):
            netloc = host
    path = parsed.path or "/"
    base_url = urlunparse((scheme, netloc, path, "", "", ""))

    query_params: dict[str, list[str]] = {}
    if parsed.query:
        for key, value in parse_qsl(parsed.query, keep_blank_values=True):
            query_params.setdefault(key, []).append(value)
    return base_url, query_params


def generate_oauth_signature(
    *,
    http_method: str,
    url: str,
    params: dict[str, str] | None,
    consumer_secret: str,
    token_secret: str,
) -> str:
    """Return the base64-encoded HMAC-SHA1 signature for an OAuth 1.0a request.

    ``params`` must include every OAuth protocol parameter (``oauth_*``)
    except ``oauth_signature`` itself, merged with any ``x-www-form-urlencoded``
    body parameters and the URL query string. Callers that use JSON bodies
    should pass only the query parameters (Magento REST uses JSON bodies,
    which are excluded from the signature per RFC 5849 §3.4.1.3.1).
    """
    method = (http_method or "GET").upper()
    base_url, query_params = _normalize_url(url)

    # Merge any query string extracted from the URL into the caller's params.
    merged: list[tuple[str, str]] = []
    if params:
        for key, value in params.items():
            merged.append((str(key), "" if value is None else str(value)))
    for key, values in query_params.items():
        for value in values:
            merged.append((str(key), str(value)))

    # RFC 5849 §3.4.1.3.2: percent-encode each key/value, sort lexicographically
    # first by key, then by value. Sorting is done on the ENCODED strings.
    encoded = sorted((percent_encode(k), percent_encode(v)) for k, v in merged)
    params_string = "&".join(f"{k}={v}" for k, v in encoded)

    base_string = (
        f"{method}&{percent_encode(base_url)}&{percent_encode(params_string)}"
    )
    signing_key = f"{percent_encode(consumer_secret)}&{percent_encode(token_secret)}"

    digest = hmac.new(
        signing_key.encode("utf-8"),
        base_string.encode("utf-8"),
        hashlib.sha1,
    ).digest()
    return base64.b64encode(digest).decode("ascii")


def build_authorization_header(
    *,
    consumer_key: str,
    consumer_secret: str,
    access_token: str,
    access_token_secret: str,
    http_method: str,
    url: str,
    query_params: dict[str, str] | None = None,
    nonce: str | None = None,
    timestamp: str | None = None,
) -> str:
    """Build a ready-to-send ``Authorization: OAuth …`` header string.

    Pass explicit ``nonce`` / ``timestamp`` only in tests — production
    callers should let the helper generate fresh values on every call.
    """
    if not consumer_key or not access_token:
        raise ValueError("consumer_key and access_token are required")

    oauth_params: dict[str, str] = {
        "oauth_consumer_key": consumer_key,
        "oauth_token": access_token,
        "oauth_signature_method": OAUTH_SIGNATURE_METHOD,
        "oauth_timestamp": timestamp or generate_timestamp(),
        "oauth_nonce": nonce or generate_nonce(),
        "oauth_version": OAUTH_VERSION,
    }

    # Parameters used for signing = oauth_* + query params (JSON body excluded).
    all_params: dict[str, str] = dict(oauth_params)
    if query_params:
        for key, value in query_params.items():
            # If a caller passes a list of values we collapse to repr; Magento
            # query params are always scalar in practice.
            all_params[str(key)] = "" if value is None else str(value)

    signature = generate_oauth_signature(
        http_method=http_method,
        url=url,
        params=all_params,
        consumer_secret=consumer_secret,
        token_secret=access_token_secret,
    )
    oauth_params["oauth_signature"] = signature

    # Header format: `OAuth k1="v1", k2="v2", ...` with every key and value
    # percent-encoded and wrapped in double quotes. Sort for deterministic
    # output (easier to test).
    parts = [
        f'{percent_encode(k)}="{percent_encode(v)}"'
        for k, v in sorted(oauth_params.items())
    ]
    return "OAuth " + ", ".join(parts)
