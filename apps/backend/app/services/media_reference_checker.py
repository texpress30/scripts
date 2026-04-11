from __future__ import annotations

from dataclasses import dataclass
from typing import Any

try:
    import psycopg
except Exception:  # noqa: BLE001
    psycopg = None


@dataclass(frozen=True)
class MediaReference:
    kind: str          # e.g. "subaccount_business_profile" | "company_settings"
    entity_id: int | None
    entity_label: str  # human-readable string for error messages
    field: str         # e.g. "logo_media_id"


class MediaReferenceChecker:
    """Finds records across the app that point at a given media_id so we can
    refuse (or orchestrate) its deletion."""

    def _connect(self):
        from app.db.pool import get_connection
        return get_connection()

    def _find_subaccount_profile_references(self, *, media_id: str) -> list[MediaReference]:
        references: list[MediaReference] = []
        try:
            with self._connect() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT p.client_id,
                               COALESCE(c.name, '') AS client_name
                        FROM subaccount_business_profiles p
                        LEFT JOIN agency_clients c ON c.id = p.client_id
                        WHERE p.payload_json ->> 'logo_media_id' = %s
                        """,
                        (media_id,),
                    )
                    rows = cur.fetchall() or []
        except Exception:  # noqa: BLE001
            # Best-effort — if the legacy schema is not yet migrated, treat as no references.
            return references
        for row in rows:
            entity_id = int(row[0]) if row[0] is not None else None
            entity_label = str(row[1] or f"Sub-account #{entity_id}")
            references.append(
                MediaReference(
                    kind="subaccount_business_profile",
                    entity_id=entity_id,
                    entity_label=f"{entity_label} — Profil Business (logo)",
                    field="logo_media_id",
                )
            )
        return references

    def _find_company_settings_references(self, *, media_id: str) -> list[MediaReference]:
        references: list[MediaReference] = []
        try:
            with self._connect() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT id, COALESCE(name, '')
                        FROM companies
                        WHERE logo_media_id = %s
                        """,
                        (media_id,),
                    )
                    rows = cur.fetchall() or []
        except Exception:  # noqa: BLE001
            return references
        for row in rows:
            entity_id = int(row[0]) if row[0] is not None else None
            entity_label = str(row[1] or f"Company #{entity_id}")
            references.append(
                MediaReference(
                    kind="company_settings",
                    entity_id=entity_id,
                    entity_label=f"{entity_label} — Setări companie (logo)",
                    field="logo_media_id",
                )
            )
        return references

    def find_references(self, *, media_id: str) -> list[MediaReference]:
        normalized_media_id = str(media_id or "").strip()
        if normalized_media_id == "":
            return []
        references: list[MediaReference] = []
        references.extend(self._find_subaccount_profile_references(media_id=normalized_media_id))
        references.extend(self._find_company_settings_references(media_id=normalized_media_id))
        return references

    def serialize_references(self, references: list[MediaReference]) -> list[dict[str, Any]]:
        return [
            {
                "kind": ref.kind,
                "entity_id": ref.entity_id,
                "entity_label": ref.entity_label,
                "field": ref.field,
            }
            for ref in references
        ]


media_reference_checker = MediaReferenceChecker()
