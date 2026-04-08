"""Custom exceptions raised by the BigCommerce REST API client.

Every exception is a subclass of :class:`BigCommerceAPIError` so callers can
use a single ``except BigCommerceAPIError`` guard when they don't need to
discriminate. Specific subclasses exist for the HTTP status codes the app
reacts to (auth, not-found, rate limit, server, connectivity).
"""

from __future__ import annotations


class BigCommerceAPIError(Exception):
    """Base exception for every BigCommerce REST API failure.

    ``status_code`` is the HTTP status returned by BigCommerce (or ``None``
    for transport-level errors). ``body`` is the raw response body
    (truncated) for debugging — never log it at INFO level since the
    payload may include partial customer data on edge endpoints.
    """

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        body: str | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = int(status_code) if status_code is not None else None
        self.body = body

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return (
            f"{type(self).__name__}(status_code={self.status_code!r}, "
            f"message={self.message!r})"
        )


class BigCommerceAuthError(BigCommerceAPIError):
    """Raised on HTTP 401 / 403 — access token invalid, revoked, or the
    granted OAuth scope list does not include the requested resource."""


class BigCommerceNotFoundError(BigCommerceAPIError):
    """Raised on HTTP 404 — endpoint or resource does not exist."""


class BigCommerceRateLimitError(BigCommerceAPIError):
    """Raised on HTTP 429 — too many requests inside the 30s window.

    The BigCommerce client transparently retries once after sleeping for
    the duration advertised in ``X-Rate-Limit-Time-Reset-Ms``; this
    exception is only raised when even the retry attempt is throttled.
    """


class BigCommerceServerError(BigCommerceAPIError):
    """Raised on HTTP 5xx — BigCommerce backend is degraded.

    Callers may retry with exponential backoff; the underlying request
    is idempotent for GET / DELETE.
    """


class BigCommerceConnectionError(BigCommerceAPIError):
    """Raised on transport-level failure (DNS, TCP, TLS handshake, read
    timeout) — BigCommerce itself never responded."""
