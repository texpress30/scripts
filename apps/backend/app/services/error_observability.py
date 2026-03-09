from __future__ import annotations

import json
import re
from typing import Any

_SENSITIVE_KEY_RE = re.compile(r"(token|secret|password|authorization|api[_-]?key|refresh[_-]?token)", re.IGNORECASE)
_BEARER_RE = re.compile(r"(?i)bearer\s+[a-z0-9\-._~+/]+=*")
_URL_CRED_RE = re.compile(r"(https?://)([^\s/@:]+):([^\s/@]+)@")
_LONG_TOKEN_RE = re.compile(r"(?i)\b[a-z0-9_\-]{24,}\b")


def _mask_secret(value: str) -> str:
    masked = _BEARER_RE.sub("Bearer ***", value)
    masked = _URL_CRED_RE.sub(r"\1***:***@", masked)
    return _LONG_TOKEN_RE.sub("***", masked)


def sanitize_text(value: object, *, max_len: int = 300) -> str:
    raw = "" if value is None else str(value)
    sanitized = _mask_secret(raw).replace("\n", " ").replace("\r", " ").strip()
    if len(sanitized) > max_len:
        return f"{sanitized[:max_len]}..."
    return sanitized


def sanitize_payload(value: Any, *, max_depth: int = 4) -> Any:
    if max_depth <= 0:
        return "..."
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for key, item in value.items():
            key_s = str(key)
            if _SENSITIVE_KEY_RE.search(key_s):
                out[key_s] = "***"
            else:
                out[key_s] = sanitize_payload(item, max_depth=max_depth - 1)
        return out
    if isinstance(value, list):
        return [sanitize_payload(item, max_depth=max_depth - 1) for item in value[:20]]
    if isinstance(value, str):
        return sanitize_text(value, max_len=200)
    return value


def safe_body_snippet(raw_body: str, *, max_len: int = 400) -> str:
    body = raw_body.strip()
    if body == "":
        return ""
    try:
        parsed = json.loads(body)
        body = json.dumps(sanitize_payload(parsed), ensure_ascii=False)
    except Exception:  # noqa: BLE001
        body = sanitize_text(body, max_len=max_len)
    if len(body) > max_len:
        return f"{body[:max_len]}..."
    return body
