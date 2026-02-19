from __future__ import annotations


def sanitize_ai_output(text: str) -> str:
    cleaned = " ".join(text.strip().split())
    if not cleaned:
        return "Nu am destule date"

    blocked_markers = ["as an ai", "cannot provide", "i am unable"]
    lowered = cleaned.lower()
    for marker in blocked_markers:
        if marker in lowered:
            return "Nu am destule date"

    if len(cleaned) > 1200:
        cleaned = cleaned[:1200].rstrip() + "..."

    return cleaned


def has_sufficient_data(spend: float, conversions: int) -> bool:
    return spend > 0 and conversions > 0
