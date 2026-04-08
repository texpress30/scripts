"""Custom exceptions raised by the Magento 2 REST API client.

Every exception is a subclass of :class:`MagentoAPIError` so callers can
use a single ``except MagentoAPIError`` guard when they don't need to
discriminate. Specific subclasses exist for the HTTP status codes that
the app reacts to (auth, not-found, rate limit, connectivity).
"""

from __future__ import annotations


class MagentoAPIError(Exception):
    """Base exception for every Magento 2 REST API failure.

    ``status_code`` is the HTTP status returned by Magento (or ``None``
    for transport-level errors). ``body`` is the raw response body
    (truncated) for debugging — **never** log it at INFO level since
    Magento may echo request headers containing OAuth parameters.
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
        return f"{type(self).__name__}(status_code={self.status_code!r}, message={self.message!r})"


class MagentoAuthError(MagentoAPIError):
    """Raised on HTTP 401 / 403 — OAuth 1.0a credentials invalid, revoked,
    or missing a required ACL resource in the Magento Integration."""


class MagentoNotFoundError(MagentoAPIError):
    """Raised on HTTP 404 — endpoint or resource does not exist."""


class MagentoRateLimitError(MagentoAPIError):
    """Raised on HTTP 429 — too many requests. Callers should back off
    and retry with exponential jitter."""


class MagentoConnectionError(MagentoAPIError):
    """Raised on transport-level failure (DNS, TCP, TLS handshake,
    read timeout) — Magento itself never responded."""
