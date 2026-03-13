from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class TikTokAccountDailyIdentityResolution:
    canonical_persistence_customer_id: str | None
    identity_source: str
    provider_ids_seen: tuple[str, ...]
    is_ambiguous: bool
    ambiguity_reason: str | None


def _normalize_identity(value: object) -> str:
    return str(value or "").strip()


def resolve_tiktok_account_daily_persistence_identity(
    *,
    attached_account_id: str,
    provider_ids_in_scope: Iterable[object] | None = None,
) -> TikTokAccountDailyIdentityResolution:
    attached_normalized = _normalize_identity(attached_account_id)

    normalized_provider_ids: list[str] = []
    if provider_ids_in_scope is not None:
        for raw in provider_ids_in_scope:
            normalized = _normalize_identity(raw)
            if normalized == "":
                continue
            normalized_provider_ids.append(normalized)

    unique_provider_ids = tuple(sorted(set(normalized_provider_ids)))
    unique_identities = set(unique_provider_ids)
    if attached_normalized != "":
        unique_identities.add(attached_normalized)

    if len(unique_identities) <= 0:
        return TikTokAccountDailyIdentityResolution(
            canonical_persistence_customer_id=None,
            identity_source="unresolved",
            provider_ids_seen=unique_provider_ids,
            is_ambiguous=True,
            ambiguity_reason="no_provider_identity_in_scope",
        )

    if len(unique_identities) == 1:
        canonical = next(iter(unique_identities))
        source = "provider_scope" if canonical in set(unique_provider_ids) else "attached_account_id"
        return TikTokAccountDailyIdentityResolution(
            canonical_persistence_customer_id=canonical,
            identity_source=source,
            provider_ids_seen=unique_provider_ids,
            is_ambiguous=False,
            ambiguity_reason=None,
        )

    return TikTokAccountDailyIdentityResolution(
        canonical_persistence_customer_id=None,
        identity_source="ambiguous",
        provider_ids_seen=unique_provider_ids,
        is_ambiguous=True,
        ambiguity_reason="conflicting_provider_identities_in_scope",
    )
