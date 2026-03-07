import unittest
from datetime import date
from unittest.mock import patch

from app.workers import sync_worker


class SyncWorkerTests(unittest.TestCase):
    def _build_state(self, *, job_type: str = "manual", grain: object = "account_daily", platform: str = "google_ads") -> dict[str, object]:
        return {
            "run": {
                "job_id": "job-1",
                "platform": platform,
                "status": "queued",
                "client_id": 101,
                "account_id": "3986597205",
                "job_type": job_type,
                "date_end": str(date(2026, 2, 7)),
                "chunk_days": 7,
                "chunks_done": 0,
                "rows_written": 0,
                "error": None,
                "grain": grain,
            },
            "chunk": {
                "job_id": "job-1",
                "chunk_index": 0,
                "date_start": str(date(2026, 2, 1)),
                "date_end": str(date(2026, 2, 7)),
                "status": "queued",
                "rows_written": 0,
            },
            "claimed": False,
            "metadata_calls": [],
        }

    def test_process_next_chunk_once_marks_done_updates_progress_and_watermark(self):
        state = self._build_state(job_type="manual")

        def _claim_any(**kwargs):
            if state["claimed"]:
                return None
            state["claimed"] = True
            state["chunk"]["status"] = "running"
            return dict(state["chunk"])

        def _get_run(job_id):
            if job_id != "job-1":
                return None
            return dict(state["run"])

        def _update_run_status(**kwargs):
            if kwargs.get("status") is not None:
                state["run"]["status"] = kwargs["status"]
            if kwargs.get("error") is not None:
                state["run"]["error"] = kwargs["error"]
            return dict(state["run"])

        def _update_chunk_status(**kwargs):
            state["chunk"]["status"] = kwargs["status"]
            if kwargs.get("rows_written") is not None:
                state["chunk"]["rows_written"] = int(kwargs.get("rows_written") or 0)
            return dict(state["chunk"])

        def _update_progress(**kwargs):
            state["run"]["chunks_done"] = int(state["run"].get("chunks_done") or 0) + int(kwargs.get("chunks_done_delta") or 0)
            state["run"]["rows_written"] = int(state["run"].get("rows_written") or 0) + int(kwargs.get("rows_written_delta") or 0)
            return dict(state["run"])

        def _counts(job_id):
            return {"remaining": 0 if state["chunk"]["status"] in ("done", "error") else 1, "errors": 0}

        def _metadata_update(**kwargs):
            state["metadata_calls"].append(dict(kwargs))
            return kwargs

        with patch.object(sync_worker.sync_run_chunks_store, "claim_next_queued_chunk_any", side_effect=_claim_any), patch.object(
            sync_worker.sync_runs_store,
            "get_sync_run",
            side_effect=_get_run,
        ), patch.object(sync_worker.sync_runs_store, "update_sync_run_status", side_effect=_update_run_status), patch.object(
            sync_worker.sync_run_chunks_store,
            "update_sync_run_chunk_status",
            side_effect=_update_chunk_status,
        ), patch.object(sync_worker.sync_runs_store, "update_sync_run_progress", side_effect=_update_progress), patch.object(
            sync_worker.sync_run_chunks_store,
            "get_sync_run_chunk_status_counts",
            side_effect=_counts,
        ), patch.object(
            sync_worker.client_registry_service,
            "update_platform_account_operational_metadata",
            side_effect=_metadata_update,
        ), patch.object(
            sync_worker.google_ads_service,
            "sync_customer_for_client",
            return_value={"inserted_rows": 9},
        ):
            processed = sync_worker.process_next_chunk()

        self.assertTrue(processed)
        self.assertEqual(state["chunk"]["status"], "done")
        self.assertEqual(state["run"]["chunks_done"], 1)
        self.assertEqual(state["run"]["rows_written"], 9)
        self.assertEqual(state["run"]["status"], "done")
        self.assertEqual(len(state["metadata_calls"]), 1)
        metadata_call = state["metadata_calls"][0]
        self.assertEqual(metadata_call["platform"], "google_ads")
        self.assertEqual(metadata_call["account_id"], "3986597205")
        self.assertEqual(metadata_call["last_run_id"], "job-1")
        self.assertIn("last_success_at", metadata_call)
        self.assertEqual(str(metadata_call.get("rolling_synced_through")), "2026-02-07")

    def test_process_next_chunk_error_updates_last_error(self):
        state = self._build_state(job_type="historical_backfill")

        def _claim_any(**kwargs):
            if state["claimed"]:
                return None
            state["claimed"] = True
            state["chunk"]["status"] = "running"
            return dict(state["chunk"])

        def _get_run(job_id):
            if job_id != "job-1":
                return None
            return dict(state["run"])

        def _update_run_status(**kwargs):
            if kwargs.get("status") is not None:
                state["run"]["status"] = kwargs["status"]
            if kwargs.get("error") is not None:
                state["run"]["error"] = kwargs["error"]
            return dict(state["run"])

        def _update_chunk_status(**kwargs):
            state["chunk"]["status"] = kwargs["status"]
            return dict(state["chunk"])

        def _update_progress(**kwargs):
            state["run"]["chunks_done"] = int(state["run"].get("chunks_done") or 0) + int(kwargs.get("chunks_done_delta") or 0)
            return dict(state["run"])

        def _counts(job_id):
            return {"remaining": 0 if state["chunk"]["status"] in ("done", "error") else 1, "errors": 1}

        def _metadata_update(**kwargs):
            state["metadata_calls"].append(dict(kwargs))
            return kwargs

        with patch.object(sync_worker.sync_run_chunks_store, "claim_next_queued_chunk_any", side_effect=_claim_any), patch.object(
            sync_worker.sync_runs_store,
            "get_sync_run",
            side_effect=_get_run,
        ), patch.object(sync_worker.sync_runs_store, "update_sync_run_status", side_effect=_update_run_status), patch.object(
            sync_worker.sync_run_chunks_store,
            "update_sync_run_chunk_status",
            side_effect=_update_chunk_status,
        ), patch.object(sync_worker.sync_runs_store, "update_sync_run_progress", side_effect=_update_progress), patch.object(
            sync_worker.sync_run_chunks_store,
            "get_sync_run_chunk_status_counts",
            side_effect=_counts,
        ), patch.object(
            sync_worker.client_registry_service,
            "update_platform_account_operational_metadata",
            side_effect=_metadata_update,
        ), patch.object(
            sync_worker.google_ads_service,
            "sync_customer_for_client_historical_range",
            side_effect=RuntimeError("boom"),
        ):
            processed = sync_worker.process_next_chunk()

        self.assertTrue(processed)
        self.assertEqual(state["chunk"]["status"], "error")
        self.assertEqual(state["run"]["status"], "error")
        self.assertEqual(len(state["metadata_calls"]), 1)
        metadata_call = state["metadata_calls"][0]
        self.assertEqual(metadata_call["platform"], "google_ads")
        self.assertEqual(metadata_call["account_id"], "3986597205")
        self.assertEqual(metadata_call["last_run_id"], "job-1")
        self.assertIn("last_error", metadata_call)


    def test_process_next_chunk_oauth_failure_marks_terminal_error_without_crash(self):
        state = self._build_state(job_type="historical_backfill")

        def _claim_any(**kwargs):
            if state["claimed"]:
                return None
            state["claimed"] = True
            state["chunk"]["status"] = "running"
            return dict(state["chunk"])

        def _get_run(job_id):
            if job_id != "job-1":
                return None
            return dict(state["run"])

        def _update_run_status(**kwargs):
            if kwargs.get("status") is not None:
                state["run"]["status"] = kwargs["status"]
            if kwargs.get("error") is not None:
                state["run"]["error"] = kwargs["error"]
            return dict(state["run"])

        def _update_chunk_status(**kwargs):
            state["chunk"]["status"] = kwargs["status"]
            if kwargs.get("error") is not None:
                state["chunk"]["error"] = kwargs["error"]
            return dict(state["chunk"])

        def _update_progress(**kwargs):
            state["run"]["chunks_done"] = int(state["run"].get("chunks_done") or 0) + int(kwargs.get("chunks_done_delta") or 0)
            return dict(state["run"])

        def _counts(job_id):
            return {"remaining": 0 if state["chunk"]["status"] in ("done", "error") else 1, "errors": 1}

        with patch.object(sync_worker.sync_run_chunks_store, "claim_next_queued_chunk_any", side_effect=_claim_any), patch.object(
            sync_worker.sync_runs_store,
            "get_sync_run",
            side_effect=_get_run,
        ), patch.object(sync_worker.sync_runs_store, "update_sync_run_status", side_effect=_update_run_status), patch.object(
            sync_worker.sync_run_chunks_store,
            "update_sync_run_chunk_status",
            side_effect=_update_chunk_status,
        ), patch.object(sync_worker.sync_runs_store, "update_sync_run_progress", side_effect=_update_progress), patch.object(
            sync_worker.sync_run_chunks_store,
            "get_sync_run_chunk_status_counts",
            side_effect=_counts,
        ), patch.object(
            sync_worker.client_registry_service,
            "update_platform_account_operational_metadata",
            return_value=None,
        ), patch.object(
            sync_worker.google_ads_service,
            "sync_customer_for_client_historical_range",
            side_effect=RuntimeError("POST https://oauth2.googleapis.com/token 400 Bad Request"),
        ):
            processed = sync_worker.process_next_chunk()

        self.assertTrue(processed)
        self.assertEqual(state["chunk"]["status"], "error")
        self.assertIn("oauth2.googleapis.com/token", str(state["chunk"].get("error") or ""))
        self.assertEqual(state["run"]["status"], "error")
        self.assertEqual(state["run"]["chunks_done"], 1)


    def test_process_next_chunk_null_grain_defaults_to_account_daily_path(self):
        state = self._build_state(job_type="manual", grain=None)

        def _claim_any(**kwargs):
            if state["claimed"]:
                return None
            state["claimed"] = True
            state["chunk"]["status"] = "running"
            return dict(state["chunk"])

        def _get_run(job_id):
            return dict(state["run"]) if job_id == "job-1" else None

        def _update_run_status(**kwargs):
            if kwargs.get("status") is not None:
                state["run"]["status"] = kwargs["status"]
            if kwargs.get("error") is not None:
                state["run"]["error"] = kwargs["error"]
            return dict(state["run"])

        def _update_chunk_status(**kwargs):
            state["chunk"]["status"] = kwargs["status"]
            state["chunk"]["metadata"] = kwargs.get("metadata") or {}
            return dict(state["chunk"])

        def _update_progress(**kwargs):
            state["run"]["chunks_done"] = int(state["run"].get("chunks_done") or 0) + int(kwargs.get("chunks_done_delta") or 0)
            return dict(state["run"])

        def _counts(job_id):
            return {"remaining": 0 if state["chunk"]["status"] in ("done", "error") else 1, "errors": 0}

        with patch.object(sync_worker.sync_run_chunks_store, "claim_next_queued_chunk_any", side_effect=_claim_any), patch.object(
            sync_worker.sync_runs_store,
            "get_sync_run",
            side_effect=_get_run,
        ), patch.object(sync_worker.sync_runs_store, "update_sync_run_status", side_effect=_update_run_status), patch.object(
            sync_worker.sync_run_chunks_store,
            "update_sync_run_chunk_status",
            side_effect=_update_chunk_status,
        ), patch.object(sync_worker.sync_runs_store, "update_sync_run_progress", side_effect=_update_progress), patch.object(
            sync_worker.sync_run_chunks_store,
            "get_sync_run_chunk_status_counts",
            side_effect=_counts,
        ), patch.object(
            sync_worker.client_registry_service,
            "update_platform_account_operational_metadata",
            return_value=None,
        ), patch.object(
            sync_worker.google_ads_service,
            "sync_customer_for_client",
            return_value={"inserted_rows": 3},
        ) as account_sync:
            processed = sync_worker.process_next_chunk()

        self.assertTrue(processed)
        self.assertEqual(state["chunk"]["status"], "done")
        self.assertEqual((state["chunk"].get("metadata") or {}).get("grain"), "account_daily")
        self.assertEqual(account_sync.call_count, 1)

    def test_process_next_chunk_unknown_grain_marks_error_without_crash(self):
        state = self._build_state(job_type="manual", grain="mystery_grain")

        def _claim_any(**kwargs):
            if state["claimed"]:
                return None
            state["claimed"] = True
            state["chunk"]["status"] = "running"
            return dict(state["chunk"])

        def _get_run(job_id):
            return dict(state["run"]) if job_id == "job-1" else None

        def _update_run_status(**kwargs):
            if kwargs.get("status") is not None:
                state["run"]["status"] = kwargs["status"]
            if kwargs.get("error") is not None:
                state["run"]["error"] = kwargs["error"]
            return dict(state["run"])

        def _update_chunk_status(**kwargs):
            state["chunk"]["status"] = kwargs["status"]
            state["chunk"]["error"] = kwargs.get("error")
            state["chunk"]["metadata"] = kwargs.get("metadata") or {}
            return dict(state["chunk"])

        def _update_progress(**kwargs):
            state["run"]["chunks_done"] = int(state["run"].get("chunks_done") or 0) + int(kwargs.get("chunks_done_delta") or 0)
            return dict(state["run"])

        def _counts(job_id):
            return {"remaining": 0 if state["chunk"]["status"] in ("done", "error") else 1, "errors": 1}

        with patch.object(sync_worker.sync_run_chunks_store, "claim_next_queued_chunk_any", side_effect=_claim_any), patch.object(
            sync_worker.sync_runs_store,
            "get_sync_run",
            side_effect=_get_run,
        ), patch.object(sync_worker.sync_runs_store, "update_sync_run_status", side_effect=_update_run_status), patch.object(
            sync_worker.sync_run_chunks_store,
            "update_sync_run_chunk_status",
            side_effect=_update_chunk_status,
        ), patch.object(sync_worker.sync_runs_store, "update_sync_run_progress", side_effect=_update_progress), patch.object(
            sync_worker.google_ads_service,
            "sync_customer_for_client",
            return_value={"inserted_rows": 3},
        ) as account_sync:
            processed = sync_worker.process_next_chunk()

        self.assertTrue(processed)
        self.assertEqual(state["chunk"]["status"], "error")
        self.assertIn("grain_not_supported", str(state["chunk"].get("error") or ""))
        self.assertEqual((state["chunk"].get("metadata") or {}).get("error_code"), "grain_not_supported")
        self.assertEqual(state["run"]["status"], "error")
        self.assertIn("grain_not_supported", str(state["run"].get("error") or ""))
        self.assertEqual(account_sync.call_count, 0)


    def test_process_next_chunk_campaign_daily_google_ads_upserts_entity_facts(self):
        state = self._build_state(job_type="manual", grain="campaign_daily", platform="google_ads")

        def _claim_any(**kwargs):
            if state["claimed"]:
                return None
            state["claimed"] = True
            state["chunk"]["status"] = "running"
            return dict(state["chunk"])

        def _get_run(job_id):
            return dict(state["run"]) if job_id == "job-1" else None

        def _update_run_status(**kwargs):
            if kwargs.get("status") is not None:
                state["run"]["status"] = kwargs["status"]
            if kwargs.get("error") is not None:
                state["run"]["error"] = kwargs["error"]
            return dict(state["run"])

        def _update_chunk_status(**kwargs):
            state["chunk"]["status"] = kwargs["status"]
            state["chunk"]["metadata"] = kwargs.get("metadata") or {}
            if kwargs.get("rows_written") is not None:
                state["chunk"]["rows_written"] = int(kwargs.get("rows_written") or 0)
            return dict(state["chunk"])

        def _update_progress(**kwargs):
            state["run"]["chunks_done"] = int(state["run"].get("chunks_done") or 0) + int(kwargs.get("chunks_done_delta") or 0)
            state["run"]["rows_written"] = int(state["run"].get("rows_written") or 0) + int(kwargs.get("rows_written_delta") or 0)
            return dict(state["run"])

        def _counts(job_id):
            return {"remaining": 0 if state["chunk"]["status"] in ("done", "error") else 1, "errors": 0}

        upsert_calls = []
        entity_upsert_calls = []

        class _Conn:
            def __enter__(self):
                return self
            def __exit__(self, exc_type, exc, tb):
                return False
            def commit(self):
                return None

        def _upsert_campaign(conn, rows):
            upsert_calls.append(rows)
            return len(rows)

        def _upsert_entities(conn, rows):
            entity_upsert_calls.append(rows)
            return len(rows)

        with patch.object(sync_worker.sync_run_chunks_store, "claim_next_queued_chunk_any", side_effect=_claim_any), patch.object(
            sync_worker.sync_runs_store,
            "get_sync_run",
            side_effect=_get_run,
        ), patch.object(sync_worker.sync_runs_store, "update_sync_run_status", side_effect=_update_run_status), patch.object(
            sync_worker.sync_run_chunks_store,
            "update_sync_run_chunk_status",
            side_effect=_update_chunk_status,
        ), patch.object(sync_worker.sync_runs_store, "update_sync_run_progress", side_effect=_update_progress), patch.object(
            sync_worker.sync_run_chunks_store,
            "get_sync_run_chunk_status_counts",
            side_effect=_counts,
        ), patch.object(sync_worker.sync_runs_store, "_connect", return_value=_Conn()), patch.object(
            sync_worker,
            "upsert_platform_campaigns",
            side_effect=_upsert_entities,
        ), patch.object(
            sync_worker,
            "upsert_campaign_performance_reports",
            side_effect=_upsert_campaign,
        ), patch.object(
            sync_worker,
            "reconcile_platform_account_watermarks",
            return_value={"updated_count_by_grain": {"campaign_daily": 1}},
        ), patch.object(
            sync_worker.client_registry_service,
            "update_platform_account_operational_metadata",
            return_value=None,
        ), patch.object(
            sync_worker.google_ads_service,
            "fetch_campaign_daily_metrics",
            return_value=[
                {
                    "campaign_id": "123",
                    "campaign_name": "Brand",
                    "campaign_status": "ENABLED",
                    "campaign_raw": {"id": "123", "name": "Brand", "status": "ENABLED"},
                    "campaign_payload_hash": "h1",
                    "report_date": "2026-02-01",
                    "spend": 1.2,
                    "impressions": 10,
                    "clicks": 2,
                    "conversions": 0.5,
                    "conversion_value": 5.0,
                    "extra_metrics": {"google_ads": {"cost_micros": 1200000}},
                },
                {
                    "campaign_id": "123",
                    "campaign_name": "Brand",
                    "campaign_status": "ENABLED",
                    "campaign_raw": {"id": "123", "name": "Brand", "status": "ENABLED"},
                    "campaign_payload_hash": "h1",
                    "report_date": "2026-02-02",
                    "spend": 1.5,
                    "impressions": 11,
                    "clicks": 3,
                    "conversions": 0.6,
                    "conversion_value": 5.5,
                    "extra_metrics": {"google_ads": {"cost_micros": 1500000}},
                }
            ],
        ) as campaign_fetch:
            processed = sync_worker.process_next_chunk()

        self.assertTrue(processed)
        self.assertEqual(state["chunk"]["status"], "done")
        self.assertEqual(state["run"]["status"], "done")
        self.assertEqual(state["chunk"]["rows_written"], 2)
        self.assertEqual(state["run"]["rows_written"], 2)
        self.assertEqual((state["chunk"].get("metadata") or {}).get("grain"), "campaign_daily")
        self.assertEqual(campaign_fetch.call_count, 1)
        self.assertEqual(str(campaign_fetch.call_args.kwargs["start_date"]), "2026-02-01")
        self.assertEqual(str(campaign_fetch.call_args.kwargs["end_date_exclusive"]), "2026-02-08")
        self.assertEqual(len(entity_upsert_calls), 1)
        self.assertEqual(len(entity_upsert_calls[0]), 1)
        self.assertEqual(entity_upsert_calls[0][0]["campaign_id"], "123")
        self.assertEqual(len(upsert_calls), 1)
        self.assertEqual(len(upsert_calls[0]), 2)
        self.assertEqual(upsert_calls[0][0]["source_job_id"], "job-1")
        self.assertEqual(str(upsert_calls[0][0]["source_window_start"]), "2026-02-01")
        self.assertEqual(str(upsert_calls[0][0]["source_window_end"]), "2026-02-08")

    def test_process_next_chunk_ad_group_daily_google_ads_upserts_entity_facts(self):
        state = self._build_state(job_type="manual", grain="ad_group_daily", platform="google_ads")

        def _claim_any(**kwargs):
            if state["claimed"]:
                return None
            state["claimed"] = True
            state["chunk"]["status"] = "running"
            return dict(state["chunk"])

        def _get_run(job_id):
            return dict(state["run"]) if job_id == "job-1" else None

        def _update_run_status(**kwargs):
            if kwargs.get("status") is not None:
                state["run"]["status"] = kwargs["status"]
            if kwargs.get("error") is not None:
                state["run"]["error"] = kwargs["error"]
            return dict(state["run"])

        def _update_chunk_status(**kwargs):
            state["chunk"]["status"] = kwargs["status"]
            state["chunk"]["metadata"] = kwargs.get("metadata") or {}
            if kwargs.get("rows_written") is not None:
                state["chunk"]["rows_written"] = int(kwargs.get("rows_written") or 0)
            return dict(state["chunk"])

        def _update_progress(**kwargs):
            state["run"]["chunks_done"] = int(state["run"].get("chunks_done") or 0) + int(kwargs.get("chunks_done_delta") or 0)
            state["run"]["rows_written"] = int(state["run"].get("rows_written") or 0) + int(kwargs.get("rows_written_delta") or 0)
            return dict(state["run"])

        def _counts(job_id):
            return {"remaining": 0 if state["chunk"]["status"] in ("done", "error") else 1, "errors": 0}

        entity_upsert_calls = []
        facts_upsert_calls = []

        class _Conn:
            def __enter__(self):
                return self
            def __exit__(self, exc_type, exc, tb):
                return False
            def commit(self):
                return None

        def _upsert_entities(conn, rows):
            entity_upsert_calls.append(rows)
            return len(rows)

        def _upsert_facts(conn, rows):
            facts_upsert_calls.append(rows)
            return len(rows)

        with patch.object(sync_worker.sync_run_chunks_store, "claim_next_queued_chunk_any", side_effect=_claim_any), patch.object(
            sync_worker.sync_runs_store,
            "get_sync_run",
            side_effect=_get_run,
        ), patch.object(sync_worker.sync_runs_store, "update_sync_run_status", side_effect=_update_run_status), patch.object(
            sync_worker.sync_run_chunks_store,
            "update_sync_run_chunk_status",
            side_effect=_update_chunk_status,
        ), patch.object(sync_worker.sync_runs_store, "update_sync_run_progress", side_effect=_update_progress), patch.object(
            sync_worker.sync_run_chunks_store,
            "get_sync_run_chunk_status_counts",
            side_effect=_counts,
        ), patch.object(sync_worker.sync_runs_store, "_connect", return_value=_Conn()), patch.object(
            sync_worker,
            "upsert_platform_ad_groups",
            side_effect=_upsert_entities,
        ), patch.object(
            sync_worker,
            "upsert_ad_group_performance_reports",
            side_effect=_upsert_facts,
        ), patch.object(
            sync_worker,
            "reconcile_platform_account_watermarks",
            return_value={"updated_count_by_grain": {"ad_group_daily": 1}},
        ), patch.object(
            sync_worker.client_registry_service,
            "update_platform_account_operational_metadata",
            return_value=None,
        ), patch.object(
            sync_worker.google_ads_service,
            "fetch_ad_group_daily_metrics",
            return_value=[
                {
                    "report_date": "2026-02-01",
                    "campaign_id": "cmp-1",
                    "campaign_name": "Campaign 1",
                    "ad_group_id": "ag-1",
                    "ad_group_name": "AG One",
                    "spend": 2.4,
                    "impressions": 100,
                    "clicks": 7,
                    "conversions": 1.2,
                    "conversion_value": 12.0,
                    "extra_metrics": {"google_ads": {"cost_micros": 2400000}},
                },
                {
                    "report_date": "2026-02-02",
                    "campaign_id": "cmp-1",
                    "campaign_name": "Campaign 1",
                    "ad_group_id": "ag-1",
                    "ad_group_name": "AG One",
                    "spend": 1.1,
                    "impressions": 90,
                    "clicks": 5,
                    "conversions": 0.7,
                    "conversion_value": 8.0,
                    "extra_metrics": {"google_ads": {"cost_micros": 1100000}},
                },
            ],
        ) as ad_group_fetch:
            processed = sync_worker.process_next_chunk()

        self.assertTrue(processed)
        self.assertEqual(state["chunk"]["status"], "done")
        self.assertEqual(state["run"]["status"], "done")
        self.assertEqual(state["chunk"]["rows_written"], 2)
        self.assertEqual((state["chunk"].get("metadata") or {}).get("grain"), "ad_group_daily")
        self.assertEqual(ad_group_fetch.call_count, 1)
        self.assertEqual(str(ad_group_fetch.call_args.kwargs["start_date"]), "2026-02-01")
        self.assertEqual(str(ad_group_fetch.call_args.kwargs["end_date_exclusive"]), "2026-02-08")
        self.assertEqual(ad_group_fetch.call_args.kwargs["source_job_id"], "job-1")
        self.assertEqual(len(entity_upsert_calls), 1)
        self.assertEqual(len(entity_upsert_calls[0]), 1)
        self.assertEqual(entity_upsert_calls[0][0]["ad_group_id"], "ag-1")
        self.assertEqual(len(facts_upsert_calls), 1)
        self.assertEqual(len(facts_upsert_calls[0]), 2)
        self.assertEqual(str(facts_upsert_calls[0][0]["source_window_end"]), "2026-02-08")




    def test_process_next_chunk_ad_daily_google_ads_upserts_entity_facts_and_reconciles(self):
        state = self._build_state(job_type="manual", grain="ad_daily", platform="google_ads")

        def _claim_any(**kwargs):
            if state["claimed"]:
                return None
            state["claimed"] = True
            state["chunk"]["status"] = "running"
            return dict(state["chunk"])

        def _get_run(job_id):
            return dict(state["run"]) if job_id == "job-1" else None

        def _update_run_status(**kwargs):
            if kwargs.get("status") is not None:
                state["run"]["status"] = kwargs["status"]
            if kwargs.get("error") is not None:
                state["run"]["error"] = kwargs["error"]
            return dict(state["run"])

        def _update_chunk_status(**kwargs):
            state["chunk"]["status"] = kwargs["status"]
            state["chunk"]["metadata"] = kwargs.get("metadata") or {}
            if kwargs.get("rows_written") is not None:
                state["chunk"]["rows_written"] = int(kwargs.get("rows_written") or 0)
            return dict(state["chunk"])

        def _update_progress(**kwargs):
            state["run"]["chunks_done"] = int(state["run"].get("chunks_done") or 0) + int(kwargs.get("chunks_done_delta") or 0)
            state["run"]["rows_written"] = int(state["run"].get("rows_written") or 0) + int(kwargs.get("rows_written_delta") or 0)
            return dict(state["run"])

        def _counts(job_id):
            return {"remaining": 0 if state["chunk"]["status"] in ("done", "error") else 1, "errors": 0}

        entity_upsert_calls = []
        facts_upsert_calls = []

        class _Conn:
            def __enter__(self):
                return self
            def __exit__(self, exc_type, exc, tb):
                return False
            def commit(self):
                return None

        def _upsert_entities(conn, rows):
            entity_upsert_calls.append(rows)
            return len(rows)

        def _upsert_facts(conn, rows):
            facts_upsert_calls.append(rows)
            return len(rows)

        with patch.object(sync_worker.sync_run_chunks_store, "claim_next_queued_chunk_any", side_effect=_claim_any), patch.object(
            sync_worker.sync_runs_store,
            "get_sync_run",
            side_effect=_get_run,
        ), patch.object(sync_worker.sync_runs_store, "update_sync_run_status", side_effect=_update_run_status), patch.object(
            sync_worker.sync_run_chunks_store,
            "update_sync_run_chunk_status",
            side_effect=_update_chunk_status,
        ), patch.object(sync_worker.sync_runs_store, "update_sync_run_progress", side_effect=_update_progress), patch.object(
            sync_worker.sync_run_chunks_store,
            "get_sync_run_chunk_status_counts",
            side_effect=_counts,
        ), patch.object(sync_worker.sync_runs_store, "_connect", return_value=_Conn()), patch.object(
            sync_worker,
            "upsert_platform_ads",
            side_effect=_upsert_entities,
        ), patch.object(
            sync_worker,
            "upsert_ad_unit_performance_reports",
            side_effect=_upsert_facts,
        ), patch.object(
            sync_worker,
            "reconcile_platform_account_watermarks",
            return_value={"updated_count_by_grain": {"ad_daily": 1}},
        ) as reconcile_mock, patch.object(
            sync_worker.client_registry_service,
            "update_platform_account_operational_metadata",
            return_value=None,
        ), patch.object(
            sync_worker.google_ads_service,
            "fetch_ad_unit_daily_metrics",
            return_value=[
                {
                    "report_date": "2026-02-01",
                    "campaign_id": "cmp-1",
                    "ad_group_id": "ag-1",
                    "ad_id": "ad-1",
                    "ad_name": "Ad One",
                    "ad_status": "ENABLED",
                    "spend": 4.2,
                    "impressions": 100,
                    "clicks": 5,
                    "conversions": 1.0,
                    "conversion_value": 15.0,
                    "extra_metrics": {"google_ads": {"cost_micros": 4200000}},
                }
            ],
        ) as ad_fetch:
            processed = sync_worker.process_next_chunk()

        self.assertTrue(processed)
        self.assertEqual(state["chunk"]["status"], "done")
        self.assertEqual(state["run"]["status"], "done")
        self.assertEqual((state["chunk"].get("metadata") or {}).get("grain"), "ad_daily")
        self.assertEqual(ad_fetch.call_count, 1)
        self.assertEqual(str(ad_fetch.call_args.kwargs["end_date_exclusive"]), "2026-02-08")
        self.assertEqual(len(entity_upsert_calls), 1)
        self.assertEqual(entity_upsert_calls[0][0]["ad_id"], "ad-1")
        self.assertEqual(len(facts_upsert_calls), 1)
        self.assertEqual(facts_upsert_calls[0][0]["ad_id"], "ad-1")
        self.assertEqual(str(facts_upsert_calls[0][0]["source_window_end"]), "2026-02-08")
        self.assertEqual(reconcile_mock.call_count, 1)
        self.assertEqual(reconcile_mock.call_args.kwargs["grains"], ["ad_daily"])



    def test_process_next_chunk_keyword_daily_google_ads_upserts_entity_facts_and_reconciles(self):
        state = self._build_state(job_type="manual", grain="keyword_daily", platform="google_ads")

        def _claim_any(**kwargs):
            if state["claimed"]:
                return None
            state["claimed"] = True
            state["chunk"]["status"] = "running"
            return dict(state["chunk"])

        def _get_run(job_id):
            return dict(state["run"]) if job_id == "job-1" else None

        def _update_run_status(**kwargs):
            if kwargs.get("status") is not None:
                state["run"]["status"] = kwargs["status"]
            if kwargs.get("error") is not None:
                state["run"]["error"] = kwargs["error"]
            return dict(state["run"])

        def _update_chunk_status(**kwargs):
            state["chunk"]["status"] = kwargs["status"]
            state["chunk"]["metadata"] = kwargs.get("metadata") or {}
            if kwargs.get("rows_written") is not None:
                state["chunk"]["rows_written"] = int(kwargs.get("rows_written") or 0)
            return dict(state["chunk"])

        def _update_progress(**kwargs):
            state["run"]["chunks_done"] = int(state["run"].get("chunks_done") or 0) + int(kwargs.get("chunks_done_delta") or 0)
            state["run"]["rows_written"] = int(state["run"].get("rows_written") or 0) + int(kwargs.get("rows_written_delta") or 0)
            return dict(state["run"])

        def _counts(job_id):
            return {"remaining": 0 if state["chunk"]["status"] in ("done", "error") else 1, "errors": 0}

        entity_upsert_calls = []
        facts_upsert_calls = []

        class _Conn:
            def __enter__(self):
                return self
            def __exit__(self, exc_type, exc, tb):
                return False
            def commit(self):
                return None

        def _upsert_entities(conn, rows):
            entity_upsert_calls.append(rows)
            return len(rows)

        def _upsert_facts(conn, rows):
            facts_upsert_calls.append(rows)
            return len(rows)

        with patch.object(sync_worker.sync_run_chunks_store, "claim_next_queued_chunk_any", side_effect=_claim_any), patch.object(
            sync_worker.sync_runs_store,
            "get_sync_run",
            side_effect=_get_run,
        ), patch.object(sync_worker.sync_runs_store, "update_sync_run_status", side_effect=_update_run_status), patch.object(
            sync_worker.sync_run_chunks_store,
            "update_sync_run_chunk_status",
            side_effect=_update_chunk_status,
        ), patch.object(sync_worker.sync_runs_store, "update_sync_run_progress", side_effect=_update_progress), patch.object(
            sync_worker.sync_run_chunks_store,
            "get_sync_run_chunk_status_counts",
            side_effect=_counts,
        ), patch.object(sync_worker.sync_runs_store, "_connect", return_value=_Conn()), patch.object(
            sync_worker,
            "upsert_platform_keywords",
            side_effect=_upsert_entities,
        ), patch.object(
            sync_worker,
            "upsert_keyword_performance_reports",
            side_effect=_upsert_facts,
        ), patch.object(
            sync_worker,
            "reconcile_platform_account_watermarks",
            return_value={"updated_count_by_grain": {"keyword_daily": 1}},
        ) as reconcile_mock, patch.object(
            sync_worker.client_registry_service,
            "update_platform_account_operational_metadata",
            return_value=None,
        ), patch.object(
            sync_worker.google_ads_service,
            "fetch_keyword_daily_metrics",
            return_value=[
                {
                    "report_date": "2026-02-01",
                    "campaign_id": "cmp-1",
                    "ad_group_id": "ag-1",
                    "keyword_id": "ag-1~555",
                    "keyword_text": "brand",
                    "match_type": "EXACT",
                    "status": "ENABLED",
                    "spend": 2.5,
                    "impressions": 100,
                    "clicks": 5,
                    "conversions": 1.0,
                    "conversion_value": 9.0,
                    "extra_metrics": {"google_ads": {"cost_micros": 2500000}},
                    "keyword_raw": {"criterion_id": "555"},
                    "keyword_payload_hash": "h1",
                }
            ],
        ) as kw_fetch:
            processed = sync_worker.process_next_chunk()

        self.assertTrue(processed)
        self.assertEqual(state["chunk"]["status"], "done")
        self.assertEqual(state["run"]["status"], "done")
        self.assertEqual((state["chunk"].get("metadata") or {}).get("grain"), "keyword_daily")
        self.assertEqual(kw_fetch.call_count, 1)
        self.assertEqual(str(kw_fetch.call_args.kwargs["end_date_exclusive"]), "2026-02-08")
        self.assertEqual(len(entity_upsert_calls), 1)
        self.assertEqual(entity_upsert_calls[0][0]["keyword_id"], "ag-1~555")
        self.assertEqual(len(facts_upsert_calls), 1)
        self.assertEqual(facts_upsert_calls[0][0]["keyword_id"], "ag-1~555")
        self.assertEqual(str(facts_upsert_calls[0][0]["source_window_end"]), "2026-02-08")
        self.assertEqual(reconcile_mock.call_count, 1)
        self.assertEqual(reconcile_mock.call_args.kwargs["grains"], ["keyword_daily"])

    def test_process_next_chunk_keyword_daily_non_google_is_terminal_grain_not_supported(self):
        state = self._build_state(job_type="manual", grain="keyword_daily", platform="meta_ads")

        def _claim_any(**kwargs):
            if state["claimed"]:
                return None
            state["claimed"] = True
            state["chunk"]["status"] = "running"
            return dict(state["chunk"])

        def _get_run(job_id):
            return dict(state["run"]) if job_id == "job-1" else None

        def _update_run_status(**kwargs):
            if kwargs.get("status") is not None:
                state["run"]["status"] = kwargs["status"]
            if kwargs.get("error") is not None:
                state["run"]["error"] = kwargs["error"]
            return dict(state["run"])

        def _update_chunk_status(**kwargs):
            state["chunk"]["status"] = kwargs["status"]
            if kwargs.get("error") is not None:
                state["chunk"]["error"] = kwargs["error"]
            return dict(state["chunk"])

        def _update_progress(**kwargs):
            state["run"]["chunks_done"] = int(state["run"].get("chunks_done") or 0) + int(kwargs.get("chunks_done_delta") or 0)
            return dict(state["run"])

        def _counts(job_id):
            return {"remaining": 0 if state["chunk"]["status"] in ("done", "error") else 1, "errors": 1}

        with patch.object(sync_worker.sync_run_chunks_store, "claim_next_queued_chunk_any", side_effect=_claim_any), patch.object(
            sync_worker.sync_runs_store,
            "get_sync_run",
            side_effect=_get_run,
        ), patch.object(sync_worker.sync_runs_store, "update_sync_run_status", side_effect=_update_run_status), patch.object(
            sync_worker.sync_run_chunks_store,
            "update_sync_run_chunk_status",
            side_effect=_update_chunk_status,
        ), patch.object(sync_worker.sync_runs_store, "update_sync_run_progress", side_effect=_update_progress), patch.object(
            sync_worker.sync_run_chunks_store,
            "get_sync_run_chunk_status_counts",
            side_effect=_counts,
        ), patch.object(
            sync_worker.client_registry_service,
            "update_platform_account_operational_metadata",
            return_value=None,
        ), patch.object(
            sync_worker.google_ads_service,
            "fetch_keyword_daily_metrics",
            return_value=[],
        ) as kw_fetch:
            processed = sync_worker.process_next_chunk()

        self.assertTrue(processed)
        self.assertEqual(state["chunk"]["status"], "error")
        self.assertIn("grain_not_supported", str(state["chunk"].get("error") or ""))
        self.assertEqual(state["run"]["status"], "error")
        self.assertIn("grain_not_supported", str(state["run"].get("error") or ""))
        self.assertEqual(kw_fetch.call_count, 0)


    def test_process_next_chunk_campaign_daily_non_google_is_terminal_grain_not_supported(self):
        state = self._build_state(job_type="manual", grain="campaign_daily", platform="meta_ads")

        def _claim_any(**kwargs):
            if state["claimed"]:
                return None
            state["claimed"] = True
            state["chunk"]["status"] = "running"
            return dict(state["chunk"])

        def _get_run(job_id):
            return dict(state["run"]) if job_id == "job-1" else None

        def _update_run_status(**kwargs):
            if kwargs.get("status") is not None:
                state["run"]["status"] = kwargs["status"]
            if kwargs.get("error") is not None:
                state["run"]["error"] = kwargs["error"]
            return dict(state["run"])

        def _update_chunk_status(**kwargs):
            state["chunk"]["status"] = kwargs["status"]
            if kwargs.get("error") is not None:
                state["chunk"]["error"] = kwargs["error"]
            return dict(state["chunk"])

        def _update_progress(**kwargs):
            state["run"]["chunks_done"] = int(state["run"].get("chunks_done") or 0) + int(kwargs.get("chunks_done_delta") or 0)
            return dict(state["run"])

        def _counts(job_id):
            return {"remaining": 0 if state["chunk"]["status"] in ("done", "error") else 1, "errors": 1}

        with patch.object(sync_worker.sync_run_chunks_store, "claim_next_queued_chunk_any", side_effect=_claim_any), patch.object(
            sync_worker.sync_runs_store,
            "get_sync_run",
            side_effect=_get_run,
        ), patch.object(sync_worker.sync_runs_store, "update_sync_run_status", side_effect=_update_run_status), patch.object(
            sync_worker.sync_run_chunks_store,
            "update_sync_run_chunk_status",
            side_effect=_update_chunk_status,
        ), patch.object(sync_worker.sync_runs_store, "update_sync_run_progress", side_effect=_update_progress), patch.object(
            sync_worker.sync_run_chunks_store,
            "get_sync_run_chunk_status_counts",
            side_effect=_counts,
        ), patch.object(
            sync_worker.client_registry_service,
            "update_platform_account_operational_metadata",
            return_value=None,
        ), patch.object(
            sync_worker.google_ads_service,
            "fetch_campaign_daily_metrics",
            return_value=[],
        ) as campaign_fetch:
            processed = sync_worker.process_next_chunk()

        self.assertTrue(processed)
        self.assertEqual(state["chunk"]["status"], "error")
        self.assertIn("grain_not_supported", str(state["chunk"].get("error") or ""))
        self.assertEqual(state["run"]["status"], "error")
        self.assertIn("grain_not_supported", str(state["run"].get("error") or ""))
        self.assertEqual(campaign_fetch.call_count, 0)


if __name__ == "__main__":
    unittest.main()
