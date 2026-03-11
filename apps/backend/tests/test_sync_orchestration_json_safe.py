from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from enum import Enum
import unittest
from unittest.mock import patch

from app.api import sync_orchestration


class SampleEnum(Enum):
    DIAGNOSTIC = "diagnostic"


class SyncOrchestrationJsonSafeTests(unittest.TestCase):
    def test_to_json_safe_handles_supported_types_recursively(self):
        payload = {
            "set_values": {"a", "b"},
            "run_at": datetime(2026, 3, 10, 12, 30, tzinfo=timezone.utc),
            "report_date": date(2026, 3, 10),
            "cost": Decimal("12.34"),
            "marker": SampleEnum.DIAGNOSTIC,
            "binary": b"abc",
            "nested": {"raw": {1, 2, 3}},
            "endpoint": "https://example.test/path?access_token=secret-token&ok=1",
            "access_token": "secret-token",
        }

        result = sync_orchestration.to_json_safe(payload)

        self.assertIsInstance(result, dict)
        self.assertCountEqual(result["set_values"], ["a", "b"])
        self.assertEqual(result["run_at"], "2026-03-10T12:30:00+00:00")
        self.assertEqual(result["report_date"], "2026-03-10")
        self.assertEqual(result["cost"], "12.34")
        self.assertEqual(result["marker"], "diagnostic")
        self.assertEqual(result["binary"], "abc")
        self.assertCountEqual(result["nested"]["raw"], [1, 2, 3])
        self.assertEqual(result["access_token"], "***")
        self.assertNotIn("secret-token", result["endpoint"])

    def test_serialize_chunk_keeps_observability_fields_json_safe(self):
        chunk = {
            "id": 1,
            "job_id": "job-1",
            "chunk_index": 0,
            "status": "done",
            "date_start": "2026-03-01",
            "date_end": "2026-03-01",
            "attempts": 1,
            "rows_written": 0,
            "duration_ms": 123,
            "started_at": datetime(2026, 3, 1, 9, 0, tzinfo=timezone.utc),
            "finished_at": datetime(2026, 3, 1, 9, 1, tzinfo=timezone.utc),
            "created_at": datetime(2026, 3, 1, 9, 0, tzinfo=timezone.utc),
            "updated_at": datetime(2026, 3, 1, 9, 1, tzinfo=timezone.utc),
            "error": None,
            "metadata": {
                "rows_downloaded": Decimal("0"),
                "rows_mapped": 0,
                "zero_row_marker": "provider_returned_empty_list",
                "sample_row_keys": {"stat_time_day", "campaign_id"},
                "skipped_missing_required": Decimal("2"),
                "skipped_invalid_date": 1,
            },
        }

        serialized = sync_orchestration._serialize_chunk(chunk)
        metadata = serialized["metadata"]

        self.assertEqual(metadata["zero_row_marker"], "provider_returned_empty_list")
        self.assertEqual(metadata["rows_downloaded"], "0")
        self.assertEqual(metadata["rows_mapped"], 0)
        self.assertCountEqual(metadata["sample_row_keys"], ["stat_time_day", "campaign_id"])
        self.assertEqual(metadata["skipped_missing_required"], "2")
        self.assertEqual(metadata["skipped_invalid_date"], 1)

    def test_to_json_safe_masks_sensitive_keys_and_url_query_tokens(self):
        payload = {
            "refresh_token": "abcd",
            "nested": {"api_key": "xyz"},
            "url": "https://test.local/report?token=abcd&page=1",
        }

        result = sync_orchestration.to_json_safe(payload)

        self.assertEqual(result["refresh_token"], "***")
        self.assertEqual(result["nested"]["api_key"], "***")
        self.assertNotIn("abcd", result["url"])
        self.assertIn("page=1", result["url"])

    def test_list_sync_run_chunks_endpoint_function_returns_json_safe_payload(self):
        chunk = {
            "id": 1,
            "job_id": "job-1",
            "chunk_index": 0,
            "status": "done",
            "date_start": "2026-03-01",
            "date_end": "2026-03-01",
            "attempts": 1,
            "rows_written": 0,
            "duration_ms": 5,
            "started_at": None,
            "finished_at": None,
            "created_at": None,
            "updated_at": None,
            "error": None,
            "metadata": {
                "rows_downloaded": 0,
                "rows_mapped": 0,
                "zero_row_marker": "provider_returned_empty_list",
                "sample_row_keys": {"a", "b"},
                "skipped_missing_required": Decimal("0"),
                "skipped_invalid_date": 0,
                "when": datetime(2026, 3, 1, 10, 0, tzinfo=timezone.utc),
            },
        }

        with patch.object(sync_orchestration, "enforce_action_scope", side_effect=lambda **kwargs: None), patch.object(
            sync_orchestration.sync_runs_store,
            "get_sync_run",
            return_value={"job_id": "job-1"},
        ), patch.object(
            sync_orchestration.sync_run_chunks_store,
            "list_sync_run_chunks",
            return_value=[chunk],
        ):
            payload = sync_orchestration.list_sync_run_chunks("job-1", user=None)

        self.assertEqual(payload["job_id"], "job-1")
        self.assertEqual(len(payload["chunks"]), 1)
        metadata = payload["chunks"][0]["metadata"]
        self.assertEqual(metadata["zero_row_marker"], "provider_returned_empty_list")
        self.assertEqual(metadata["rows_downloaded"], 0)
        self.assertEqual(metadata["rows_mapped"], 0)
        self.assertCountEqual(metadata["sample_row_keys"], ["a", "b"])
        self.assertEqual(metadata["skipped_missing_required"], "0")
        self.assertEqual(metadata["when"], "2026-03-01T10:00:00+00:00")


if __name__ == "__main__":
    unittest.main()
