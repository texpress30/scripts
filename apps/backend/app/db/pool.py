"""Centralized psycopg connection pool.

Provides a shared ``ConnectionPool`` so that services re-use connections
instead of opening a new TCP+TLS handshake per query.

Usage in services::

    from app.db.pool import get_connection

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
"""

from __future__ import annotations

import logging
import os
from contextlib import contextmanager
from typing import TYPE_CHECKING, Generator

if TYPE_CHECKING:
    import psycopg

logger = logging.getLogger(__name__)

try:
    from psycopg_pool import ConnectionPool as _ConnectionPool
except ImportError:
    _ConnectionPool = None  # type: ignore[assignment,misc]

try:
    import psycopg as _psycopg
except ImportError:
    _psycopg = None  # type: ignore[assignment]

_pool: _ConnectionPool | None = None  # type: ignore[valid-type]

_MIN_SIZE = int(os.environ.get("DB_POOL_MIN_SIZE", "2"))
_MAX_SIZE = int(os.environ.get("DB_POOL_MAX_SIZE", "10"))
_POOL_TIMEOUT = float(os.environ.get("DB_POOL_TIMEOUT", "30"))


def open_pool(conninfo: str) -> None:
    """Create and open the global connection pool.

    Called once during application startup (``main.py``).
    """
    global _pool

    if _ConnectionPool is None:
        logger.warning("psycopg_pool not installed — falling back to per-request connections")
        return

    if _pool is not None:
        logger.debug("Pool already open — skipping")
        return

    _pool = _ConnectionPool(
        conninfo=conninfo,
        min_size=_MIN_SIZE,
        max_size=_MAX_SIZE,
        timeout=_POOL_TIMEOUT,
        open=True,
    )
    logger.info(
        "Connection pool opened (min=%d, max=%d, timeout=%.0fs)",
        _MIN_SIZE,
        _MAX_SIZE,
        _POOL_TIMEOUT,
    )


def close_pool() -> None:
    """Close the global pool, releasing all connections.

    Called during application shutdown.
    """
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None
        logger.info("Connection pool closed")


@contextmanager
def get_connection() -> Generator[psycopg.Connection, None, None]:
    """Yield a connection from the pool (or a one-shot connection as fallback).

    Commits on clean exit, rolls back on exception, then returns the
    connection to the pool (or closes it in fallback mode).
    """
    if _pool is not None:
        with _pool.connection() as conn:
            yield conn
        return

    if _psycopg is None:
        raise RuntimeError("psycopg is required for database access")

    from app.core.config import load_settings

    with _psycopg.connect(load_settings().database_url) as conn:
        yield conn
