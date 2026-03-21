from __future__ import annotations

import json
import os
from threading import Lock

from app.core.config import load_settings

try:
    import psycopg
except Exception:  # noqa: BLE001
    psycopg = None


_EMPTY_PROFILE = {
    "general": {},
    "business": {},
    "address": {},
    "representative": {},
    "logo_url": "",
}


class SubaccountBusinessProfileStore:
    def __init__(self) -> None:
        self._lock = Lock()
        self._schema_initialized = False
        self._memory_profiles: dict[int, dict[str, object]] = {}

    def _is_test_mode(self) -> bool:
        return load_settings().app_env == "test" and os.environ.get("PYTEST_CURRENT_TEST") is not None

    def _connect(self):
        settings = load_settings()
        if psycopg is None:
            raise RuntimeError("psycopg is required for subaccount business profile persistence")
        return psycopg.connect(settings.database_url)

    def _normalize_profile(self, payload: dict[str, object] | None) -> dict[str, object]:
        data = payload or {}
        general = data.get("general") if isinstance(data.get("general"), dict) else {}
        business = data.get("business") if isinstance(data.get("business"), dict) else {}
        address = data.get("address") if isinstance(data.get("address"), dict) else {}
        representative = data.get("representative") if isinstance(data.get("representative"), dict) else {}
        logo_url = str(data.get("logo_url") or "").strip()
        return {
            "general": {str(k): v for k, v in general.items()},
            "business": {str(k): v for k, v in business.items()},
            "address": {str(k): v for k, v in address.items()},
            "representative": {str(k): v for k, v in representative.items()},
            "logo_url": logo_url,
        }

    def _ensure_schema(self) -> None:
        if self._is_test_mode() or self._schema_initialized:
            return
        with self._lock:
            if self._schema_initialized:
                return
            with self._connect() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        CREATE TABLE IF NOT EXISTS subaccount_business_profiles (
                            client_id INTEGER PRIMARY KEY REFERENCES agency_clients(id) ON DELETE CASCADE,
                            payload_json JSONB NOT NULL DEFAULT '{}'::jsonb,
                            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                        )
                        """
                    )
                conn.commit()
            self._schema_initialized = True

    def initialize_schema(self) -> None:
        self._ensure_schema()

    def get_profile(self, *, client_id: int) -> dict[str, object]:
        if self._is_test_mode():
            with self._lock:
                return self._normalize_profile(self._memory_profiles.get(int(client_id), dict(_EMPTY_PROFILE)))

        self._ensure_schema()
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT payload_json FROM subaccount_business_profiles WHERE client_id = %s", (int(client_id),))
                row = cur.fetchone()
        if row is None:
            return self._normalize_profile(dict(_EMPTY_PROFILE))
        raw_payload = row[0] if isinstance(row[0], dict) else json.loads(str(row[0] or "{}"))
        return self._normalize_profile(raw_payload if isinstance(raw_payload, dict) else {})

    def upsert_profile(self, *, client_id: int, payload: dict[str, object]) -> dict[str, object]:
        normalized = self._normalize_profile(payload)
        if self._is_test_mode():
            with self._lock:
                self._memory_profiles[int(client_id)] = normalized
                return self._normalize_profile(normalized)

        self._ensure_schema()
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO subaccount_business_profiles (client_id, payload_json, updated_at)
                    VALUES (%s, %s::jsonb, NOW())
                    ON CONFLICT (client_id)
                    DO UPDATE SET payload_json = EXCLUDED.payload_json, updated_at = NOW()
                    """,
                    (int(client_id), json.dumps(normalized)),
                )
            conn.commit()
        return self.get_profile(client_id=int(client_id))


subaccount_business_profile_store = SubaccountBusinessProfileStore()

