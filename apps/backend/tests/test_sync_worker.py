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

    def test_process_next_chunk_meta_campaign_daily_uses_meta_sync_service(self):
        state = self._build_state(job_type="rolling_refresh", grain="campaign_daily", platform="meta_ads")

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
            if kwargs.get("metadata") is not None:
                state["chunk"]["metadata"] = kwargs.get("metadata") or {}
            if kwargs.get("error") is not None:
                state["chunk"]["error"] = kwargs["error"]
            if kwargs.get("rows_written") is not None:
                state["chunk"]["rows_written"] = int(kwargs.get("rows_written") or 0)
            return dict(state["chunk"])

        def _update_progress(**kwargs):
            state["run"]["chunks_done"] = int(state["run"].get("chunks_done") or 0) + int(kwargs.get("chunks_done_delta") or 0)
            state["run"]["rows_written"] = int(state["run"].get("rows_written") or 0) + int(kwargs.get("rows_written_delta") or 0)
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
            sync_worker.meta_ads_service,
            "sync_client",
            return_value={"rows_written": 7, "grain": "campaign_daily", "accounts_processed": 1, "token_source": "database"},
        ) as meta_sync_mock, patch.object(
            sync_worker.google_ads_service,
            "fetch_campaign_daily_metrics",
            return_value=[],
        ) as google_fetch_mock:
            processed = sync_worker.process_next_chunk()

        self.assertTrue(processed)
        self.assertEqual(state["chunk"]["status"], "done")
        self.assertEqual(state["chunk"]["rows_written"], 7)
        self.assertEqual(state["run"]["status"], "done")
        self.assertEqual(state["run"]["rows_written"], 7)
        self.assertEqual(meta_sync_mock.call_count, 1)
        self.assertEqual(meta_sync_mock.call_args.kwargs["grain"], "campaign_daily")
        self.assertEqual(meta_sync_mock.call_args.kwargs["account_id"], "3986597205")
        self.assertEqual(google_fetch_mock.call_count, 0)

    def test_process_next_chunk_tiktok_ad_daily_uses_tiktok_sync_service(self):
        state = self._build_state(job_type="rolling_refresh", grain="ad_daily", platform="tiktok_ads")

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
            if kwargs.get("metadata") is not None:
                state["chunk"]["metadata"] = kwargs.get("metadata") or {}
            if kwargs.get("error") is not None:
                state["chunk"]["error"] = kwargs["error"]
            if kwargs.get("rows_written") is not None:
                state["chunk"]["rows_written"] = int(kwargs.get("rows_written") or 0)
            return dict(state["chunk"])

        def _update_progress(**kwargs):
            state["run"]["chunks_done"] = int(state["run"].get("chunks_done") or 0) + int(kwargs.get("chunks_done_delta") or 0)
            state["run"]["rows_written"] = int(state["run"].get("rows_written") or 0) + int(kwargs.get("rows_written_delta") or 0)
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
            sync_worker.tiktok_ads_service,
            "sync_client",
            return_value={
                "rows_written": 5,
                "rows_downloaded": 12,
                "provider_row_count": 12,
                "rows_mapped": 5,
                "zero_row_observability": [{"zero_row_marker": "provider_returned_empty_list", "account_id": "3986597205"}],
                "grain": "ad_daily",
                "accounts_processed": 1,
                "token_source": "database",
            },
        ) as tiktok_sync_mock:
            processed = sync_worker.process_next_chunk()

        self.assertTrue(processed)
        self.assertEqual(state["chunk"]["status"], "done")
        self.assertEqual(state["chunk"]["rows_written"], 5)
        self.assertEqual(state["run"]["status"], "done")
        self.assertEqual(state["run"]["rows_written"], 5)
        self.assertEqual((state["chunk"].get("metadata") or {}).get("rows_downloaded"), 12)
        self.assertEqual((state["chunk"].get("metadata") or {}).get("provider_row_count"), 12)
        self.assertEqual((state["chunk"].get("metadata") or {}).get("rows_mapped"), 5)
        self.assertEqual(tiktok_sync_mock.call_count, 1)
        self.assertEqual(tiktok_sync_mock.call_args.kwargs["grain"], "ad_daily")
        self.assertEqual(tiktok_sync_mock.call_args.kwargs["account_id"], "3986597205")

    def test_process_next_chunk_tiktok_error_maps_to_run_status(self):
        state = self._build_state(job_type="rolling_refresh", grain="campaign_daily", platform="tiktok_ads")

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
            sync_worker.tiktok_ads_service,
            "sync_client",
            side_effect=sync_worker.TikTokAdsIntegrationError("TikTok reporting API failed: code=401"),
        ):
            processed = sync_worker.process_next_chunk()

        self.assertTrue(processed)
        self.assertEqual(state["chunk"]["status"], "error")
        self.assertIn("TikTok reporting API failed", str(state["chunk"].get("error") or ""))
        self.assertEqual(state["run"]["status"], "error")
        self.assertIn("TikTok reporting API failed", str(state["run"].get("error") or ""))

    def test_process_next_chunk_meta_campaign_daily_error_maps_to_run_status(self):
        state = self._build_state(job_type="rolling_refresh", grain="campaign_daily", platform="meta_ads")

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
            sync_worker.meta_ads_service,
            "sync_client",
            side_effect=sync_worker.MetaAdsIntegrationError("Meta API request failed: status=401"),
        ):
            processed = sync_worker.process_next_chunk()

        self.assertTrue(processed)
        self.assertEqual(state["chunk"]["status"], "error")
        self.assertIn("Meta API request failed", str(state["chunk"].get("error") or ""))
        self.assertEqual(state["run"]["status"], "error")
        self.assertIn("Meta API request failed", str(state["run"].get("error") or ""))


    def test_process_next_chunk_tiktok_error_stores_structured_details(self):
        state = self._build_state(job_type="historical_backfill", grain="ad_daily", platform="tiktok_ads")
        captured_chunk_updates = []

        def _claim_any(**kwargs):
            if state["claimed"]:
                return None
            state["claimed"] = True
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
            captured_chunk_updates.append(dict(kwargs))
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
            sync_worker.tiktok_ads_service,
            "sync_client",
            side_effect=sync_worker.TikTokAdsIntegrationError(
                "TikTok advertiser access probe failed for advertiser 3986597205.",
                endpoint="https://business-api.tiktok.com/open_api/v1.3/oauth2/advertiser/get/?access_token=tok_abcdefghijklmnopqrstuvwxyz123456",
                http_status=401,
                provider_error_code="40100",
                provider_error_message="Unauthorized access_token tok_abcdefghijklmnopqrstuvwxyz123456",
                retryable=False,
                error_category="token_missing_or_invalid",
                token_source="database",
                advertiser_id="3986597205",
            ),
        ):
            processed = sync_worker.process_next_chunk()

        self.assertTrue(processed)
        self.assertEqual(state["chunk"]["status"], "error")
        error_update = next(item for item in captured_chunk_updates if item.get("status") == "error")
        details = error_update["metadata"]["last_error_details"]
        self.assertEqual(details["provider_error_code"], "40100")
        self.assertEqual(details["http_status"], 401)
        self.assertEqual(details["platform"], "tiktok_ads")
        self.assertEqual(details["grain"], "ad_daily")
        self.assertEqual(details.get("error_category"), "token_missing_or_invalid")
        self.assertEqual(details.get("token_source"), "database")
        self.assertEqual(details.get("advertiser_id"), "3986597205")
        self.assertNotIn("tok_abcdefghijklmnopqrstuvwxyz123456", str(details))


    def test_meta_historical_success_uses_chunk_coverage_end_for_backfill_metadata(self):
        state = self._build_state(job_type="historical_backfill", platform="meta_ads")
        state["run"]["account_id"] = "act_123"
        state["run"]["date_end"] = str(date(2026, 2, 7))

        metadata_calls = []

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
            return dict(state["run"])

        def _update_chunk_status(**kwargs):
            state["chunk"]["status"] = kwargs["status"]
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
            sync_worker.sync_run_chunks_store,
            "list_sync_run_chunks",
            return_value=[
                {"chunk_index": 0, "status": "done", "date_end": str(date(2026, 2, 12))},
                {"chunk_index": 1, "status": "done", "date_end": str(date(2026, 2, 14))},
            ],
        ), patch.object(
            sync_worker.client_registry_service,
            "update_platform_account_operational_metadata",
            side_effect=lambda **kwargs: metadata_calls.append(kwargs) or kwargs,
        ), patch.object(
            sync_worker.meta_ads_service,
            "sync_client",
            return_value={"rows_upserted": 0},
        ):
            processed = sync_worker.process_next_chunk()

        self.assertTrue(processed)
        self.assertEqual(state["run"]["status"], "done")
        self.assertEqual(len(metadata_calls), 1)
        self.assertEqual(str(metadata_calls[0].get("backfill_completed_through")), "2026-02-14")
        self.assertNotIn("rolling_synced_through", metadata_calls[0])

    def test_tiktok_historical_empty_success_does_not_advance_backfill_coverage(self):
        state = self._build_state(job_type="historical_backfill", platform="tiktok_ads")

        metadata_calls = []

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
            if isinstance(kwargs.get("metadata"), dict):
                existing = state["run"].get("metadata") if isinstance(state["run"].get("metadata"), dict) else {}
                merged = dict(existing)
                merged.update(kwargs.get("metadata") or {})
                state["run"]["metadata"] = merged
            return dict(state["run"])

        def _update_chunk_status(**kwargs):
            state["chunk"]["status"] = kwargs["status"]
            if kwargs.get("metadata") is not None:
                state["chunk"]["metadata"] = kwargs.get("metadata") or {}
            return dict(state["chunk"])

        def _update_progress(**kwargs):
            state["run"]["chunks_done"] = int(state["run"].get("chunks_done") or 0) + int(kwargs.get("chunks_done_delta") or 0)
            state["run"]["rows_written"] = int(state["run"].get("rows_written") or 0) + int(kwargs.get("rows_written_delta") or 0)
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
            sync_worker.sync_run_chunks_store,
            "list_sync_run_chunks",
            return_value=[
                {
                    "chunk_index": 0,
                    "status": "done",
                    "metadata": {
                        "rows_downloaded": 0,
                        "rows_mapped": 0,
                        "zero_row_observability": [{"zero_row_marker": "provider_returned_empty_list"}],
                    },
                }
            ],
        ), patch.object(
            sync_worker.client_registry_service,
            "update_platform_account_operational_metadata",
            side_effect=lambda **kwargs: metadata_calls.append(kwargs) or kwargs,
        ), patch.object(
            sync_worker.tiktok_ads_service,
            "sync_client",
            return_value={
                "rows_written": 0,
                "rows_downloaded": 0,
                "provider_row_count": 0,
                "rows_mapped": 0,
                "zero_row_observability": [{"zero_row_marker": "provider_returned_empty_list"}],
            },
        ):
            processed = sync_worker.process_next_chunk()

        self.assertTrue(processed)
        self.assertEqual(state["run"]["status"], "done")
        self.assertEqual(len(metadata_calls), 1)
        self.assertNotIn("backfill_completed_through", metadata_calls[0])
        run_metadata = state["run"].get("metadata") or {}
        self.assertTrue(bool(run_metadata.get("no_data_success")))
        self.assertEqual(run_metadata.get("zero_row_marker"), "provider_returned_empty_list")



    def test_tiktok_historical_parser_failure_marks_run_error_and_does_not_advance_backfill(self):
        state = self._build_state(job_type="historical_backfill", platform="tiktok_ads")

        metadata_calls = []

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
                state["run"]["error"] = kwargs.get("error")
            if isinstance(kwargs.get("metadata"), dict):
                existing = state["run"].get("metadata") if isinstance(state["run"].get("metadata"), dict) else {}
                merged = dict(existing)
                merged.update(kwargs.get("metadata") or {})
                state["run"]["metadata"] = merged
            return dict(state["run"])

        def _update_chunk_status(**kwargs):
            state["chunk"]["status"] = kwargs["status"]
            if kwargs.get("metadata") is not None:
                state["chunk"]["metadata"] = kwargs.get("metadata") or {}
            return dict(state["chunk"])

        def _update_progress(**kwargs):
            state["run"]["chunks_done"] = int(state["run"].get("chunks_done") or 0) + int(kwargs.get("chunks_done_delta") or 0)
            state["run"]["rows_written"] = int(state["run"].get("rows_written") or 0) + int(kwargs.get("rows_written_delta") or 0)
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
            sync_worker.sync_run_chunks_store,
            "list_sync_run_chunks",
            return_value=[
                {
                    "chunk_index": 0,
                    "status": "done",
                    "metadata": {
                        "rows_downloaded": 30,
                        "rows_mapped": 0,
                        "zero_row_observability": [{"zero_row_marker": "response_parsed_but_zero_rows_mapped"}],
                    },
                }
            ],
        ), patch.object(
            sync_worker.client_registry_service,
            "update_platform_account_operational_metadata",
            side_effect=lambda **kwargs: metadata_calls.append(kwargs) or kwargs,
        ), patch.object(
            sync_worker.tiktok_ads_service,
            "sync_client",
            return_value={
                "rows_written": 0,
                "rows_downloaded": 30,
                "provider_row_count": 30,
                "rows_mapped": 0,
                "zero_row_observability": [{"zero_row_marker": "response_parsed_but_zero_rows_mapped"}],
            },
        ):
            processed = sync_worker.process_next_chunk()

        self.assertTrue(processed)
        self.assertEqual(state["run"]["status"], "error")
        self.assertEqual(len(metadata_calls), 1)
        self.assertNotIn("backfill_completed_through", metadata_calls[0])
        self.assertNotIn("last_success_at", metadata_calls[0])
        self.assertIn("parser_failure", str(metadata_calls[0].get("last_error") or ""))
        run_metadata = state["run"].get("metadata") or {}
        self.assertTrue(bool(run_metadata.get("parser_failure")))

    def test_tiktok_historical_empty_success_does_not_advance_backfill_coverage(self):
        state = self._build_state(job_type="historical_backfill", platform="tiktok_ads")

        metadata_calls = []

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
            if isinstance(kwargs.get("metadata"), dict):
                existing = state["run"].get("metadata") if isinstance(state["run"].get("metadata"), dict) else {}
                merged = dict(existing)
                merged.update(kwargs.get("metadata") or {})
                state["run"]["metadata"] = merged
            return dict(state["run"])

        def _update_chunk_status(**kwargs):
            state["chunk"]["status"] = kwargs["status"]
            if kwargs.get("metadata") is not None:
                state["chunk"]["metadata"] = kwargs.get("metadata") or {}
            return dict(state["chunk"])

        def _update_progress(**kwargs):
            state["run"]["chunks_done"] = int(state["run"].get("chunks_done") or 0) + int(kwargs.get("chunks_done_delta") or 0)
            state["run"]["rows_written"] = int(state["run"].get("rows_written") or 0) + int(kwargs.get("rows_written_delta") or 0)
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
            sync_worker.sync_run_chunks_store,
            "list_sync_run_chunks",
            return_value=[
                {
                    "chunk_index": 0,
                    "status": "done",
                    "metadata": {
                        "rows_downloaded": 0,
                        "rows_mapped": 0,
                        "zero_row_observability": [{"zero_row_marker": "provider_returned_empty_list"}],
                    },
                }
            ],
        ), patch.object(
            sync_worker.client_registry_service,
            "update_platform_account_operational_metadata",
            side_effect=lambda **kwargs: metadata_calls.append(kwargs) or kwargs,
        ), patch.object(
            sync_worker.tiktok_ads_service,
            "sync_client",
            return_value={
                "rows_written": 0,
                "rows_downloaded": 0,
                "provider_row_count": 0,
                "rows_mapped": 0,
                "zero_row_observability": [{"zero_row_marker": "provider_returned_empty_list"}],
            },
        ):
            processed = sync_worker.process_next_chunk()

        self.assertTrue(processed)
        self.assertEqual(state["run"]["status"], "done")
        self.assertEqual(len(metadata_calls), 1)
        self.assertNotIn("backfill_completed_through", metadata_calls[0])
        run_metadata = state["run"].get("metadata") or {}
        self.assertTrue(bool(run_metadata.get("no_data_success")))
        self.assertEqual(run_metadata.get("zero_row_marker"), "provider_returned_empty_list")



    def test_tiktok_historical_parser_failure_marks_run_error_and_does_not_advance_backfill(self):
        state = self._build_state(job_type="historical_backfill", platform="tiktok_ads")

        metadata_calls = []

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
                state["run"]["error"] = kwargs.get("error")
            if isinstance(kwargs.get("metadata"), dict):
                existing = state["run"].get("metadata") if isinstance(state["run"].get("metadata"), dict) else {}
                merged = dict(existing)
                merged.update(kwargs.get("metadata") or {})
                state["run"]["metadata"] = merged
            return dict(state["run"])

        def _update_chunk_status(**kwargs):
            state["chunk"]["status"] = kwargs["status"]
            if kwargs.get("metadata") is not None:
                state["chunk"]["metadata"] = kwargs.get("metadata") or {}
            return dict(state["chunk"])

        def _update_progress(**kwargs):
            state["run"]["chunks_done"] = int(state["run"].get("chunks_done") or 0) + int(kwargs.get("chunks_done_delta") or 0)
            state["run"]["rows_written"] = int(state["run"].get("rows_written") or 0) + int(kwargs.get("rows_written_delta") or 0)
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
            sync_worker.sync_run_chunks_store,
            "list_sync_run_chunks",
            return_value=[
                {
                    "chunk_index": 0,
                    "status": "done",
                    "metadata": {
                        "rows_downloaded": 30,
                        "rows_mapped": 0,
                        "zero_row_observability": [{"zero_row_marker": "response_parsed_but_zero_rows_mapped"}],
                    },
                }
            ],
        ), patch.object(
            sync_worker.client_registry_service,
            "update_platform_account_operational_metadata",
            side_effect=lambda **kwargs: metadata_calls.append(kwargs) or kwargs,
        ), patch.object(
            sync_worker.tiktok_ads_service,
            "sync_client",
            return_value={
                "rows_written": 0,
                "rows_downloaded": 30,
                "provider_row_count": 30,
                "rows_mapped": 0,
                "zero_row_observability": [{"zero_row_marker": "response_parsed_but_zero_rows_mapped"}],
            },
        ):
            processed = sync_worker.process_next_chunk()

        self.assertTrue(processed)
        self.assertEqual(state["run"]["status"], "error")
        self.assertEqual(len(metadata_calls), 1)
        self.assertNotIn("backfill_completed_through", metadata_calls[0])
        self.assertNotIn("last_success_at", metadata_calls[0])
        self.assertIn("parser_failure", str(metadata_calls[0].get("last_error") or ""))
        run_metadata = state["run"].get("metadata") or {}
        self.assertTrue(bool(run_metadata.get("parser_failure")))

    def test_tiktok_historical_empty_success_does_not_advance_backfill_coverage(self):
        state = self._build_state(job_type="historical_backfill", platform="tiktok_ads")

        metadata_calls = []

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
            if isinstance(kwargs.get("metadata"), dict):
                existing = state["run"].get("metadata") if isinstance(state["run"].get("metadata"), dict) else {}
                merged = dict(existing)
                merged.update(kwargs.get("metadata") or {})
                state["run"]["metadata"] = merged
            return dict(state["run"])

        def _update_chunk_status(**kwargs):
            state["chunk"]["status"] = kwargs["status"]
            if kwargs.get("metadata") is not None:
                state["chunk"]["metadata"] = kwargs.get("metadata") or {}
            return dict(state["chunk"])

        def _update_progress(**kwargs):
            state["run"]["chunks_done"] = int(state["run"].get("chunks_done") or 0) + int(kwargs.get("chunks_done_delta") or 0)
            state["run"]["rows_written"] = int(state["run"].get("rows_written") or 0) + int(kwargs.get("rows_written_delta") or 0)
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
            sync_worker.sync_run_chunks_store,
            "list_sync_run_chunks",
            return_value=[
                {
                    "chunk_index": 0,
                    "status": "done",
                    "metadata": {
                        "rows_downloaded": 0,
                        "rows_mapped": 0,
                        "zero_row_observability": [{"zero_row_marker": "provider_returned_empty_list"}],
                    },
                }
            ],
        ), patch.object(
            sync_worker.client_registry_service,
            "update_platform_account_operational_metadata",
            side_effect=lambda **kwargs: metadata_calls.append(kwargs) or kwargs,
        ), patch.object(
            sync_worker.tiktok_ads_service,
            "sync_client",
            return_value={
                "rows_written": 0,
                "rows_downloaded": 0,
                "provider_row_count": 0,
                "rows_mapped": 0,
                "zero_row_observability": [{"zero_row_marker": "provider_returned_empty_list"}],
            },
        ):
            processed = sync_worker.process_next_chunk()

        self.assertTrue(processed)
        self.assertEqual(state["run"]["status"], "done")
        self.assertEqual(len(metadata_calls), 1)
        self.assertNotIn("backfill_completed_through", metadata_calls[0])
        run_metadata = state["run"].get("metadata") or {}
        self.assertTrue(bool(run_metadata.get("no_data_success")))
        self.assertEqual(run_metadata.get("zero_row_marker"), "provider_returned_empty_list")



    def test_tiktok_historical_parser_failure_marks_run_error_and_does_not_advance_backfill(self):
        state = self._build_state(job_type="historical_backfill", platform="tiktok_ads")

        metadata_calls = []

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
                state["run"]["error"] = kwargs.get("error")
            if isinstance(kwargs.get("metadata"), dict):
                existing = state["run"].get("metadata") if isinstance(state["run"].get("metadata"), dict) else {}
                merged = dict(existing)
                merged.update(kwargs.get("metadata") or {})
                state["run"]["metadata"] = merged
            return dict(state["run"])

        def _update_chunk_status(**kwargs):
            state["chunk"]["status"] = kwargs["status"]
            if kwargs.get("metadata") is not None:
                state["chunk"]["metadata"] = kwargs.get("metadata") or {}
            return dict(state["chunk"])

        def _update_progress(**kwargs):
            state["run"]["chunks_done"] = int(state["run"].get("chunks_done") or 0) + int(kwargs.get("chunks_done_delta") or 0)
            state["run"]["rows_written"] = int(state["run"].get("rows_written") or 0) + int(kwargs.get("rows_written_delta") or 0)
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
            sync_worker.sync_run_chunks_store,
            "list_sync_run_chunks",
            return_value=[
                {
                    "chunk_index": 0,
                    "status": "done",
                    "metadata": {
                        "rows_downloaded": 30,
                        "rows_mapped": 0,
                        "zero_row_observability": [{"zero_row_marker": "response_parsed_but_zero_rows_mapped"}],
                    },
                }
            ],
        ), patch.object(
            sync_worker.client_registry_service,
            "update_platform_account_operational_metadata",
            side_effect=lambda **kwargs: metadata_calls.append(kwargs) or kwargs,
        ), patch.object(
            sync_worker.tiktok_ads_service,
            "sync_client",
            return_value={
                "rows_written": 0,
                "rows_downloaded": 30,
                "provider_row_count": 30,
                "rows_mapped": 0,
                "zero_row_observability": [{"zero_row_marker": "response_parsed_but_zero_rows_mapped"}],
            },
        ):
            processed = sync_worker.process_next_chunk()

        self.assertTrue(processed)
        self.assertEqual(state["run"]["status"], "error")
        self.assertEqual(len(metadata_calls), 1)
        self.assertNotIn("backfill_completed_through", metadata_calls[0])
        self.assertNotIn("last_success_at", metadata_calls[0])
        self.assertIn("parser_failure", str(metadata_calls[0].get("last_error") or ""))
        run_metadata = state["run"].get("metadata") or {}
        self.assertTrue(bool(run_metadata.get("parser_failure")))

    def test_tiktok_historical_empty_success_does_not_advance_backfill_coverage(self):
        state = self._build_state(job_type="historical_backfill", platform="tiktok_ads")

        metadata_calls = []
        cleanup_calls = []

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
            if isinstance(kwargs.get("metadata"), dict):
                existing = state["run"].get("metadata") if isinstance(state["run"].get("metadata"), dict) else {}
                merged = dict(existing)
                merged.update(kwargs.get("metadata") or {})
                state["run"]["metadata"] = merged
            return dict(state["run"])

        def _update_chunk_status(**kwargs):
            state["chunk"]["status"] = kwargs["status"]
            if kwargs.get("metadata") is not None:
                state["chunk"]["metadata"] = kwargs.get("metadata") or {}
            return dict(state["chunk"])

        def _update_progress(**kwargs):
            state["run"]["chunks_done"] = int(state["run"].get("chunks_done") or 0) + int(kwargs.get("chunks_done_delta") or 0)
            state["run"]["rows_written"] = int(state["run"].get("rows_written") or 0) + int(kwargs.get("rows_written_delta") or 0)
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
            sync_worker.sync_run_chunks_store,
            "list_sync_run_chunks",
            return_value=[
                {
                    "chunk_index": 0,
                    "status": "done",
                    "metadata": {
                        "rows_downloaded": 0,
                        "rows_mapped": 0,
                        "zero_row_observability": [{"zero_row_marker": "provider_returned_empty_list"}],
                    },
                }
            ],
        ), patch.object(
            sync_worker.client_registry_service,
            "update_platform_account_operational_metadata",
            side_effect=lambda **kwargs: metadata_calls.append(kwargs) or kwargs,
        ), patch.object(
            sync_worker.tiktok_ads_service,
            "sync_client",
            return_value={
                "rows_written": 0,
                "rows_downloaded": 0,
                "provider_row_count": 0,
                "rows_mapped": 0,
                "zero_row_observability": [{"zero_row_marker": "provider_returned_empty_list"}],
            },
        ), patch.object(
            sync_worker.sync_runs_store,
            "cleanup_superseded_tiktok_failed_runs",
            side_effect=lambda **kwargs: cleanup_calls.append(kwargs) or {"deleted_runs": 0, "deleted_chunks": 0, "superseded_run_count": 0},
        ):
            processed = sync_worker.process_next_chunk()

        self.assertTrue(processed)
        self.assertEqual(state["run"]["status"], "done")
        self.assertEqual(len(metadata_calls), 1)
        self.assertNotIn("backfill_completed_through", metadata_calls[0])
        run_metadata = state["run"].get("metadata") or {}
        self.assertTrue(bool(run_metadata.get("no_data_success")))
        self.assertEqual(run_metadata.get("zero_row_marker"), "provider_returned_empty_list")
        self.assertEqual(cleanup_calls, [{"account_ids": ["3986597205"]}])



    def test_tiktok_historical_parser_failure_marks_run_error_and_does_not_advance_backfill(self):
        state = self._build_state(job_type="historical_backfill", platform="tiktok_ads")

        metadata_calls = []

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
                state["run"]["error"] = kwargs.get("error")
            if isinstance(kwargs.get("metadata"), dict):
                existing = state["run"].get("metadata") if isinstance(state["run"].get("metadata"), dict) else {}
                merged = dict(existing)
                merged.update(kwargs.get("metadata") or {})
                state["run"]["metadata"] = merged
            return dict(state["run"])

        def _update_chunk_status(**kwargs):
            state["chunk"]["status"] = kwargs["status"]
            if kwargs.get("metadata") is not None:
                state["chunk"]["metadata"] = kwargs.get("metadata") or {}
            return dict(state["chunk"])

        def _update_progress(**kwargs):
            state["run"]["chunks_done"] = int(state["run"].get("chunks_done") or 0) + int(kwargs.get("chunks_done_delta") or 0)
            state["run"]["rows_written"] = int(state["run"].get("rows_written") or 0) + int(kwargs.get("rows_written_delta") or 0)
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
            sync_worker.sync_run_chunks_store,
            "list_sync_run_chunks",
            return_value=[
                {
                    "chunk_index": 0,
                    "status": "done",
                    "metadata": {
                        "rows_downloaded": 30,
                        "rows_mapped": 0,
                        "zero_row_observability": [{"zero_row_marker": "response_parsed_but_zero_rows_mapped"}],
                    },
                }
            ],
        ), patch.object(
            sync_worker.client_registry_service,
            "update_platform_account_operational_metadata",
            side_effect=lambda **kwargs: metadata_calls.append(kwargs) or kwargs,
        ), patch.object(
            sync_worker.tiktok_ads_service,
            "sync_client",
            return_value={
                "rows_written": 0,
                "rows_downloaded": 30,
                "provider_row_count": 30,
                "rows_mapped": 0,
                "zero_row_observability": [{"zero_row_marker": "response_parsed_but_zero_rows_mapped"}],
            },
        ):
            processed = sync_worker.process_next_chunk()

        self.assertTrue(processed)
        self.assertEqual(state["run"]["status"], "error")
        self.assertEqual(len(metadata_calls), 1)
        self.assertNotIn("backfill_completed_through", metadata_calls[0])
        self.assertNotIn("last_success_at", metadata_calls[0])
        self.assertIn("parser_failure", str(metadata_calls[0].get("last_error") or ""))
        run_metadata = state["run"].get("metadata") or {}
        self.assertTrue(bool(run_metadata.get("parser_failure")))

    def test_tiktok_historical_empty_success_does_not_advance_backfill_coverage(self):
        state = self._build_state(job_type="historical_backfill", platform="tiktok_ads")

        metadata_calls = []
        cleanup_calls = []

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
            if isinstance(kwargs.get("metadata"), dict):
                existing = state["run"].get("metadata") if isinstance(state["run"].get("metadata"), dict) else {}
                merged = dict(existing)
                merged.update(kwargs.get("metadata") or {})
                state["run"]["metadata"] = merged
            return dict(state["run"])

        def _update_chunk_status(**kwargs):
            state["chunk"]["status"] = kwargs["status"]
            if kwargs.get("metadata") is not None:
                state["chunk"]["metadata"] = kwargs.get("metadata") or {}
            return dict(state["chunk"])

        def _update_progress(**kwargs):
            state["run"]["chunks_done"] = int(state["run"].get("chunks_done") or 0) + int(kwargs.get("chunks_done_delta") or 0)
            state["run"]["rows_written"] = int(state["run"].get("rows_written") or 0) + int(kwargs.get("rows_written_delta") or 0)
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
            sync_worker.sync_run_chunks_store,
            "list_sync_run_chunks",
            return_value=[
                {
                    "chunk_index": 0,
                    "status": "done",
                    "metadata": {
                        "rows_downloaded": 0,
                        "rows_mapped": 0,
                        "zero_row_observability": [{"zero_row_marker": "provider_returned_empty_list"}],
                    },
                }
            ],
        ), patch.object(
            sync_worker.client_registry_service,
            "update_platform_account_operational_metadata",
            side_effect=lambda **kwargs: metadata_calls.append(kwargs) or kwargs,
        ), patch.object(
            sync_worker.tiktok_ads_service,
            "sync_client",
            return_value={
                "rows_written": 0,
                "rows_downloaded": 0,
                "provider_row_count": 0,
                "rows_mapped": 0,
                "zero_row_observability": [{"zero_row_marker": "provider_returned_empty_list"}],
            },
        ), patch.object(
            sync_worker.sync_runs_store,
            "cleanup_superseded_tiktok_failed_runs",
            side_effect=lambda **kwargs: cleanup_calls.append(kwargs) or {"deleted_runs": 0, "deleted_chunks": 0, "superseded_run_count": 0},
        ):
            processed = sync_worker.process_next_chunk()

        self.assertTrue(processed)
        self.assertEqual(state["run"]["status"], "done")
        self.assertEqual(len(metadata_calls), 1)
        self.assertNotIn("backfill_completed_through", metadata_calls[0])
        run_metadata = state["run"].get("metadata") or {}
        self.assertTrue(bool(run_metadata.get("no_data_success")))
        self.assertEqual(run_metadata.get("zero_row_marker"), "provider_returned_empty_list")
        self.assertEqual(cleanup_calls, [{"account_ids": ["3986597205"]}])



    def test_tiktok_historical_parser_failure_marks_run_error_and_does_not_advance_backfill(self):
        state = self._build_state(job_type="historical_backfill", platform="tiktok_ads")

        metadata_calls = []

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
                state["run"]["error"] = kwargs.get("error")
            if isinstance(kwargs.get("metadata"), dict):
                existing = state["run"].get("metadata") if isinstance(state["run"].get("metadata"), dict) else {}
                merged = dict(existing)
                merged.update(kwargs.get("metadata") or {})
                state["run"]["metadata"] = merged
            return dict(state["run"])

        def _update_chunk_status(**kwargs):
            state["chunk"]["status"] = kwargs["status"]
            if kwargs.get("metadata") is not None:
                state["chunk"]["metadata"] = kwargs.get("metadata") or {}
            return dict(state["chunk"])

        def _update_progress(**kwargs):
            state["run"]["chunks_done"] = int(state["run"].get("chunks_done") or 0) + int(kwargs.get("chunks_done_delta") or 0)
            state["run"]["rows_written"] = int(state["run"].get("rows_written") or 0) + int(kwargs.get("rows_written_delta") or 0)
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
            sync_worker.sync_run_chunks_store,
            "list_sync_run_chunks",
            return_value=[
                {
                    "chunk_index": 0,
                    "status": "done",
                    "metadata": {
                        "rows_downloaded": 30,
                        "rows_mapped": 0,
                        "zero_row_observability": [{"zero_row_marker": "response_parsed_but_zero_rows_mapped"}],
                    },
                }
            ],
        ), patch.object(
            sync_worker.client_registry_service,
            "update_platform_account_operational_metadata",
            side_effect=lambda **kwargs: metadata_calls.append(kwargs) or kwargs,
        ), patch.object(
            sync_worker.tiktok_ads_service,
            "sync_client",
            return_value={
                "rows_written": 0,
                "rows_downloaded": 30,
                "provider_row_count": 30,
                "rows_mapped": 0,
                "zero_row_observability": [{"zero_row_marker": "response_parsed_but_zero_rows_mapped"}],
            },
        ):
            processed = sync_worker.process_next_chunk()

        self.assertTrue(processed)
        self.assertEqual(state["run"]["status"], "error")
        self.assertEqual(len(metadata_calls), 1)
        self.assertNotIn("backfill_completed_through", metadata_calls[0])
        self.assertNotIn("last_success_at", metadata_calls[0])
        self.assertIn("parser_failure", str(metadata_calls[0].get("last_error") or ""))
        run_metadata = state["run"].get("metadata") or {}
        self.assertTrue(bool(run_metadata.get("parser_failure")))

    def test_tiktok_historical_empty_success_does_not_advance_backfill_coverage(self):
        state = self._build_state(job_type="historical_backfill", platform="tiktok_ads")

        metadata_calls = []
        cleanup_calls = []

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
            if isinstance(kwargs.get("metadata"), dict):
                existing = state["run"].get("metadata") if isinstance(state["run"].get("metadata"), dict) else {}
                merged = dict(existing)
                merged.update(kwargs.get("metadata") or {})
                state["run"]["metadata"] = merged
            return dict(state["run"])

        def _update_chunk_status(**kwargs):
            state["chunk"]["status"] = kwargs["status"]
            if kwargs.get("metadata") is not None:
                state["chunk"]["metadata"] = kwargs.get("metadata") or {}
            return dict(state["chunk"])

        def _update_progress(**kwargs):
            state["run"]["chunks_done"] = int(state["run"].get("chunks_done") or 0) + int(kwargs.get("chunks_done_delta") or 0)
            state["run"]["rows_written"] = int(state["run"].get("rows_written") or 0) + int(kwargs.get("rows_written_delta") or 0)
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
            sync_worker.sync_run_chunks_store,
            "list_sync_run_chunks",
            return_value=[
                {
                    "chunk_index": 0,
                    "status": "done",
                    "metadata": {
                        "rows_downloaded": 0,
                        "rows_mapped": 0,
                        "zero_row_observability": [{"zero_row_marker": "provider_returned_empty_list"}],
                    },
                }
            ],
        ), patch.object(
            sync_worker.client_registry_service,
            "update_platform_account_operational_metadata",
            side_effect=lambda **kwargs: metadata_calls.append(kwargs) or kwargs,
        ), patch.object(
            sync_worker.tiktok_ads_service,
            "sync_client",
            return_value={
                "rows_written": 0,
                "rows_downloaded": 0,
                "provider_row_count": 0,
                "rows_mapped": 0,
                "zero_row_observability": [{"zero_row_marker": "provider_returned_empty_list"}],
            },
        ), patch.object(
            sync_worker.sync_runs_store,
            "cleanup_superseded_tiktok_failed_runs",
            side_effect=lambda **kwargs: cleanup_calls.append(kwargs) or {"deleted_runs": 0, "deleted_chunks": 0, "superseded_run_count": 0},
        ):
            processed = sync_worker.process_next_chunk()

        self.assertTrue(processed)
        self.assertEqual(state["run"]["status"], "done")
        self.assertEqual(len(metadata_calls), 1)
        self.assertNotIn("backfill_completed_through", metadata_calls[0])
        run_metadata = state["run"].get("metadata") or {}
        self.assertTrue(bool(run_metadata.get("no_data_success")))
        self.assertEqual(run_metadata.get("zero_row_marker"), "provider_returned_empty_list")
        self.assertEqual(cleanup_calls, [{"account_ids": ["3986597205"]}])



    def test_tiktok_historical_parser_failure_marks_run_error_and_does_not_advance_backfill(self):
        state = self._build_state(job_type="historical_backfill", platform="tiktok_ads")

        metadata_calls = []

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
                state["run"]["error"] = kwargs.get("error")
            if isinstance(kwargs.get("metadata"), dict):
                existing = state["run"].get("metadata") if isinstance(state["run"].get("metadata"), dict) else {}
                merged = dict(existing)
                merged.update(kwargs.get("metadata") or {})
                state["run"]["metadata"] = merged
            return dict(state["run"])

        def _update_chunk_status(**kwargs):
            state["chunk"]["status"] = kwargs["status"]
            if kwargs.get("metadata") is not None:
                state["chunk"]["metadata"] = kwargs.get("metadata") or {}
            return dict(state["chunk"])

        def _update_progress(**kwargs):
            state["run"]["chunks_done"] = int(state["run"].get("chunks_done") or 0) + int(kwargs.get("chunks_done_delta") or 0)
            state["run"]["rows_written"] = int(state["run"].get("rows_written") or 0) + int(kwargs.get("rows_written_delta") or 0)
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
            sync_worker.sync_run_chunks_store,
            "list_sync_run_chunks",
            return_value=[
                {
                    "chunk_index": 0,
                    "status": "done",
                    "metadata": {
                        "rows_downloaded": 30,
                        "rows_mapped": 0,
                        "zero_row_observability": [{"zero_row_marker": "response_parsed_but_zero_rows_mapped"}],
                    },
                }
            ],
        ), patch.object(
            sync_worker.client_registry_service,
            "update_platform_account_operational_metadata",
            side_effect=lambda **kwargs: metadata_calls.append(kwargs) or kwargs,
        ), patch.object(
            sync_worker.tiktok_ads_service,
            "sync_client",
            return_value={
                "rows_written": 0,
                "rows_downloaded": 30,
                "provider_row_count": 30,
                "rows_mapped": 0,
                "zero_row_observability": [{"zero_row_marker": "response_parsed_but_zero_rows_mapped"}],
            },
        ):
            processed = sync_worker.process_next_chunk()

        self.assertTrue(processed)
        self.assertEqual(state["run"]["status"], "error")
        self.assertEqual(len(metadata_calls), 1)
        self.assertNotIn("backfill_completed_through", metadata_calls[0])
        self.assertNotIn("last_success_at", metadata_calls[0])
        self.assertIn("parser_failure", str(metadata_calls[0].get("last_error") or ""))
        run_metadata = state["run"].get("metadata") or {}
        self.assertTrue(bool(run_metadata.get("parser_failure")))

    def test_tiktok_historical_empty_success_does_not_advance_backfill_coverage(self):
        state = self._build_state(job_type="historical_backfill", platform="tiktok_ads")

        metadata_calls = []
        cleanup_calls = []

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
            if isinstance(kwargs.get("metadata"), dict):
                existing = state["run"].get("metadata") if isinstance(state["run"].get("metadata"), dict) else {}
                merged = dict(existing)
                merged.update(kwargs.get("metadata") or {})
                state["run"]["metadata"] = merged
            return dict(state["run"])

        def _update_chunk_status(**kwargs):
            state["chunk"]["status"] = kwargs["status"]
            if kwargs.get("metadata") is not None:
                state["chunk"]["metadata"] = kwargs.get("metadata") or {}
            return dict(state["chunk"])

        def _update_progress(**kwargs):
            state["run"]["chunks_done"] = int(state["run"].get("chunks_done") or 0) + int(kwargs.get("chunks_done_delta") or 0)
            state["run"]["rows_written"] = int(state["run"].get("rows_written") or 0) + int(kwargs.get("rows_written_delta") or 0)
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
            sync_worker.sync_run_chunks_store,
            "list_sync_run_chunks",
            return_value=[
                {
                    "chunk_index": 0,
                    "status": "done",
                    "metadata": {
                        "rows_downloaded": 0,
                        "rows_mapped": 0,
                        "zero_row_observability": [{"zero_row_marker": "provider_returned_empty_list"}],
                    },
                }
            ],
        ), patch.object(
            sync_worker.client_registry_service,
            "update_platform_account_operational_metadata",
            side_effect=lambda **kwargs: metadata_calls.append(kwargs) or kwargs,
        ), patch.object(
            sync_worker.tiktok_ads_service,
            "sync_client",
            return_value={
                "rows_written": 0,
                "rows_downloaded": 0,
                "provider_row_count": 0,
                "rows_mapped": 0,
                "zero_row_observability": [{"zero_row_marker": "provider_returned_empty_list"}],
            },
        ), patch.object(
            sync_worker.sync_runs_store,
            "cleanup_superseded_tiktok_failed_runs",
            side_effect=lambda **kwargs: cleanup_calls.append(kwargs) or {"deleted_runs": 0, "deleted_chunks": 0, "superseded_run_count": 0},
        ):
            processed = sync_worker.process_next_chunk()

        self.assertTrue(processed)
        self.assertEqual(state["run"]["status"], "done")
        self.assertEqual(len(metadata_calls), 1)
        self.assertNotIn("backfill_completed_through", metadata_calls[0])
        run_metadata = state["run"].get("metadata") or {}
        self.assertTrue(bool(run_metadata.get("no_data_success")))
        self.assertEqual(run_metadata.get("zero_row_marker"), "provider_returned_empty_list")
        self.assertEqual(cleanup_calls, [{"account_ids": ["3986597205"]}])



    def test_tiktok_historical_parser_failure_marks_run_error_and_does_not_advance_backfill(self):
        state = self._build_state(job_type="historical_backfill", platform="tiktok_ads")

        metadata_calls = []

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
                state["run"]["error"] = kwargs.get("error")
            if isinstance(kwargs.get("metadata"), dict):
                existing = state["run"].get("metadata") if isinstance(state["run"].get("metadata"), dict) else {}
                merged = dict(existing)
                merged.update(kwargs.get("metadata") or {})
                state["run"]["metadata"] = merged
            return dict(state["run"])

        def _update_chunk_status(**kwargs):
            state["chunk"]["status"] = kwargs["status"]
            if kwargs.get("metadata") is not None:
                state["chunk"]["metadata"] = kwargs.get("metadata") or {}
            return dict(state["chunk"])

        def _update_progress(**kwargs):
            state["run"]["chunks_done"] = int(state["run"].get("chunks_done") or 0) + int(kwargs.get("chunks_done_delta") or 0)
            state["run"]["rows_written"] = int(state["run"].get("rows_written") or 0) + int(kwargs.get("rows_written_delta") or 0)
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
            sync_worker.sync_run_chunks_store,
            "list_sync_run_chunks",
            return_value=[
                {
                    "chunk_index": 0,
                    "status": "done",
                    "metadata": {
                        "rows_downloaded": 30,
                        "rows_mapped": 0,
                        "zero_row_observability": [{"zero_row_marker": "response_parsed_but_zero_rows_mapped"}],
                    },
                }
            ],
        ), patch.object(
            sync_worker.client_registry_service,
            "update_platform_account_operational_metadata",
            side_effect=lambda **kwargs: metadata_calls.append(kwargs) or kwargs,
        ), patch.object(
            sync_worker.tiktok_ads_service,
            "sync_client",
            return_value={
                "rows_written": 0,
                "rows_downloaded": 30,
                "provider_row_count": 30,
                "rows_mapped": 0,
                "zero_row_observability": [{"zero_row_marker": "response_parsed_but_zero_rows_mapped"}],
            },
        ):
            processed = sync_worker.process_next_chunk()

        self.assertTrue(processed)
        self.assertEqual(state["run"]["status"], "error")
        self.assertEqual(len(metadata_calls), 1)
        self.assertNotIn("backfill_completed_through", metadata_calls[0])
        self.assertNotIn("last_success_at", metadata_calls[0])
        self.assertIn("parser_failure", str(metadata_calls[0].get("last_error") or ""))
        run_metadata = state["run"].get("metadata") or {}
        self.assertTrue(bool(run_metadata.get("parser_failure")))

    def test_tiktok_historical_empty_success_does_not_advance_backfill_coverage(self):
        state = self._build_state(job_type="historical_backfill", platform="tiktok_ads")

        metadata_calls = []
        cleanup_calls = []

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
            if isinstance(kwargs.get("metadata"), dict):
                existing = state["run"].get("metadata") if isinstance(state["run"].get("metadata"), dict) else {}
                merged = dict(existing)
                merged.update(kwargs.get("metadata") or {})
                state["run"]["metadata"] = merged
            return dict(state["run"])

        def _update_chunk_status(**kwargs):
            state["chunk"]["status"] = kwargs["status"]
            if kwargs.get("metadata") is not None:
                state["chunk"]["metadata"] = kwargs.get("metadata") or {}
            return dict(state["chunk"])

        def _update_progress(**kwargs):
            state["run"]["chunks_done"] = int(state["run"].get("chunks_done") or 0) + int(kwargs.get("chunks_done_delta") or 0)
            state["run"]["rows_written"] = int(state["run"].get("rows_written") or 0) + int(kwargs.get("rows_written_delta") or 0)
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
            sync_worker.sync_run_chunks_store,
            "list_sync_run_chunks",
            return_value=[
                {
                    "chunk_index": 0,
                    "status": "done",
                    "metadata": {
                        "rows_downloaded": 0,
                        "rows_mapped": 0,
                        "zero_row_observability": [{"zero_row_marker": "provider_returned_empty_list"}],
                    },
                }
            ],
        ), patch.object(
            sync_worker.client_registry_service,
            "update_platform_account_operational_metadata",
            side_effect=lambda **kwargs: metadata_calls.append(kwargs) or kwargs,
        ), patch.object(
            sync_worker.tiktok_ads_service,
            "sync_client",
            return_value={
                "rows_written": 0,
                "rows_downloaded": 0,
                "provider_row_count": 0,
                "rows_mapped": 0,
                "zero_row_observability": [{"zero_row_marker": "provider_returned_empty_list"}],
            },
        ), patch.object(
            sync_worker.sync_runs_store,
            "cleanup_superseded_tiktok_failed_runs",
            side_effect=lambda **kwargs: cleanup_calls.append(kwargs) or {"deleted_runs": 0, "deleted_chunks": 0, "superseded_run_count": 0},
        ):
            processed = sync_worker.process_next_chunk()

        self.assertTrue(processed)
        self.assertEqual(state["run"]["status"], "done")
        self.assertEqual(len(metadata_calls), 1)
        self.assertNotIn("backfill_completed_through", metadata_calls[0])
        run_metadata = state["run"].get("metadata") or {}
        self.assertTrue(bool(run_metadata.get("no_data_success")))
        self.assertEqual(run_metadata.get("zero_row_marker"), "provider_returned_empty_list")
        self.assertEqual(cleanup_calls, [{"account_ids": ["3986597205"]}])



    def test_tiktok_historical_parser_failure_marks_run_error_and_does_not_advance_backfill(self):
        state = self._build_state(job_type="historical_backfill", platform="tiktok_ads")

        metadata_calls = []

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
                state["run"]["error"] = kwargs.get("error")
            if isinstance(kwargs.get("metadata"), dict):
                existing = state["run"].get("metadata") if isinstance(state["run"].get("metadata"), dict) else {}
                merged = dict(existing)
                merged.update(kwargs.get("metadata") or {})
                state["run"]["metadata"] = merged
            return dict(state["run"])

        def _update_chunk_status(**kwargs):
            state["chunk"]["status"] = kwargs["status"]
            if kwargs.get("metadata") is not None:
                state["chunk"]["metadata"] = kwargs.get("metadata") or {}
            return dict(state["chunk"])

        def _update_progress(**kwargs):
            state["run"]["chunks_done"] = int(state["run"].get("chunks_done") or 0) + int(kwargs.get("chunks_done_delta") or 0)
            state["run"]["rows_written"] = int(state["run"].get("rows_written") or 0) + int(kwargs.get("rows_written_delta") or 0)
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
            sync_worker.sync_run_chunks_store,
            "list_sync_run_chunks",
            return_value=[
                {
                    "chunk_index": 0,
                    "status": "done",
                    "metadata": {
                        "rows_downloaded": 30,
                        "rows_mapped": 0,
                        "zero_row_observability": [{"zero_row_marker": "response_parsed_but_zero_rows_mapped"}],
                    },
                }
            ],
        ), patch.object(
            sync_worker.client_registry_service,
            "update_platform_account_operational_metadata",
            side_effect=lambda **kwargs: metadata_calls.append(kwargs) or kwargs,
        ), patch.object(
            sync_worker.tiktok_ads_service,
            "sync_client",
            return_value={
                "rows_written": 0,
                "rows_downloaded": 30,
                "provider_row_count": 30,
                "rows_mapped": 0,
                "zero_row_observability": [{"zero_row_marker": "response_parsed_but_zero_rows_mapped"}],
            },
        ):
            processed = sync_worker.process_next_chunk()

        self.assertTrue(processed)
        self.assertEqual(state["run"]["status"], "error")
        self.assertEqual(len(metadata_calls), 1)
        self.assertNotIn("backfill_completed_through", metadata_calls[0])
        self.assertNotIn("last_success_at", metadata_calls[0])
        self.assertIn("parser_failure", str(metadata_calls[0].get("last_error") or ""))
        run_metadata = state["run"].get("metadata") or {}
        self.assertTrue(bool(run_metadata.get("parser_failure")))

    def test_tiktok_historical_empty_success_does_not_advance_backfill_coverage(self):
        state = self._build_state(job_type="historical_backfill", platform="tiktok_ads")

        metadata_calls = []
        cleanup_calls = []

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
            if isinstance(kwargs.get("metadata"), dict):
                existing = state["run"].get("metadata") if isinstance(state["run"].get("metadata"), dict) else {}
                merged = dict(existing)
                merged.update(kwargs.get("metadata") or {})
                state["run"]["metadata"] = merged
            return dict(state["run"])

        def _update_chunk_status(**kwargs):
            state["chunk"]["status"] = kwargs["status"]
            if kwargs.get("metadata") is not None:
                state["chunk"]["metadata"] = kwargs.get("metadata") or {}
            return dict(state["chunk"])

        def _update_progress(**kwargs):
            state["run"]["chunks_done"] = int(state["run"].get("chunks_done") or 0) + int(kwargs.get("chunks_done_delta") or 0)
            state["run"]["rows_written"] = int(state["run"].get("rows_written") or 0) + int(kwargs.get("rows_written_delta") or 0)
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
            sync_worker.sync_run_chunks_store,
            "list_sync_run_chunks",
            return_value=[
                {
                    "chunk_index": 0,
                    "status": "done",
                    "metadata": {
                        "rows_downloaded": 0,
                        "rows_mapped": 0,
                        "zero_row_observability": [{"zero_row_marker": "provider_returned_empty_list"}],
                    },
                }
            ],
        ), patch.object(
            sync_worker.client_registry_service,
            "update_platform_account_operational_metadata",
            side_effect=lambda **kwargs: metadata_calls.append(kwargs) or kwargs,
        ), patch.object(
            sync_worker.tiktok_ads_service,
            "sync_client",
            return_value={
                "rows_written": 0,
                "rows_downloaded": 0,
                "provider_row_count": 0,
                "rows_mapped": 0,
                "zero_row_observability": [{"zero_row_marker": "provider_returned_empty_list"}],
            },
        ), patch.object(
            sync_worker.sync_runs_store,
            "cleanup_superseded_tiktok_failed_runs",
            side_effect=lambda **kwargs: cleanup_calls.append(kwargs) or {"deleted_runs": 0, "deleted_chunks": 0, "superseded_run_count": 0},
        ):
            processed = sync_worker.process_next_chunk()

        self.assertTrue(processed)
        self.assertEqual(state["run"]["status"], "done")
        self.assertEqual(len(metadata_calls), 1)
        self.assertNotIn("backfill_completed_through", metadata_calls[0])
        run_metadata = state["run"].get("metadata") or {}
        self.assertTrue(bool(run_metadata.get("no_data_success")))
        self.assertEqual(run_metadata.get("zero_row_marker"), "provider_returned_empty_list")
        self.assertEqual(cleanup_calls, [{"account_ids": ["3986597205"]}])



    def test_tiktok_historical_parser_failure_marks_run_error_and_does_not_advance_backfill(self):
        state = self._build_state(job_type="historical_backfill", platform="tiktok_ads")

        metadata_calls = []

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
                state["run"]["error"] = kwargs.get("error")
            if isinstance(kwargs.get("metadata"), dict):
                existing = state["run"].get("metadata") if isinstance(state["run"].get("metadata"), dict) else {}
                merged = dict(existing)
                merged.update(kwargs.get("metadata") or {})
                state["run"]["metadata"] = merged
            return dict(state["run"])

        def _update_chunk_status(**kwargs):
            state["chunk"]["status"] = kwargs["status"]
            if kwargs.get("metadata") is not None:
                state["chunk"]["metadata"] = kwargs.get("metadata") or {}
            return dict(state["chunk"])

        def _update_progress(**kwargs):
            state["run"]["chunks_done"] = int(state["run"].get("chunks_done") or 0) + int(kwargs.get("chunks_done_delta") or 0)
            state["run"]["rows_written"] = int(state["run"].get("rows_written") or 0) + int(kwargs.get("rows_written_delta") or 0)
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
            sync_worker.sync_run_chunks_store,
            "list_sync_run_chunks",
            return_value=[
                {
                    "chunk_index": 0,
                    "status": "done",
                    "metadata": {
                        "rows_downloaded": 30,
                        "rows_mapped": 0,
                        "zero_row_observability": [{"zero_row_marker": "response_parsed_but_zero_rows_mapped"}],
                    },
                }
            ],
        ), patch.object(
            sync_worker.client_registry_service,
            "update_platform_account_operational_metadata",
            side_effect=lambda **kwargs: metadata_calls.append(kwargs) or kwargs,
        ), patch.object(
            sync_worker.tiktok_ads_service,
            "sync_client",
            return_value={
                "rows_written": 0,
                "rows_downloaded": 30,
                "provider_row_count": 30,
                "rows_mapped": 0,
                "zero_row_observability": [{"zero_row_marker": "response_parsed_but_zero_rows_mapped"}],
            },
        ):
            processed = sync_worker.process_next_chunk()

        self.assertTrue(processed)
        self.assertEqual(state["run"]["status"], "error")
        self.assertEqual(len(metadata_calls), 1)
        self.assertNotIn("backfill_completed_through", metadata_calls[0])
        self.assertNotIn("last_success_at", metadata_calls[0])
        self.assertIn("parser_failure", str(metadata_calls[0].get("last_error") or ""))
        run_metadata = state["run"].get("metadata") or {}
        self.assertTrue(bool(run_metadata.get("parser_failure")))

    def test_tiktok_historical_empty_success_does_not_advance_backfill_coverage(self):
        state = self._build_state(job_type="historical_backfill", platform="tiktok_ads")

        metadata_calls = []
        cleanup_calls = []

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
            if isinstance(kwargs.get("metadata"), dict):
                existing = state["run"].get("metadata") if isinstance(state["run"].get("metadata"), dict) else {}
                merged = dict(existing)
                merged.update(kwargs.get("metadata") or {})
                state["run"]["metadata"] = merged
            return dict(state["run"])

        def _update_chunk_status(**kwargs):
            state["chunk"]["status"] = kwargs["status"]
            if kwargs.get("metadata") is not None:
                state["chunk"]["metadata"] = kwargs.get("metadata") or {}
            return dict(state["chunk"])

        def _update_progress(**kwargs):
            state["run"]["chunks_done"] = int(state["run"].get("chunks_done") or 0) + int(kwargs.get("chunks_done_delta") or 0)
            state["run"]["rows_written"] = int(state["run"].get("rows_written") or 0) + int(kwargs.get("rows_written_delta") or 0)
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
            sync_worker.sync_run_chunks_store,
            "list_sync_run_chunks",
            return_value=[
                {
                    "chunk_index": 0,
                    "status": "done",
                    "metadata": {
                        "rows_downloaded": 0,
                        "rows_mapped": 0,
                        "zero_row_observability": [{"zero_row_marker": "provider_returned_empty_list"}],
                    },
                }
            ],
        ), patch.object(
            sync_worker.client_registry_service,
            "update_platform_account_operational_metadata",
            side_effect=lambda **kwargs: metadata_calls.append(kwargs) or kwargs,
        ), patch.object(
            sync_worker.tiktok_ads_service,
            "sync_client",
            return_value={
                "rows_written": 0,
                "rows_downloaded": 0,
                "provider_row_count": 0,
                "rows_mapped": 0,
                "zero_row_observability": [{"zero_row_marker": "provider_returned_empty_list"}],
            },
        ), patch.object(
            sync_worker.sync_runs_store,
            "cleanup_superseded_tiktok_failed_runs",
            side_effect=lambda **kwargs: cleanup_calls.append(kwargs) or {"deleted_runs": 0, "deleted_chunks": 0, "superseded_run_count": 0},
        ):
            processed = sync_worker.process_next_chunk()

        self.assertTrue(processed)
        self.assertEqual(state["run"]["status"], "done")
        self.assertEqual(len(metadata_calls), 1)
        self.assertNotIn("backfill_completed_through", metadata_calls[0])
        run_metadata = state["run"].get("metadata") or {}
        self.assertTrue(bool(run_metadata.get("no_data_success")))
        self.assertEqual(run_metadata.get("zero_row_marker"), "provider_returned_empty_list")
        self.assertEqual(cleanup_calls, [{"account_ids": ["3986597205"]}])



    def test_tiktok_historical_parser_failure_marks_run_error_and_does_not_advance_backfill(self):
        state = self._build_state(job_type="historical_backfill", platform="tiktok_ads")

        metadata_calls = []

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
                state["run"]["error"] = kwargs.get("error")
            if isinstance(kwargs.get("metadata"), dict):
                existing = state["run"].get("metadata") if isinstance(state["run"].get("metadata"), dict) else {}
                merged = dict(existing)
                merged.update(kwargs.get("metadata") or {})
                state["run"]["metadata"] = merged
            return dict(state["run"])

        def _update_chunk_status(**kwargs):
            state["chunk"]["status"] = kwargs["status"]
            if kwargs.get("metadata") is not None:
                state["chunk"]["metadata"] = kwargs.get("metadata") or {}
            return dict(state["chunk"])

        def _update_progress(**kwargs):
            state["run"]["chunks_done"] = int(state["run"].get("chunks_done") or 0) + int(kwargs.get("chunks_done_delta") or 0)
            state["run"]["rows_written"] = int(state["run"].get("rows_written") or 0) + int(kwargs.get("rows_written_delta") or 0)
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
            sync_worker.sync_run_chunks_store,
            "list_sync_run_chunks",
            return_value=[
                {
                    "chunk_index": 0,
                    "status": "done",
                    "metadata": {
                        "rows_downloaded": 30,
                        "rows_mapped": 0,
                        "zero_row_observability": [{"zero_row_marker": "response_parsed_but_zero_rows_mapped"}],
                    },
                }
            ],
        ), patch.object(
            sync_worker.client_registry_service,
            "update_platform_account_operational_metadata",
            side_effect=lambda **kwargs: metadata_calls.append(kwargs) or kwargs,
        ), patch.object(
            sync_worker.tiktok_ads_service,
            "sync_client",
            return_value={
                "rows_written": 0,
                "rows_downloaded": 30,
                "provider_row_count": 30,
                "rows_mapped": 0,
                "zero_row_observability": [{"zero_row_marker": "response_parsed_but_zero_rows_mapped"}],
            },
        ):
            processed = sync_worker.process_next_chunk()

        self.assertTrue(processed)
        self.assertEqual(state["run"]["status"], "error")
        self.assertEqual(len(metadata_calls), 1)
        self.assertNotIn("backfill_completed_through", metadata_calls[0])
        self.assertNotIn("last_success_at", metadata_calls[0])
        self.assertIn("parser_failure", str(metadata_calls[0].get("last_error") or ""))
        run_metadata = state["run"].get("metadata") or {}
        self.assertTrue(bool(run_metadata.get("parser_failure")))

    def test_tiktok_historical_empty_success_does_not_advance_backfill_coverage(self):
        state = self._build_state(job_type="historical_backfill", platform="tiktok_ads")

        metadata_calls = []
        cleanup_calls = []

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
            if isinstance(kwargs.get("metadata"), dict):
                existing = state["run"].get("metadata") if isinstance(state["run"].get("metadata"), dict) else {}
                merged = dict(existing)
                merged.update(kwargs.get("metadata") or {})
                state["run"]["metadata"] = merged
            return dict(state["run"])

        def _update_chunk_status(**kwargs):
            state["chunk"]["status"] = kwargs["status"]
            if kwargs.get("metadata") is not None:
                state["chunk"]["metadata"] = kwargs.get("metadata") or {}
            return dict(state["chunk"])

        def _update_progress(**kwargs):
            state["run"]["chunks_done"] = int(state["run"].get("chunks_done") or 0) + int(kwargs.get("chunks_done_delta") or 0)
            state["run"]["rows_written"] = int(state["run"].get("rows_written") or 0) + int(kwargs.get("rows_written_delta") or 0)
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
            sync_worker.sync_run_chunks_store,
            "list_sync_run_chunks",
            return_value=[
                {
                    "chunk_index": 0,
                    "status": "done",
                    "metadata": {
                        "rows_downloaded": 0,
                        "rows_mapped": 0,
                        "zero_row_observability": [{"zero_row_marker": "provider_returned_empty_list"}],
                    },
                }
            ],
        ), patch.object(
            sync_worker.client_registry_service,
            "update_platform_account_operational_metadata",
            side_effect=lambda **kwargs: metadata_calls.append(kwargs) or kwargs,
        ), patch.object(
            sync_worker.tiktok_ads_service,
            "sync_client",
            return_value={
                "rows_written": 0,
                "rows_downloaded": 0,
                "provider_row_count": 0,
                "rows_mapped": 0,
                "zero_row_observability": [{"zero_row_marker": "provider_returned_empty_list"}],
            },
        ), patch.object(
            sync_worker.sync_runs_store,
            "cleanup_superseded_tiktok_failed_runs",
            side_effect=lambda **kwargs: cleanup_calls.append(kwargs) or {"deleted_runs": 0, "deleted_chunks": 0, "superseded_run_count": 0},
        ):
            processed = sync_worker.process_next_chunk()

        self.assertTrue(processed)
        self.assertEqual(state["run"]["status"], "done")
        self.assertEqual(len(metadata_calls), 1)
        self.assertNotIn("backfill_completed_through", metadata_calls[0])
        run_metadata = state["run"].get("metadata") or {}
        self.assertTrue(bool(run_metadata.get("no_data_success")))
        self.assertEqual(run_metadata.get("zero_row_marker"), "provider_returned_empty_list")
        self.assertEqual(cleanup_calls, [{"account_ids": ["3986597205"]}])



    def test_tiktok_historical_parser_failure_marks_run_error_and_does_not_advance_backfill(self):
        state = self._build_state(job_type="historical_backfill", platform="tiktok_ads")

        metadata_calls = []

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
                state["run"]["error"] = kwargs.get("error")
            if isinstance(kwargs.get("metadata"), dict):
                existing = state["run"].get("metadata") if isinstance(state["run"].get("metadata"), dict) else {}
                merged = dict(existing)
                merged.update(kwargs.get("metadata") or {})
                state["run"]["metadata"] = merged
            return dict(state["run"])

        def _update_chunk_status(**kwargs):
            state["chunk"]["status"] = kwargs["status"]
            if kwargs.get("metadata") is not None:
                state["chunk"]["metadata"] = kwargs.get("metadata") or {}
            return dict(state["chunk"])

        def _update_progress(**kwargs):
            state["run"]["chunks_done"] = int(state["run"].get("chunks_done") or 0) + int(kwargs.get("chunks_done_delta") or 0)
            state["run"]["rows_written"] = int(state["run"].get("rows_written") or 0) + int(kwargs.get("rows_written_delta") or 0)
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
            sync_worker.sync_run_chunks_store,
            "list_sync_run_chunks",
            return_value=[
                {
                    "chunk_index": 0,
                    "status": "done",
                    "metadata": {
                        "rows_downloaded": 30,
                        "rows_mapped": 0,
                        "zero_row_observability": [{"zero_row_marker": "response_parsed_but_zero_rows_mapped"}],
                    },
                }
            ],
        ), patch.object(
            sync_worker.client_registry_service,
            "update_platform_account_operational_metadata",
            side_effect=lambda **kwargs: metadata_calls.append(kwargs) or kwargs,
        ), patch.object(
            sync_worker.tiktok_ads_service,
            "sync_client",
            return_value={
                "rows_written": 0,
                "rows_downloaded": 30,
                "provider_row_count": 30,
                "rows_mapped": 0,
                "zero_row_observability": [{"zero_row_marker": "response_parsed_but_zero_rows_mapped"}],
            },
        ):
            processed = sync_worker.process_next_chunk()

        self.assertTrue(processed)
        self.assertEqual(state["run"]["status"], "error")
        self.assertEqual(len(metadata_calls), 1)
        self.assertNotIn("backfill_completed_through", metadata_calls[0])
        self.assertNotIn("last_success_at", metadata_calls[0])
        self.assertIn("parser_failure", str(metadata_calls[0].get("last_error") or ""))
        run_metadata = state["run"].get("metadata") or {}
        self.assertTrue(bool(run_metadata.get("parser_failure")))

    def test_tiktok_historical_empty_success_does_not_advance_backfill_coverage(self):
        state = self._build_state(job_type="historical_backfill", platform="tiktok_ads")

        metadata_calls = []
        cleanup_calls = []

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
            if isinstance(kwargs.get("metadata"), dict):
                existing = state["run"].get("metadata") if isinstance(state["run"].get("metadata"), dict) else {}
                merged = dict(existing)
                merged.update(kwargs.get("metadata") or {})
                state["run"]["metadata"] = merged
            return dict(state["run"])

        def _update_chunk_status(**kwargs):
            state["chunk"]["status"] = kwargs["status"]
            if kwargs.get("metadata") is not None:
                state["chunk"]["metadata"] = kwargs.get("metadata") or {}
            return dict(state["chunk"])

        def _update_progress(**kwargs):
            state["run"]["chunks_done"] = int(state["run"].get("chunks_done") or 0) + int(kwargs.get("chunks_done_delta") or 0)
            state["run"]["rows_written"] = int(state["run"].get("rows_written") or 0) + int(kwargs.get("rows_written_delta") or 0)
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
            sync_worker.sync_run_chunks_store,
            "list_sync_run_chunks",
            return_value=[
                {
                    "chunk_index": 0,
                    "status": "done",
                    "metadata": {
                        "rows_downloaded": 0,
                        "rows_mapped": 0,
                        "zero_row_observability": [{"zero_row_marker": "provider_returned_empty_list"}],
                    },
                }
            ],
        ), patch.object(
            sync_worker.client_registry_service,
            "update_platform_account_operational_metadata",
            side_effect=lambda **kwargs: metadata_calls.append(kwargs) or kwargs,
        ), patch.object(
            sync_worker.tiktok_ads_service,
            "sync_client",
            return_value={
                "rows_written": 0,
                "rows_downloaded": 0,
                "provider_row_count": 0,
                "rows_mapped": 0,
                "zero_row_observability": [{"zero_row_marker": "provider_returned_empty_list"}],
            },
        ), patch.object(
            sync_worker.sync_runs_store,
            "cleanup_superseded_tiktok_failed_runs",
            side_effect=lambda **kwargs: cleanup_calls.append(kwargs) or {"deleted_runs": 0, "deleted_chunks": 0, "superseded_run_count": 0},
        ):
            processed = sync_worker.process_next_chunk()

        self.assertTrue(processed)
        self.assertEqual(state["run"]["status"], "done")
        self.assertEqual(len(metadata_calls), 1)
        self.assertNotIn("backfill_completed_through", metadata_calls[0])
        run_metadata = state["run"].get("metadata") or {}
        self.assertTrue(bool(run_metadata.get("no_data_success")))
        self.assertEqual(run_metadata.get("zero_row_marker"), "provider_returned_empty_list")
        self.assertEqual(cleanup_calls, [{"account_ids": ["3986597205"]}])



    def test_tiktok_historical_parser_failure_marks_run_error_and_does_not_advance_backfill(self):
        state = self._build_state(job_type="historical_backfill", platform="tiktok_ads")

        metadata_calls = []

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
                state["run"]["error"] = kwargs.get("error")
            if isinstance(kwargs.get("metadata"), dict):
                existing = state["run"].get("metadata") if isinstance(state["run"].get("metadata"), dict) else {}
                merged = dict(existing)
                merged.update(kwargs.get("metadata") or {})
                state["run"]["metadata"] = merged
            return dict(state["run"])

        def _update_chunk_status(**kwargs):
            state["chunk"]["status"] = kwargs["status"]
            if kwargs.get("metadata") is not None:
                state["chunk"]["metadata"] = kwargs.get("metadata") or {}
            return dict(state["chunk"])

        def _update_progress(**kwargs):
            state["run"]["chunks_done"] = int(state["run"].get("chunks_done") or 0) + int(kwargs.get("chunks_done_delta") or 0)
            state["run"]["rows_written"] = int(state["run"].get("rows_written") or 0) + int(kwargs.get("rows_written_delta") or 0)
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
            sync_worker.sync_run_chunks_store,
            "list_sync_run_chunks",
            return_value=[
                {
                    "chunk_index": 0,
                    "status": "done",
                    "metadata": {
                        "rows_downloaded": 30,
                        "rows_mapped": 0,
                        "zero_row_observability": [{"zero_row_marker": "response_parsed_but_zero_rows_mapped"}],
                    },
                }
            ],
        ), patch.object(
            sync_worker.client_registry_service,
            "update_platform_account_operational_metadata",
            side_effect=lambda **kwargs: metadata_calls.append(kwargs) or kwargs,
        ), patch.object(
            sync_worker.tiktok_ads_service,
            "sync_client",
            return_value={
                "rows_written": 0,
                "rows_downloaded": 30,
                "provider_row_count": 30,
                "rows_mapped": 0,
                "zero_row_observability": [{"zero_row_marker": "response_parsed_but_zero_rows_mapped"}],
            },
        ):
            processed = sync_worker.process_next_chunk()

        self.assertTrue(processed)
        self.assertEqual(state["run"]["status"], "error")
        self.assertEqual(len(metadata_calls), 1)
        self.assertNotIn("backfill_completed_through", metadata_calls[0])
        self.assertNotIn("last_success_at", metadata_calls[0])
        self.assertIn("parser_failure", str(metadata_calls[0].get("last_error") or ""))
        run_metadata = state["run"].get("metadata") or {}
        self.assertTrue(bool(run_metadata.get("parser_failure")))

    def test_tiktok_historical_empty_success_does_not_advance_backfill_coverage(self):
        state = self._build_state(job_type="historical_backfill", platform="tiktok_ads")

        metadata_calls = []
        cleanup_calls = []

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
            if isinstance(kwargs.get("metadata"), dict):
                existing = state["run"].get("metadata") if isinstance(state["run"].get("metadata"), dict) else {}
                merged = dict(existing)
                merged.update(kwargs.get("metadata") or {})
                state["run"]["metadata"] = merged
            return dict(state["run"])

        def _update_chunk_status(**kwargs):
            state["chunk"]["status"] = kwargs["status"]
            if kwargs.get("metadata") is not None:
                state["chunk"]["metadata"] = kwargs.get("metadata") or {}
            return dict(state["chunk"])

        def _update_progress(**kwargs):
            state["run"]["chunks_done"] = int(state["run"].get("chunks_done") or 0) + int(kwargs.get("chunks_done_delta") or 0)
            state["run"]["rows_written"] = int(state["run"].get("rows_written") or 0) + int(kwargs.get("rows_written_delta") or 0)
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
            sync_worker.sync_run_chunks_store,
            "list_sync_run_chunks",
            return_value=[
                {
                    "chunk_index": 0,
                    "status": "done",
                    "metadata": {
                        "rows_downloaded": 0,
                        "rows_mapped": 0,
                        "zero_row_observability": [{"zero_row_marker": "provider_returned_empty_list"}],
                    },
                }
            ],
        ), patch.object(
            sync_worker.client_registry_service,
            "update_platform_account_operational_metadata",
            side_effect=lambda **kwargs: metadata_calls.append(kwargs) or kwargs,
        ), patch.object(
            sync_worker.tiktok_ads_service,
            "sync_client",
            return_value={
                "rows_written": 0,
                "rows_downloaded": 0,
                "provider_row_count": 0,
                "rows_mapped": 0,
                "zero_row_observability": [{"zero_row_marker": "provider_returned_empty_list"}],
            },
        ), patch.object(
            sync_worker.sync_runs_store,
            "cleanup_superseded_tiktok_failed_runs",
            side_effect=lambda **kwargs: cleanup_calls.append(kwargs) or {"deleted_runs": 0, "deleted_chunks": 0, "superseded_run_count": 0},
        ):
            processed = sync_worker.process_next_chunk()

        self.assertTrue(processed)
        self.assertEqual(state["run"]["status"], "done")
        self.assertEqual(len(metadata_calls), 1)
        self.assertNotIn("backfill_completed_through", metadata_calls[0])
        run_metadata = state["run"].get("metadata") or {}
        self.assertTrue(bool(run_metadata.get("no_data_success")))
        self.assertEqual(run_metadata.get("zero_row_marker"), "provider_returned_empty_list")
        self.assertEqual(cleanup_calls, [{"account_ids": ["3986597205"]}])



    def test_tiktok_historical_parser_failure_marks_run_error_and_does_not_advance_backfill(self):
        state = self._build_state(job_type="historical_backfill", platform="tiktok_ads")

        metadata_calls = []

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
                state["run"]["error"] = kwargs.get("error")
            if isinstance(kwargs.get("metadata"), dict):
                existing = state["run"].get("metadata") if isinstance(state["run"].get("metadata"), dict) else {}
                merged = dict(existing)
                merged.update(kwargs.get("metadata") or {})
                state["run"]["metadata"] = merged
            return dict(state["run"])

        def _update_chunk_status(**kwargs):
            state["chunk"]["status"] = kwargs["status"]
            if kwargs.get("metadata") is not None:
                state["chunk"]["metadata"] = kwargs.get("metadata") or {}
            return dict(state["chunk"])

        def _update_progress(**kwargs):
            state["run"]["chunks_done"] = int(state["run"].get("chunks_done") or 0) + int(kwargs.get("chunks_done_delta") or 0)
            state["run"]["rows_written"] = int(state["run"].get("rows_written") or 0) + int(kwargs.get("rows_written_delta") or 0)
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
            sync_worker.sync_run_chunks_store,
            "list_sync_run_chunks",
            return_value=[
                {
                    "chunk_index": 0,
                    "status": "done",
                    "metadata": {
                        "rows_downloaded": 30,
                        "rows_mapped": 0,
                        "zero_row_observability": [{"zero_row_marker": "response_parsed_but_zero_rows_mapped"}],
                    },
                }
            ],
        ), patch.object(
            sync_worker.client_registry_service,
            "update_platform_account_operational_metadata",
            side_effect=lambda **kwargs: metadata_calls.append(kwargs) or kwargs,
        ), patch.object(
            sync_worker.tiktok_ads_service,
            "sync_client",
            return_value={
                "rows_written": 0,
                "rows_downloaded": 30,
                "provider_row_count": 30,
                "rows_mapped": 0,
                "zero_row_observability": [{"zero_row_marker": "response_parsed_but_zero_rows_mapped"}],
            },
        ):
            processed = sync_worker.process_next_chunk()

        self.assertTrue(processed)
        self.assertEqual(state["run"]["status"], "error")
        self.assertEqual(len(metadata_calls), 1)
        self.assertNotIn("backfill_completed_through", metadata_calls[0])
        self.assertNotIn("last_success_at", metadata_calls[0])
        self.assertIn("parser_failure", str(metadata_calls[0].get("last_error") or ""))
        run_metadata = state["run"].get("metadata") or {}
        self.assertTrue(bool(run_metadata.get("parser_failure")))

    def test_tiktok_historical_empty_success_does_not_advance_backfill_coverage(self):
        state = self._build_state(job_type="historical_backfill", platform="tiktok_ads")

        metadata_calls = []
        cleanup_calls = []

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
            if isinstance(kwargs.get("metadata"), dict):
                existing = state["run"].get("metadata") if isinstance(state["run"].get("metadata"), dict) else {}
                merged = dict(existing)
                merged.update(kwargs.get("metadata") or {})
                state["run"]["metadata"] = merged
            return dict(state["run"])

        def _update_chunk_status(**kwargs):
            state["chunk"]["status"] = kwargs["status"]
            if kwargs.get("metadata") is not None:
                state["chunk"]["metadata"] = kwargs.get("metadata") or {}
            return dict(state["chunk"])

        def _update_progress(**kwargs):
            state["run"]["chunks_done"] = int(state["run"].get("chunks_done") or 0) + int(kwargs.get("chunks_done_delta") or 0)
            state["run"]["rows_written"] = int(state["run"].get("rows_written") or 0) + int(kwargs.get("rows_written_delta") or 0)
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
            sync_worker.sync_run_chunks_store,
            "list_sync_run_chunks",
            return_value=[
                {
                    "chunk_index": 0,
                    "status": "done",
                    "metadata": {
                        "rows_downloaded": 0,
                        "rows_mapped": 0,
                        "zero_row_observability": [{"zero_row_marker": "provider_returned_empty_list"}],
                    },
                }
            ],
        ), patch.object(
            sync_worker.client_registry_service,
            "update_platform_account_operational_metadata",
            side_effect=lambda **kwargs: metadata_calls.append(kwargs) or kwargs,
        ), patch.object(
            sync_worker.tiktok_ads_service,
            "sync_client",
            return_value={
                "rows_written": 0,
                "rows_downloaded": 0,
                "provider_row_count": 0,
                "rows_mapped": 0,
                "zero_row_observability": [{"zero_row_marker": "provider_returned_empty_list"}],
            },
        ), patch.object(
            sync_worker.sync_runs_store,
            "cleanup_superseded_tiktok_failed_runs",
            side_effect=lambda **kwargs: cleanup_calls.append(kwargs) or {"deleted_runs": 0, "deleted_chunks": 0, "superseded_run_count": 0},
        ):
            processed = sync_worker.process_next_chunk()

        self.assertTrue(processed)
        self.assertEqual(state["run"]["status"], "done")
        self.assertEqual(len(metadata_calls), 1)
        self.assertNotIn("backfill_completed_through", metadata_calls[0])
        run_metadata = state["run"].get("metadata") or {}
        self.assertTrue(bool(run_metadata.get("no_data_success")))
        self.assertEqual(run_metadata.get("zero_row_marker"), "provider_returned_empty_list")
        self.assertEqual(cleanup_calls, [{"account_ids": ["3986597205"]}])



    def test_tiktok_historical_parser_failure_marks_run_error_and_does_not_advance_backfill(self):
        state = self._build_state(job_type="historical_backfill", platform="tiktok_ads")

        metadata_calls = []

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
                state["run"]["error"] = kwargs.get("error")
            if isinstance(kwargs.get("metadata"), dict):
                existing = state["run"].get("metadata") if isinstance(state["run"].get("metadata"), dict) else {}
                merged = dict(existing)
                merged.update(kwargs.get("metadata") or {})
                state["run"]["metadata"] = merged
            return dict(state["run"])

        def _update_chunk_status(**kwargs):
            state["chunk"]["status"] = kwargs["status"]
            if kwargs.get("metadata") is not None:
                state["chunk"]["metadata"] = kwargs.get("metadata") or {}
            return dict(state["chunk"])

        def _update_progress(**kwargs):
            state["run"]["chunks_done"] = int(state["run"].get("chunks_done") or 0) + int(kwargs.get("chunks_done_delta") or 0)
            state["run"]["rows_written"] = int(state["run"].get("rows_written") or 0) + int(kwargs.get("rows_written_delta") or 0)
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
            sync_worker.sync_run_chunks_store,
            "list_sync_run_chunks",
            return_value=[
                {
                    "chunk_index": 0,
                    "status": "done",
                    "metadata": {
                        "rows_downloaded": 30,
                        "rows_mapped": 0,
                        "zero_row_observability": [{"zero_row_marker": "response_parsed_but_zero_rows_mapped"}],
                    },
                }
            ],
        ), patch.object(
            sync_worker.client_registry_service,
            "update_platform_account_operational_metadata",
            side_effect=lambda **kwargs: metadata_calls.append(kwargs) or kwargs,
        ), patch.object(
            sync_worker.tiktok_ads_service,
            "sync_client",
            return_value={
                "rows_written": 0,
                "rows_downloaded": 30,
                "provider_row_count": 30,
                "rows_mapped": 0,
                "zero_row_observability": [{"zero_row_marker": "response_parsed_but_zero_rows_mapped"}],
            },
        ):
            processed = sync_worker.process_next_chunk()

        self.assertTrue(processed)
        self.assertEqual(state["run"]["status"], "error")
        self.assertEqual(len(metadata_calls), 1)
        self.assertNotIn("backfill_completed_through", metadata_calls[0])
        self.assertNotIn("last_success_at", metadata_calls[0])
        self.assertIn("parser_failure", str(metadata_calls[0].get("last_error") or ""))
        run_metadata = state["run"].get("metadata") or {}
        self.assertTrue(bool(run_metadata.get("parser_failure")))

    def test_tiktok_historical_empty_success_does_not_advance_backfill_coverage(self):
        state = self._build_state(job_type="historical_backfill", platform="tiktok_ads")

        metadata_calls = []
        cleanup_calls = []

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
            if isinstance(kwargs.get("metadata"), dict):
                existing = state["run"].get("metadata") if isinstance(state["run"].get("metadata"), dict) else {}
                merged = dict(existing)
                merged.update(kwargs.get("metadata") or {})
                state["run"]["metadata"] = merged
            return dict(state["run"])

        def _update_chunk_status(**kwargs):
            state["chunk"]["status"] = kwargs["status"]
            if kwargs.get("metadata") is not None:
                state["chunk"]["metadata"] = kwargs.get("metadata") or {}
            return dict(state["chunk"])

        def _update_progress(**kwargs):
            state["run"]["chunks_done"] = int(state["run"].get("chunks_done") or 0) + int(kwargs.get("chunks_done_delta") or 0)
            state["run"]["rows_written"] = int(state["run"].get("rows_written") or 0) + int(kwargs.get("rows_written_delta") or 0)
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
            sync_worker.sync_run_chunks_store,
            "list_sync_run_chunks",
            return_value=[
                {
                    "chunk_index": 0,
                    "status": "done",
                    "metadata": {
                        "rows_downloaded": 0,
                        "rows_mapped": 0,
                        "zero_row_observability": [{"zero_row_marker": "provider_returned_empty_list"}],
                    },
                }
            ],
        ), patch.object(
            sync_worker.client_registry_service,
            "update_platform_account_operational_metadata",
            side_effect=lambda **kwargs: metadata_calls.append(kwargs) or kwargs,
        ), patch.object(
            sync_worker.tiktok_ads_service,
            "sync_client",
            return_value={
                "rows_written": 0,
                "rows_downloaded": 0,
                "provider_row_count": 0,
                "rows_mapped": 0,
                "zero_row_observability": [{"zero_row_marker": "provider_returned_empty_list"}],
            },
        ), patch.object(
            sync_worker.sync_runs_store,
            "cleanup_superseded_tiktok_failed_runs",
            side_effect=lambda **kwargs: cleanup_calls.append(kwargs) or {"deleted_runs": 0, "deleted_chunks": 0, "superseded_run_count": 0},
        ):
            processed = sync_worker.process_next_chunk()

        self.assertTrue(processed)
        self.assertEqual(state["run"]["status"], "done")
        self.assertEqual(len(metadata_calls), 1)
        self.assertNotIn("backfill_completed_through", metadata_calls[0])
        run_metadata = state["run"].get("metadata") or {}
        self.assertTrue(bool(run_metadata.get("no_data_success")))
        self.assertEqual(run_metadata.get("zero_row_marker"), "provider_returned_empty_list")
        self.assertEqual(cleanup_calls, [{"account_ids": ["3986597205"]}])



    def test_tiktok_historical_parser_failure_marks_run_error_and_does_not_advance_backfill(self):
        state = self._build_state(job_type="historical_backfill", platform="tiktok_ads")

        metadata_calls = []

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
                state["run"]["error"] = kwargs.get("error")
            if isinstance(kwargs.get("metadata"), dict):
                existing = state["run"].get("metadata") if isinstance(state["run"].get("metadata"), dict) else {}
                merged = dict(existing)
                merged.update(kwargs.get("metadata") or {})
                state["run"]["metadata"] = merged
            return dict(state["run"])

        def _update_chunk_status(**kwargs):
            state["chunk"]["status"] = kwargs["status"]
            if kwargs.get("metadata") is not None:
                state["chunk"]["metadata"] = kwargs.get("metadata") or {}
            return dict(state["chunk"])

        def _update_progress(**kwargs):
            state["run"]["chunks_done"] = int(state["run"].get("chunks_done") or 0) + int(kwargs.get("chunks_done_delta") or 0)
            state["run"]["rows_written"] = int(state["run"].get("rows_written") or 0) + int(kwargs.get("rows_written_delta") or 0)
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
            sync_worker.sync_run_chunks_store,
            "list_sync_run_chunks",
            return_value=[
                {
                    "chunk_index": 0,
                    "status": "done",
                    "metadata": {
                        "rows_downloaded": 30,
                        "rows_mapped": 0,
                        "zero_row_observability": [{"zero_row_marker": "response_parsed_but_zero_rows_mapped"}],
                    },
                }
            ],
        ), patch.object(
            sync_worker.client_registry_service,
            "update_platform_account_operational_metadata",
            side_effect=lambda **kwargs: metadata_calls.append(kwargs) or kwargs,
        ), patch.object(
            sync_worker.tiktok_ads_service,
            "sync_client",
            return_value={
                "rows_written": 0,
                "rows_downloaded": 30,
                "provider_row_count": 30,
                "rows_mapped": 0,
                "zero_row_observability": [{"zero_row_marker": "response_parsed_but_zero_rows_mapped"}],
            },
        ):
            processed = sync_worker.process_next_chunk()

        self.assertTrue(processed)
        self.assertEqual(state["run"]["status"], "error")
        self.assertEqual(len(metadata_calls), 1)
        self.assertNotIn("backfill_completed_through", metadata_calls[0])
        self.assertNotIn("last_success_at", metadata_calls[0])
        self.assertIn("parser_failure", str(metadata_calls[0].get("last_error") or ""))
        run_metadata = state["run"].get("metadata") or {}
        self.assertTrue(bool(run_metadata.get("parser_failure")))

    def test_tiktok_historical_empty_success_does_not_advance_backfill_coverage(self):
        state = self._build_state(job_type="historical_backfill", platform="tiktok_ads")

        metadata_calls = []
        cleanup_calls = []

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
            if isinstance(kwargs.get("metadata"), dict):
                existing = state["run"].get("metadata") if isinstance(state["run"].get("metadata"), dict) else {}
                merged = dict(existing)
                merged.update(kwargs.get("metadata") or {})
                state["run"]["metadata"] = merged
            return dict(state["run"])

        def _update_chunk_status(**kwargs):
            state["chunk"]["status"] = kwargs["status"]
            if kwargs.get("metadata") is not None:
                state["chunk"]["metadata"] = kwargs.get("metadata") or {}
            return dict(state["chunk"])

        def _update_progress(**kwargs):
            state["run"]["chunks_done"] = int(state["run"].get("chunks_done") or 0) + int(kwargs.get("chunks_done_delta") or 0)
            state["run"]["rows_written"] = int(state["run"].get("rows_written") or 0) + int(kwargs.get("rows_written_delta") or 0)
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
            sync_worker.sync_run_chunks_store,
            "list_sync_run_chunks",
            return_value=[
                {
                    "chunk_index": 0,
                    "status": "done",
                    "metadata": {
                        "rows_downloaded": 0,
                        "rows_mapped": 0,
                        "zero_row_observability": [{"zero_row_marker": "provider_returned_empty_list"}],
                    },
                }
            ],
        ), patch.object(
            sync_worker.client_registry_service,
            "update_platform_account_operational_metadata",
            side_effect=lambda **kwargs: metadata_calls.append(kwargs) or kwargs,
        ), patch.object(
            sync_worker.tiktok_ads_service,
            "sync_client",
            return_value={
                "rows_written": 0,
                "rows_downloaded": 0,
                "provider_row_count": 0,
                "rows_mapped": 0,
                "zero_row_observability": [{"zero_row_marker": "provider_returned_empty_list"}],
            },
        ), patch.object(
            sync_worker.sync_runs_store,
            "cleanup_superseded_tiktok_failed_runs",
            side_effect=lambda **kwargs: cleanup_calls.append(kwargs) or {"deleted_runs": 0, "deleted_chunks": 0, "superseded_run_count": 0},
        ):
            processed = sync_worker.process_next_chunk()

        self.assertTrue(processed)
        self.assertEqual(state["run"]["status"], "done")
        self.assertEqual(len(metadata_calls), 1)
        self.assertNotIn("backfill_completed_through", metadata_calls[0])
        run_metadata = state["run"].get("metadata") or {}
        self.assertTrue(bool(run_metadata.get("no_data_success")))
        self.assertEqual(run_metadata.get("zero_row_marker"), "provider_returned_empty_list")
        self.assertEqual(cleanup_calls, [{"account_ids": ["3986597205"]}])



    def test_tiktok_historical_parser_failure_marks_run_error_and_does_not_advance_backfill(self):
        state = self._build_state(job_type="historical_backfill", platform="tiktok_ads")

        metadata_calls = []

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
                state["run"]["error"] = kwargs.get("error")
            if isinstance(kwargs.get("metadata"), dict):
                existing = state["run"].get("metadata") if isinstance(state["run"].get("metadata"), dict) else {}
                merged = dict(existing)
                merged.update(kwargs.get("metadata") or {})
                state["run"]["metadata"] = merged
            return dict(state["run"])

        def _update_chunk_status(**kwargs):
            state["chunk"]["status"] = kwargs["status"]
            if kwargs.get("metadata") is not None:
                state["chunk"]["metadata"] = kwargs.get("metadata") or {}
            return dict(state["chunk"])

        def _update_progress(**kwargs):
            state["run"]["chunks_done"] = int(state["run"].get("chunks_done") or 0) + int(kwargs.get("chunks_done_delta") or 0)
            state["run"]["rows_written"] = int(state["run"].get("rows_written") or 0) + int(kwargs.get("rows_written_delta") or 0)
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
            sync_worker.sync_run_chunks_store,
            "list_sync_run_chunks",
            return_value=[
                {
                    "chunk_index": 0,
                    "status": "done",
                    "metadata": {
                        "rows_downloaded": 30,
                        "rows_mapped": 0,
                        "zero_row_observability": [{"zero_row_marker": "response_parsed_but_zero_rows_mapped"}],
                    },
                }
            ],
        ), patch.object(
            sync_worker.client_registry_service,
            "update_platform_account_operational_metadata",
            side_effect=lambda **kwargs: metadata_calls.append(kwargs) or kwargs,
        ), patch.object(
            sync_worker.tiktok_ads_service,
            "sync_client",
            return_value={
                "rows_written": 0,
                "rows_downloaded": 30,
                "provider_row_count": 30,
                "rows_mapped": 0,
                "zero_row_observability": [{"zero_row_marker": "response_parsed_but_zero_rows_mapped"}],
            },
        ):
            processed = sync_worker.process_next_chunk()

        self.assertTrue(processed)
        self.assertEqual(state["run"]["status"], "error")
        self.assertEqual(len(metadata_calls), 1)
        self.assertNotIn("backfill_completed_through", metadata_calls[0])
        self.assertNotIn("last_success_at", metadata_calls[0])
        self.assertIn("parser_failure", str(metadata_calls[0].get("last_error") or ""))
        run_metadata = state["run"].get("metadata") or {}
        self.assertTrue(bool(run_metadata.get("parser_failure")))

    def test_tiktok_historical_empty_success_does_not_advance_backfill_coverage(self):
        state = self._build_state(job_type="historical_backfill", platform="tiktok_ads")

        metadata_calls = []
        cleanup_calls = []

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
            if isinstance(kwargs.get("metadata"), dict):
                existing = state["run"].get("metadata") if isinstance(state["run"].get("metadata"), dict) else {}
                merged = dict(existing)
                merged.update(kwargs.get("metadata") or {})
                state["run"]["metadata"] = merged
            return dict(state["run"])

        def _update_chunk_status(**kwargs):
            state["chunk"]["status"] = kwargs["status"]
            if kwargs.get("metadata") is not None:
                state["chunk"]["metadata"] = kwargs.get("metadata") or {}
            return dict(state["chunk"])

        def _update_progress(**kwargs):
            state["run"]["chunks_done"] = int(state["run"].get("chunks_done") or 0) + int(kwargs.get("chunks_done_delta") or 0)
            state["run"]["rows_written"] = int(state["run"].get("rows_written") or 0) + int(kwargs.get("rows_written_delta") or 0)
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
            sync_worker.sync_run_chunks_store,
            "list_sync_run_chunks",
            return_value=[
                {
                    "chunk_index": 0,
                    "status": "done",
                    "metadata": {
                        "rows_downloaded": 0,
                        "rows_mapped": 0,
                        "zero_row_observability": [{"zero_row_marker": "provider_returned_empty_list"}],
                    },
                }
            ],
        ), patch.object(
            sync_worker.client_registry_service,
            "update_platform_account_operational_metadata",
            side_effect=lambda **kwargs: metadata_calls.append(kwargs) or kwargs,
        ), patch.object(
            sync_worker.tiktok_ads_service,
            "sync_client",
            return_value={
                "rows_written": 0,
                "rows_downloaded": 0,
                "provider_row_count": 0,
                "rows_mapped": 0,
                "zero_row_observability": [{"zero_row_marker": "provider_returned_empty_list"}],
            },
        ), patch.object(
            sync_worker.sync_runs_store,
            "cleanup_superseded_tiktok_failed_runs",
            side_effect=lambda **kwargs: cleanup_calls.append(kwargs) or {"deleted_runs": 0, "deleted_chunks": 0, "superseded_run_count": 0},
        ):
            processed = sync_worker.process_next_chunk()

        self.assertTrue(processed)
        self.assertEqual(state["run"]["status"], "done")
        self.assertEqual(len(metadata_calls), 1)
        self.assertNotIn("backfill_completed_through", metadata_calls[0])
        run_metadata = state["run"].get("metadata") or {}
        self.assertTrue(bool(run_metadata.get("no_data_success")))
        self.assertEqual(run_metadata.get("zero_row_marker"), "provider_returned_empty_list")
        self.assertEqual(cleanup_calls, [{"account_ids": ["3986597205"]}])



    def test_tiktok_historical_parser_failure_marks_run_error_and_does_not_advance_backfill(self):
        state = self._build_state(job_type="historical_backfill", platform="tiktok_ads")

        metadata_calls = []

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
                state["run"]["error"] = kwargs.get("error")
            if isinstance(kwargs.get("metadata"), dict):
                existing = state["run"].get("metadata") if isinstance(state["run"].get("metadata"), dict) else {}
                merged = dict(existing)
                merged.update(kwargs.get("metadata") or {})
                state["run"]["metadata"] = merged
            return dict(state["run"])

        def _update_chunk_status(**kwargs):
            state["chunk"]["status"] = kwargs["status"]
            if kwargs.get("metadata") is not None:
                state["chunk"]["metadata"] = kwargs.get("metadata") or {}
            return dict(state["chunk"])

        def _update_progress(**kwargs):
            state["run"]["chunks_done"] = int(state["run"].get("chunks_done") or 0) + int(kwargs.get("chunks_done_delta") or 0)
            state["run"]["rows_written"] = int(state["run"].get("rows_written") or 0) + int(kwargs.get("rows_written_delta") or 0)
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
            sync_worker.sync_run_chunks_store,
            "list_sync_run_chunks",
            return_value=[
                {
                    "chunk_index": 0,
                    "status": "done",
                    "metadata": {
                        "rows_downloaded": 30,
                        "rows_mapped": 0,
                        "zero_row_observability": [{"zero_row_marker": "response_parsed_but_zero_rows_mapped"}],
                    },
                }
            ],
        ), patch.object(
            sync_worker.client_registry_service,
            "update_platform_account_operational_metadata",
            side_effect=lambda **kwargs: metadata_calls.append(kwargs) or kwargs,
        ), patch.object(
            sync_worker.tiktok_ads_service,
            "sync_client",
            return_value={
                "rows_written": 0,
                "rows_downloaded": 30,
                "provider_row_count": 30,
                "rows_mapped": 0,
                "zero_row_observability": [{"zero_row_marker": "response_parsed_but_zero_rows_mapped"}],
            },
        ):
            processed = sync_worker.process_next_chunk()

        self.assertTrue(processed)
        self.assertEqual(state["run"]["status"], "error")
        self.assertEqual(len(metadata_calls), 1)
        self.assertNotIn("backfill_completed_through", metadata_calls[0])
        self.assertNotIn("last_success_at", metadata_calls[0])
        self.assertIn("parser_failure", str(metadata_calls[0].get("last_error") or ""))
        run_metadata = state["run"].get("metadata") or {}
        self.assertTrue(bool(run_metadata.get("parser_failure")))

    def test_tiktok_historical_empty_success_does_not_advance_backfill_coverage(self):
        state = self._build_state(job_type="historical_backfill", platform="tiktok_ads")

        metadata_calls = []
        cleanup_calls = []

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
            if isinstance(kwargs.get("metadata"), dict):
                existing = state["run"].get("metadata") if isinstance(state["run"].get("metadata"), dict) else {}
                merged = dict(existing)
                merged.update(kwargs.get("metadata") or {})
                state["run"]["metadata"] = merged
            return dict(state["run"])

        def _update_chunk_status(**kwargs):
            state["chunk"]["status"] = kwargs["status"]
            if kwargs.get("metadata") is not None:
                state["chunk"]["metadata"] = kwargs.get("metadata") or {}
            return dict(state["chunk"])

        def _update_progress(**kwargs):
            state["run"]["chunks_done"] = int(state["run"].get("chunks_done") or 0) + int(kwargs.get("chunks_done_delta") or 0)
            state["run"]["rows_written"] = int(state["run"].get("rows_written") or 0) + int(kwargs.get("rows_written_delta") or 0)
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
            sync_worker.sync_run_chunks_store,
            "list_sync_run_chunks",
            return_value=[
                {
                    "chunk_index": 0,
                    "status": "done",
                    "metadata": {
                        "rows_downloaded": 0,
                        "rows_mapped": 0,
                        "zero_row_observability": [{"zero_row_marker": "provider_returned_empty_list"}],
                    },
                }
            ],
        ), patch.object(
            sync_worker.client_registry_service,
            "update_platform_account_operational_metadata",
            side_effect=lambda **kwargs: metadata_calls.append(kwargs) or kwargs,
        ), patch.object(
            sync_worker.tiktok_ads_service,
            "sync_client",
            return_value={
                "rows_written": 0,
                "rows_downloaded": 0,
                "provider_row_count": 0,
                "rows_mapped": 0,
                "zero_row_observability": [{"zero_row_marker": "provider_returned_empty_list"}],
            },
        ), patch.object(
            sync_worker.sync_runs_store,
            "cleanup_superseded_tiktok_failed_runs",
            side_effect=lambda **kwargs: cleanup_calls.append(kwargs) or {"deleted_runs": 0, "deleted_chunks": 0, "superseded_run_count": 0},
        ):
            processed = sync_worker.process_next_chunk()

        self.assertTrue(processed)
        self.assertEqual(state["run"]["status"], "done")
        self.assertEqual(len(metadata_calls), 1)
        self.assertNotIn("backfill_completed_through", metadata_calls[0])
        run_metadata = state["run"].get("metadata") or {}
        self.assertTrue(bool(run_metadata.get("no_data_success")))
        self.assertEqual(run_metadata.get("zero_row_marker"), "provider_returned_empty_list")
        self.assertEqual(cleanup_calls, [{"account_ids": ["3986597205"]}])



    def test_tiktok_historical_parser_failure_marks_run_error_and_does_not_advance_backfill(self):
        state = self._build_state(job_type="historical_backfill", platform="tiktok_ads")

        metadata_calls = []

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
                state["run"]["error"] = kwargs.get("error")
            if isinstance(kwargs.get("metadata"), dict):
                existing = state["run"].get("metadata") if isinstance(state["run"].get("metadata"), dict) else {}
                merged = dict(existing)
                merged.update(kwargs.get("metadata") or {})
                state["run"]["metadata"] = merged
            return dict(state["run"])

        def _update_chunk_status(**kwargs):
            state["chunk"]["status"] = kwargs["status"]
            if kwargs.get("metadata") is not None:
                state["chunk"]["metadata"] = kwargs.get("metadata") or {}
            return dict(state["chunk"])

        def _update_progress(**kwargs):
            state["run"]["chunks_done"] = int(state["run"].get("chunks_done") or 0) + int(kwargs.get("chunks_done_delta") or 0)
            state["run"]["rows_written"] = int(state["run"].get("rows_written") or 0) + int(kwargs.get("rows_written_delta") or 0)
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
            sync_worker.sync_run_chunks_store,
            "list_sync_run_chunks",
            return_value=[
                {
                    "chunk_index": 0,
                    "status": "done",
                    "metadata": {
                        "rows_downloaded": 30,
                        "rows_mapped": 0,
                        "zero_row_observability": [{"zero_row_marker": "response_parsed_but_zero_rows_mapped"}],
                    },
                }
            ],
        ), patch.object(
            sync_worker.client_registry_service,
            "update_platform_account_operational_metadata",
            side_effect=lambda **kwargs: metadata_calls.append(kwargs) or kwargs,
        ), patch.object(
            sync_worker.tiktok_ads_service,
            "sync_client",
            return_value={
                "rows_written": 0,
                "rows_downloaded": 30,
                "provider_row_count": 30,
                "rows_mapped": 0,
                "zero_row_observability": [{"zero_row_marker": "response_parsed_but_zero_rows_mapped"}],
            },
        ):
            processed = sync_worker.process_next_chunk()

        self.assertTrue(processed)
        self.assertEqual(state["run"]["status"], "error")
        self.assertEqual(len(metadata_calls), 1)
        self.assertNotIn("backfill_completed_through", metadata_calls[0])
        self.assertNotIn("last_success_at", metadata_calls[0])
        self.assertIn("parser_failure", str(metadata_calls[0].get("last_error") or ""))
        run_metadata = state["run"].get("metadata") or {}
        self.assertTrue(bool(run_metadata.get("parser_failure")))

    def test_tiktok_historical_empty_success_does_not_advance_backfill_coverage(self):
        state = self._build_state(job_type="historical_backfill", platform="tiktok_ads")

        metadata_calls = []
        cleanup_calls = []

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
            if isinstance(kwargs.get("metadata"), dict):
                existing = state["run"].get("metadata") if isinstance(state["run"].get("metadata"), dict) else {}
                merged = dict(existing)
                merged.update(kwargs.get("metadata") or {})
                state["run"]["metadata"] = merged
            return dict(state["run"])

        def _update_chunk_status(**kwargs):
            state["chunk"]["status"] = kwargs["status"]
            if kwargs.get("metadata") is not None:
                state["chunk"]["metadata"] = kwargs.get("metadata") or {}
            return dict(state["chunk"])

        def _update_progress(**kwargs):
            state["run"]["chunks_done"] = int(state["run"].get("chunks_done") or 0) + int(kwargs.get("chunks_done_delta") or 0)
            state["run"]["rows_written"] = int(state["run"].get("rows_written") or 0) + int(kwargs.get("rows_written_delta") or 0)
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
            sync_worker.sync_run_chunks_store,
            "list_sync_run_chunks",
            return_value=[
                {
                    "chunk_index": 0,
                    "status": "done",
                    "metadata": {
                        "rows_downloaded": 0,
                        "rows_mapped": 0,
                        "zero_row_observability": [{"zero_row_marker": "provider_returned_empty_list"}],
                    },
                }
            ],
        ), patch.object(
            sync_worker.client_registry_service,
            "update_platform_account_operational_metadata",
            side_effect=lambda **kwargs: metadata_calls.append(kwargs) or kwargs,
        ), patch.object(
            sync_worker.tiktok_ads_service,
            "sync_client",
            return_value={
                "rows_written": 0,
                "rows_downloaded": 0,
                "provider_row_count": 0,
                "rows_mapped": 0,
                "zero_row_observability": [{"zero_row_marker": "provider_returned_empty_list"}],
            },
        ), patch.object(
            sync_worker.sync_runs_store,
            "cleanup_superseded_tiktok_failed_runs",
            side_effect=lambda **kwargs: cleanup_calls.append(kwargs) or {"deleted_runs": 0, "deleted_chunks": 0, "superseded_run_count": 0},
        ):
            processed = sync_worker.process_next_chunk()

        self.assertTrue(processed)
        self.assertEqual(state["run"]["status"], "done")
        self.assertEqual(len(metadata_calls), 1)
        self.assertNotIn("backfill_completed_through", metadata_calls[0])
        run_metadata = state["run"].get("metadata") or {}
        self.assertTrue(bool(run_metadata.get("no_data_success")))
        self.assertEqual(run_metadata.get("zero_row_marker"), "provider_returned_empty_list")
        self.assertEqual(cleanup_calls, [{"account_ids": ["3986597205"]}])



    def test_tiktok_historical_parser_failure_marks_run_error_and_does_not_advance_backfill(self):
        state = self._build_state(job_type="historical_backfill", platform="tiktok_ads")

        metadata_calls = []

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
                state["run"]["error"] = kwargs.get("error")
            if isinstance(kwargs.get("metadata"), dict):
                existing = state["run"].get("metadata") if isinstance(state["run"].get("metadata"), dict) else {}
                merged = dict(existing)
                merged.update(kwargs.get("metadata") or {})
                state["run"]["metadata"] = merged
            return dict(state["run"])

        def _update_chunk_status(**kwargs):
            state["chunk"]["status"] = kwargs["status"]
            if kwargs.get("metadata") is not None:
                state["chunk"]["metadata"] = kwargs.get("metadata") or {}
            return dict(state["chunk"])

        def _update_progress(**kwargs):
            state["run"]["chunks_done"] = int(state["run"].get("chunks_done") or 0) + int(kwargs.get("chunks_done_delta") or 0)
            state["run"]["rows_written"] = int(state["run"].get("rows_written") or 0) + int(kwargs.get("rows_written_delta") or 0)
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
            sync_worker.sync_run_chunks_store,
            "list_sync_run_chunks",
            return_value=[
                {
                    "chunk_index": 0,
                    "status": "done",
                    "metadata": {
                        "rows_downloaded": 30,
                        "rows_mapped": 0,
                        "zero_row_observability": [{"zero_row_marker": "response_parsed_but_zero_rows_mapped"}],
                    },
                }
            ],
        ), patch.object(
            sync_worker.client_registry_service,
            "update_platform_account_operational_metadata",
            side_effect=lambda **kwargs: metadata_calls.append(kwargs) or kwargs,
        ), patch.object(
            sync_worker.tiktok_ads_service,
            "sync_client",
            return_value={
                "rows_written": 0,
                "rows_downloaded": 30,
                "provider_row_count": 30,
                "rows_mapped": 0,
                "zero_row_observability": [{"zero_row_marker": "response_parsed_but_zero_rows_mapped"}],
            },
        ):
            processed = sync_worker.process_next_chunk()

        self.assertTrue(processed)
        self.assertEqual(state["run"]["status"], "error")
        self.assertEqual(len(metadata_calls), 1)
        self.assertNotIn("backfill_completed_through", metadata_calls[0])
        self.assertNotIn("last_success_at", metadata_calls[0])
        self.assertIn("parser_failure", str(metadata_calls[0].get("last_error") or ""))
        run_metadata = state["run"].get("metadata") or {}
        self.assertTrue(bool(run_metadata.get("parser_failure")))

    def test_tiktok_historical_empty_success_does_not_advance_backfill_coverage(self):
        state = self._build_state(job_type="historical_backfill", platform="tiktok_ads")

        metadata_calls = []
        cleanup_calls = []

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
            if isinstance(kwargs.get("metadata"), dict):
                existing = state["run"].get("metadata") if isinstance(state["run"].get("metadata"), dict) else {}
                merged = dict(existing)
                merged.update(kwargs.get("metadata") or {})
                state["run"]["metadata"] = merged
            return dict(state["run"])

        def _update_chunk_status(**kwargs):
            state["chunk"]["status"] = kwargs["status"]
            if kwargs.get("metadata") is not None:
                state["chunk"]["metadata"] = kwargs.get("metadata") or {}
            return dict(state["chunk"])

        def _update_progress(**kwargs):
            state["run"]["chunks_done"] = int(state["run"].get("chunks_done") or 0) + int(kwargs.get("chunks_done_delta") or 0)
            state["run"]["rows_written"] = int(state["run"].get("rows_written") or 0) + int(kwargs.get("rows_written_delta") or 0)
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
            sync_worker.sync_run_chunks_store,
            "list_sync_run_chunks",
            return_value=[
                {
                    "chunk_index": 0,
                    "status": "done",
                    "metadata": {
                        "rows_downloaded": 0,
                        "rows_mapped": 0,
                        "zero_row_observability": [{"zero_row_marker": "provider_returned_empty_list"}],
                    },
                }
            ],
        ), patch.object(
            sync_worker.client_registry_service,
            "update_platform_account_operational_metadata",
            side_effect=lambda **kwargs: metadata_calls.append(kwargs) or kwargs,
        ), patch.object(
            sync_worker.tiktok_ads_service,
            "sync_client",
            return_value={
                "rows_written": 0,
                "rows_downloaded": 0,
                "provider_row_count": 0,
                "rows_mapped": 0,
                "zero_row_observability": [{"zero_row_marker": "provider_returned_empty_list"}],
            },
        ), patch.object(
            sync_worker.sync_runs_store,
            "cleanup_superseded_tiktok_failed_runs",
            side_effect=lambda **kwargs: cleanup_calls.append(kwargs) or {"deleted_runs": 0, "deleted_chunks": 0, "superseded_run_count": 0},
        ):
            processed = sync_worker.process_next_chunk()

        self.assertTrue(processed)
        self.assertEqual(state["run"]["status"], "done")
        self.assertEqual(len(metadata_calls), 1)
        self.assertNotIn("backfill_completed_through", metadata_calls[0])
        run_metadata = state["run"].get("metadata") or {}
        self.assertTrue(bool(run_metadata.get("no_data_success")))
        self.assertEqual(run_metadata.get("zero_row_marker"), "provider_returned_empty_list")
        self.assertEqual(cleanup_calls, [{"account_ids": ["3986597205"]}])



    def test_tiktok_historical_parser_failure_marks_run_error_and_does_not_advance_backfill(self):
        state = self._build_state(job_type="historical_backfill", platform="tiktok_ads")

        metadata_calls = []

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
                state["run"]["error"] = kwargs.get("error")
            if isinstance(kwargs.get("metadata"), dict):
                existing = state["run"].get("metadata") if isinstance(state["run"].get("metadata"), dict) else {}
                merged = dict(existing)
                merged.update(kwargs.get("metadata") or {})
                state["run"]["metadata"] = merged
            return dict(state["run"])

        def _update_chunk_status(**kwargs):
            state["chunk"]["status"] = kwargs["status"]
            if kwargs.get("metadata") is not None:
                state["chunk"]["metadata"] = kwargs.get("metadata") or {}
            return dict(state["chunk"])

        def _update_progress(**kwargs):
            state["run"]["chunks_done"] = int(state["run"].get("chunks_done") or 0) + int(kwargs.get("chunks_done_delta") or 0)
            state["run"]["rows_written"] = int(state["run"].get("rows_written") or 0) + int(kwargs.get("rows_written_delta") or 0)
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
            sync_worker.sync_run_chunks_store,
            "list_sync_run_chunks",
            return_value=[
                {
                    "chunk_index": 0,
                    "status": "done",
                    "metadata": {
                        "rows_downloaded": 30,
                        "rows_mapped": 0,
                        "zero_row_observability": [{"zero_row_marker": "response_parsed_but_zero_rows_mapped"}],
                    },
                }
            ],
        ), patch.object(
            sync_worker.client_registry_service,
            "update_platform_account_operational_metadata",
            side_effect=lambda **kwargs: metadata_calls.append(kwargs) or kwargs,
        ), patch.object(
            sync_worker.tiktok_ads_service,
            "sync_client",
            return_value={
                "rows_written": 0,
                "rows_downloaded": 30,
                "provider_row_count": 30,
                "rows_mapped": 0,
                "zero_row_observability": [{"zero_row_marker": "response_parsed_but_zero_rows_mapped"}],
            },
        ):
            processed = sync_worker.process_next_chunk()

        self.assertTrue(processed)
        self.assertEqual(state["run"]["status"], "error")
        self.assertEqual(len(metadata_calls), 1)
        self.assertNotIn("backfill_completed_through", metadata_calls[0])
        self.assertNotIn("last_success_at", metadata_calls[0])
        self.assertIn("parser_failure", str(metadata_calls[0].get("last_error") or ""))
        run_metadata = state["run"].get("metadata") or {}
        self.assertTrue(bool(run_metadata.get("parser_failure")))

    def test_tiktok_historical_empty_success_does_not_advance_backfill_coverage(self):
        state = self._build_state(job_type="historical_backfill", platform="tiktok_ads")

        metadata_calls = []
        cleanup_calls = []

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
            if isinstance(kwargs.get("metadata"), dict):
                existing = state["run"].get("metadata") if isinstance(state["run"].get("metadata"), dict) else {}
                merged = dict(existing)
                merged.update(kwargs.get("metadata") or {})
                state["run"]["metadata"] = merged
            return dict(state["run"])

        def _update_chunk_status(**kwargs):
            state["chunk"]["status"] = kwargs["status"]
            if kwargs.get("metadata") is not None:
                state["chunk"]["metadata"] = kwargs.get("metadata") or {}
            return dict(state["chunk"])

        def _update_progress(**kwargs):
            state["run"]["chunks_done"] = int(state["run"].get("chunks_done") or 0) + int(kwargs.get("chunks_done_delta") or 0)
            state["run"]["rows_written"] = int(state["run"].get("rows_written") or 0) + int(kwargs.get("rows_written_delta") or 0)
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
            sync_worker.sync_run_chunks_store,
            "list_sync_run_chunks",
            return_value=[
                {
                    "chunk_index": 0,
                    "status": "done",
                    "metadata": {
                        "rows_downloaded": 0,
                        "rows_mapped": 0,
                        "zero_row_observability": [{"zero_row_marker": "provider_returned_empty_list"}],
                    },
                }
            ],
        ), patch.object(
            sync_worker.client_registry_service,
            "update_platform_account_operational_metadata",
            side_effect=lambda **kwargs: metadata_calls.append(kwargs) or kwargs,
        ), patch.object(
            sync_worker.tiktok_ads_service,
            "sync_client",
            return_value={
                "rows_written": 0,
                "rows_downloaded": 0,
                "provider_row_count": 0,
                "rows_mapped": 0,
                "zero_row_observability": [{"zero_row_marker": "provider_returned_empty_list"}],
            },
        ), patch.object(
            sync_worker.sync_runs_store,
            "cleanup_superseded_tiktok_failed_runs",
            side_effect=lambda **kwargs: cleanup_calls.append(kwargs) or {"deleted_runs": 0, "deleted_chunks": 0, "superseded_run_count": 0},
        ):
            processed = sync_worker.process_next_chunk()

        self.assertTrue(processed)
        self.assertEqual(state["run"]["status"], "done")
        self.assertEqual(len(metadata_calls), 1)
        self.assertNotIn("backfill_completed_through", metadata_calls[0])
        run_metadata = state["run"].get("metadata") or {}
        self.assertTrue(bool(run_metadata.get("no_data_success")))
        self.assertEqual(run_metadata.get("zero_row_marker"), "provider_returned_empty_list")
        self.assertEqual(cleanup_calls, [{"account_ids": ["3986597205"]}])



    def test_tiktok_historical_parser_failure_marks_run_error_and_does_not_advance_backfill(self):
        state = self._build_state(job_type="historical_backfill", platform="tiktok_ads")

        metadata_calls = []

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
                state["run"]["error"] = kwargs.get("error")
            if isinstance(kwargs.get("metadata"), dict):
                existing = state["run"].get("metadata") if isinstance(state["run"].get("metadata"), dict) else {}
                merged = dict(existing)
                merged.update(kwargs.get("metadata") or {})
                state["run"]["metadata"] = merged
            return dict(state["run"])

        def _update_chunk_status(**kwargs):
            state["chunk"]["status"] = kwargs["status"]
            if kwargs.get("metadata") is not None:
                state["chunk"]["metadata"] = kwargs.get("metadata") or {}
            return dict(state["chunk"])

        def _update_progress(**kwargs):
            state["run"]["chunks_done"] = int(state["run"].get("chunks_done") or 0) + int(kwargs.get("chunks_done_delta") or 0)
            state["run"]["rows_written"] = int(state["run"].get("rows_written") or 0) + int(kwargs.get("rows_written_delta") or 0)
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
            sync_worker.sync_run_chunks_store,
            "list_sync_run_chunks",
            return_value=[
                {
                    "chunk_index": 0,
                    "status": "done",
                    "metadata": {
                        "rows_downloaded": 30,
                        "rows_mapped": 0,
                        "zero_row_observability": [{"zero_row_marker": "response_parsed_but_zero_rows_mapped"}],
                    },
                }
            ],
        ), patch.object(
            sync_worker.client_registry_service,
            "update_platform_account_operational_metadata",
            side_effect=lambda **kwargs: metadata_calls.append(kwargs) or kwargs,
        ), patch.object(
            sync_worker.tiktok_ads_service,
            "sync_client",
            return_value={
                "rows_written": 0,
                "rows_downloaded": 30,
                "provider_row_count": 30,
                "rows_mapped": 0,
                "zero_row_observability": [{"zero_row_marker": "response_parsed_but_zero_rows_mapped"}],
            },
        ):
            processed = sync_worker.process_next_chunk()

        self.assertTrue(processed)
        self.assertEqual(state["run"]["status"], "error")
        self.assertEqual(len(metadata_calls), 1)
        self.assertNotIn("backfill_completed_through", metadata_calls[0])
        self.assertNotIn("last_success_at", metadata_calls[0])
        self.assertIn("parser_failure", str(metadata_calls[0].get("last_error") or ""))
        run_metadata = state["run"].get("metadata") or {}
        self.assertTrue(bool(run_metadata.get("parser_failure")))

    def test_tiktok_historical_empty_success_does_not_advance_backfill_coverage(self):
        state = self._build_state(job_type="historical_backfill", platform="tiktok_ads")

        metadata_calls = []
        cleanup_calls = []

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
            if isinstance(kwargs.get("metadata"), dict):
                existing = state["run"].get("metadata") if isinstance(state["run"].get("metadata"), dict) else {}
                merged = dict(existing)
                merged.update(kwargs.get("metadata") or {})
                state["run"]["metadata"] = merged
            return dict(state["run"])

        def _update_chunk_status(**kwargs):
            state["chunk"]["status"] = kwargs["status"]
            if kwargs.get("metadata") is not None:
                state["chunk"]["metadata"] = kwargs.get("metadata") or {}
            return dict(state["chunk"])

        def _update_progress(**kwargs):
            state["run"]["chunks_done"] = int(state["run"].get("chunks_done") or 0) + int(kwargs.get("chunks_done_delta") or 0)
            state["run"]["rows_written"] = int(state["run"].get("rows_written") or 0) + int(kwargs.get("rows_written_delta") or 0)
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
            sync_worker.sync_run_chunks_store,
            "list_sync_run_chunks",
            return_value=[
                {
                    "chunk_index": 0,
                    "status": "done",
                    "metadata": {
                        "rows_downloaded": 0,
                        "rows_mapped": 0,
                        "zero_row_observability": [{"zero_row_marker": "provider_returned_empty_list"}],
                    },
                }
            ],
        ), patch.object(
            sync_worker.client_registry_service,
            "update_platform_account_operational_metadata",
            side_effect=lambda **kwargs: metadata_calls.append(kwargs) or kwargs,
        ), patch.object(
            sync_worker.tiktok_ads_service,
            "sync_client",
            return_value={
                "rows_written": 0,
                "rows_downloaded": 0,
                "provider_row_count": 0,
                "rows_mapped": 0,
                "zero_row_observability": [{"zero_row_marker": "provider_returned_empty_list"}],
            },
        ), patch.object(
            sync_worker.sync_runs_store,
            "cleanup_superseded_tiktok_failed_runs",
            side_effect=lambda **kwargs: cleanup_calls.append(kwargs) or {"deleted_runs": 0, "deleted_chunks": 0, "superseded_run_count": 0},
        ):
            processed = sync_worker.process_next_chunk()

        self.assertTrue(processed)
        self.assertEqual(state["run"]["status"], "done")
        self.assertEqual(len(metadata_calls), 1)
        self.assertNotIn("backfill_completed_through", metadata_calls[0])
        run_metadata = state["run"].get("metadata") or {}
        self.assertTrue(bool(run_metadata.get("no_data_success")))
        self.assertEqual(run_metadata.get("zero_row_marker"), "provider_returned_empty_list")
        self.assertEqual(cleanup_calls, [{"account_ids": ["3986597205"]}])



    def test_tiktok_historical_parser_failure_marks_run_error_and_does_not_advance_backfill(self):
        state = self._build_state(job_type="historical_backfill", platform="tiktok_ads")

        metadata_calls = []

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
                state["run"]["error"] = kwargs.get("error")
            if isinstance(kwargs.get("metadata"), dict):
                existing = state["run"].get("metadata") if isinstance(state["run"].get("metadata"), dict) else {}
                merged = dict(existing)
                merged.update(kwargs.get("metadata") or {})
                state["run"]["metadata"] = merged
            return dict(state["run"])

        def _update_chunk_status(**kwargs):
            state["chunk"]["status"] = kwargs["status"]
            if kwargs.get("metadata") is not None:
                state["chunk"]["metadata"] = kwargs.get("metadata") or {}
            return dict(state["chunk"])

        def _update_progress(**kwargs):
            state["run"]["chunks_done"] = int(state["run"].get("chunks_done") or 0) + int(kwargs.get("chunks_done_delta") or 0)
            state["run"]["rows_written"] = int(state["run"].get("rows_written") or 0) + int(kwargs.get("rows_written_delta") or 0)
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
            sync_worker.sync_run_chunks_store,
            "list_sync_run_chunks",
            return_value=[
                {
                    "chunk_index": 0,
                    "status": "done",
                    "metadata": {
                        "rows_downloaded": 30,
                        "rows_mapped": 0,
                        "zero_row_observability": [{"zero_row_marker": "response_parsed_but_zero_rows_mapped"}],
                    },
                }
            ],
        ), patch.object(
            sync_worker.client_registry_service,
            "update_platform_account_operational_metadata",
            side_effect=lambda **kwargs: metadata_calls.append(kwargs) or kwargs,
        ), patch.object(
            sync_worker.tiktok_ads_service,
            "sync_client",
            return_value={
                "rows_written": 0,
                "rows_downloaded": 30,
                "provider_row_count": 30,
                "rows_mapped": 0,
                "zero_row_observability": [{"zero_row_marker": "response_parsed_but_zero_rows_mapped"}],
            },
        ):
            processed = sync_worker.process_next_chunk()

        self.assertTrue(processed)
        self.assertEqual(state["run"]["status"], "error")
        self.assertEqual(len(metadata_calls), 1)
        self.assertNotIn("backfill_completed_through", metadata_calls[0])
        self.assertNotIn("last_success_at", metadata_calls[0])
        self.assertIn("parser_failure", str(metadata_calls[0].get("last_error") or ""))
        run_metadata = state["run"].get("metadata") or {}
        self.assertTrue(bool(run_metadata.get("parser_failure")))

    def test_tiktok_historical_empty_success_does_not_advance_backfill_coverage(self):
        state = self._build_state(job_type="historical_backfill", platform="tiktok_ads")

        metadata_calls = []
        cleanup_calls = []

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
            if isinstance(kwargs.get("metadata"), dict):
                existing = state["run"].get("metadata") if isinstance(state["run"].get("metadata"), dict) else {}
                merged = dict(existing)
                merged.update(kwargs.get("metadata") or {})
                state["run"]["metadata"] = merged
            return dict(state["run"])

        def _update_chunk_status(**kwargs):
            state["chunk"]["status"] = kwargs["status"]
            if kwargs.get("metadata") is not None:
                state["chunk"]["metadata"] = kwargs.get("metadata") or {}
            return dict(state["chunk"])

        def _update_progress(**kwargs):
            state["run"]["chunks_done"] = int(state["run"].get("chunks_done") or 0) + int(kwargs.get("chunks_done_delta") or 0)
            state["run"]["rows_written"] = int(state["run"].get("rows_written") or 0) + int(kwargs.get("rows_written_delta") or 0)
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
            sync_worker.sync_run_chunks_store,
            "list_sync_run_chunks",
            return_value=[
                {
                    "chunk_index": 0,
                    "status": "done",
                    "metadata": {
                        "rows_downloaded": 0,
                        "rows_mapped": 0,
                        "zero_row_observability": [{"zero_row_marker": "provider_returned_empty_list"}],
                    },
                }
            ],
        ), patch.object(
            sync_worker.client_registry_service,
            "update_platform_account_operational_metadata",
            side_effect=lambda **kwargs: metadata_calls.append(kwargs) or kwargs,
        ), patch.object(
            sync_worker.tiktok_ads_service,
            "sync_client",
            return_value={
                "rows_written": 0,
                "rows_downloaded": 0,
                "provider_row_count": 0,
                "rows_mapped": 0,
                "zero_row_observability": [{"zero_row_marker": "provider_returned_empty_list"}],
            },
        ), patch.object(
            sync_worker.sync_runs_store,
            "cleanup_superseded_tiktok_failed_runs",
            side_effect=lambda **kwargs: cleanup_calls.append(kwargs) or {"deleted_runs": 0, "deleted_chunks": 0, "superseded_run_count": 0},
        ):
            processed = sync_worker.process_next_chunk()

        self.assertTrue(processed)
        self.assertEqual(state["run"]["status"], "done")
        self.assertEqual(len(metadata_calls), 1)
        self.assertNotIn("backfill_completed_through", metadata_calls[0])
        run_metadata = state["run"].get("metadata") or {}
        self.assertTrue(bool(run_metadata.get("no_data_success")))
        self.assertEqual(run_metadata.get("zero_row_marker"), "provider_returned_empty_list")
        self.assertEqual(cleanup_calls, [{"account_ids": ["3986597205"]}])



    def test_tiktok_historical_parser_failure_marks_run_error_and_does_not_advance_backfill(self):
        state = self._build_state(job_type="historical_backfill", platform="tiktok_ads")

        metadata_calls = []

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
                state["run"]["error"] = kwargs.get("error")
            if isinstance(kwargs.get("metadata"), dict):
                existing = state["run"].get("metadata") if isinstance(state["run"].get("metadata"), dict) else {}
                merged = dict(existing)
                merged.update(kwargs.get("metadata") or {})
                state["run"]["metadata"] = merged
            return dict(state["run"])

        def _update_chunk_status(**kwargs):
            state["chunk"]["status"] = kwargs["status"]
            if kwargs.get("metadata") is not None:
                state["chunk"]["metadata"] = kwargs.get("metadata") or {}
            return dict(state["chunk"])

        def _update_progress(**kwargs):
            state["run"]["chunks_done"] = int(state["run"].get("chunks_done") or 0) + int(kwargs.get("chunks_done_delta") or 0)
            state["run"]["rows_written"] = int(state["run"].get("rows_written") or 0) + int(kwargs.get("rows_written_delta") or 0)
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
            sync_worker.sync_run_chunks_store,
            "list_sync_run_chunks",
            return_value=[
                {
                    "chunk_index": 0,
                    "status": "done",
                    "metadata": {
                        "rows_downloaded": 30,
                        "rows_mapped": 0,
                        "zero_row_observability": [{"zero_row_marker": "response_parsed_but_zero_rows_mapped"}],
                    },
                }
            ],
        ), patch.object(
            sync_worker.client_registry_service,
            "update_platform_account_operational_metadata",
            side_effect=lambda **kwargs: metadata_calls.append(kwargs) or kwargs,
        ), patch.object(
            sync_worker.tiktok_ads_service,
            "sync_client",
            return_value={
                "rows_written": 0,
                "rows_downloaded": 30,
                "provider_row_count": 30,
                "rows_mapped": 0,
                "zero_row_observability": [{"zero_row_marker": "response_parsed_but_zero_rows_mapped"}],
            },
        ):
            processed = sync_worker.process_next_chunk()

        self.assertTrue(processed)
        self.assertEqual(state["run"]["status"], "error")
        self.assertEqual(len(metadata_calls), 1)
        self.assertNotIn("backfill_completed_through", metadata_calls[0])
        self.assertNotIn("last_success_at", metadata_calls[0])
        self.assertIn("parser_failure", str(metadata_calls[0].get("last_error") or ""))
        run_metadata = state["run"].get("metadata") or {}
        self.assertTrue(bool(run_metadata.get("parser_failure")))

    def test_tiktok_historical_empty_success_does_not_advance_backfill_coverage(self):
        state = self._build_state(job_type="historical_backfill", platform="tiktok_ads")

        metadata_calls = []
        cleanup_calls = []

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
            if isinstance(kwargs.get("metadata"), dict):
                existing = state["run"].get("metadata") if isinstance(state["run"].get("metadata"), dict) else {}
                merged = dict(existing)
                merged.update(kwargs.get("metadata") or {})
                state["run"]["metadata"] = merged
            return dict(state["run"])

        def _update_chunk_status(**kwargs):
            state["chunk"]["status"] = kwargs["status"]
            if kwargs.get("metadata") is not None:
                state["chunk"]["metadata"] = kwargs.get("metadata") or {}
            return dict(state["chunk"])

        def _update_progress(**kwargs):
            state["run"]["chunks_done"] = int(state["run"].get("chunks_done") or 0) + int(kwargs.get("chunks_done_delta") or 0)
            state["run"]["rows_written"] = int(state["run"].get("rows_written") or 0) + int(kwargs.get("rows_written_delta") or 0)
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
            sync_worker.sync_run_chunks_store,
            "list_sync_run_chunks",
            return_value=[
                {
                    "chunk_index": 0,
                    "status": "done",
                    "metadata": {
                        "rows_downloaded": 0,
                        "rows_mapped": 0,
                        "zero_row_observability": [{"zero_row_marker": "provider_returned_empty_list"}],
                    },
                }
            ],
        ), patch.object(
            sync_worker.client_registry_service,
            "update_platform_account_operational_metadata",
            side_effect=lambda **kwargs: metadata_calls.append(kwargs) or kwargs,
        ), patch.object(
            sync_worker.tiktok_ads_service,
            "sync_client",
            return_value={
                "rows_written": 0,
                "rows_downloaded": 0,
                "provider_row_count": 0,
                "rows_mapped": 0,
                "zero_row_observability": [{"zero_row_marker": "provider_returned_empty_list"}],
            },
        ), patch.object(
            sync_worker.sync_runs_store,
            "cleanup_superseded_tiktok_failed_runs",
            side_effect=lambda **kwargs: cleanup_calls.append(kwargs) or {"deleted_runs": 0, "deleted_chunks": 0, "superseded_run_count": 0},
        ):
            processed = sync_worker.process_next_chunk()

        self.assertTrue(processed)
        self.assertEqual(state["run"]["status"], "done")
        self.assertEqual(len(metadata_calls), 1)
        self.assertNotIn("backfill_completed_through", metadata_calls[0])
        run_metadata = state["run"].get("metadata") or {}
        self.assertTrue(bool(run_metadata.get("no_data_success")))
        self.assertEqual(run_metadata.get("zero_row_marker"), "provider_returned_empty_list")
        self.assertEqual(cleanup_calls, [{"account_ids": ["3986597205"]}])



    def test_tiktok_historical_parser_failure_marks_run_error_and_does_not_advance_backfill(self):
        state = self._build_state(job_type="historical_backfill", platform="tiktok_ads")

        metadata_calls = []

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
                state["run"]["error"] = kwargs.get("error")
            if isinstance(kwargs.get("metadata"), dict):
                existing = state["run"].get("metadata") if isinstance(state["run"].get("metadata"), dict) else {}
                merged = dict(existing)
                merged.update(kwargs.get("metadata") or {})
                state["run"]["metadata"] = merged
            return dict(state["run"])

        def _update_chunk_status(**kwargs):
            state["chunk"]["status"] = kwargs["status"]
            if kwargs.get("metadata") is not None:
                state["chunk"]["metadata"] = kwargs.get("metadata") or {}
            return dict(state["chunk"])

        def _update_progress(**kwargs):
            state["run"]["chunks_done"] = int(state["run"].get("chunks_done") or 0) + int(kwargs.get("chunks_done_delta") or 0)
            state["run"]["rows_written"] = int(state["run"].get("rows_written") or 0) + int(kwargs.get("rows_written_delta") or 0)
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
            sync_worker.sync_run_chunks_store,
            "list_sync_run_chunks",
            return_value=[
                {
                    "chunk_index": 0,
                    "status": "done",
                    "metadata": {
                        "rows_downloaded": 30,
                        "rows_mapped": 0,
                        "zero_row_observability": [{"zero_row_marker": "response_parsed_but_zero_rows_mapped"}],
                    },
                }
            ],
        ), patch.object(
            sync_worker.client_registry_service,
            "update_platform_account_operational_metadata",
            side_effect=lambda **kwargs: metadata_calls.append(kwargs) or kwargs,
        ), patch.object(
            sync_worker.tiktok_ads_service,
            "sync_client",
            return_value={
                "rows_written": 0,
                "rows_downloaded": 30,
                "provider_row_count": 30,
                "rows_mapped": 0,
                "zero_row_observability": [{"zero_row_marker": "response_parsed_but_zero_rows_mapped"}],
            },
        ):
            processed = sync_worker.process_next_chunk()

        self.assertTrue(processed)
        self.assertEqual(state["run"]["status"], "error")
        self.assertEqual(len(metadata_calls), 1)
        self.assertNotIn("backfill_completed_through", metadata_calls[0])
        self.assertNotIn("last_success_at", metadata_calls[0])
        self.assertIn("parser_failure", str(metadata_calls[0].get("last_error") or ""))
        run_metadata = state["run"].get("metadata") or {}
        self.assertTrue(bool(run_metadata.get("parser_failure")))

    def test_tiktok_historical_empty_success_does_not_advance_backfill_coverage(self):
        state = self._build_state(job_type="historical_backfill", platform="tiktok_ads")

        metadata_calls = []
        cleanup_calls = []

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
            if isinstance(kwargs.get("metadata"), dict):
                existing = state["run"].get("metadata") if isinstance(state["run"].get("metadata"), dict) else {}
                merged = dict(existing)
                merged.update(kwargs.get("metadata") or {})
                state["run"]["metadata"] = merged
            return dict(state["run"])

        def _update_chunk_status(**kwargs):
            state["chunk"]["status"] = kwargs["status"]
            if kwargs.get("metadata") is not None:
                state["chunk"]["metadata"] = kwargs.get("metadata") or {}
            return dict(state["chunk"])

        def _update_progress(**kwargs):
            state["run"]["chunks_done"] = int(state["run"].get("chunks_done") or 0) + int(kwargs.get("chunks_done_delta") or 0)
            state["run"]["rows_written"] = int(state["run"].get("rows_written") or 0) + int(kwargs.get("rows_written_delta") or 0)
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
            sync_worker.sync_run_chunks_store,
            "list_sync_run_chunks",
            return_value=[
                {
                    "chunk_index": 0,
                    "status": "done",
                    "metadata": {
                        "rows_downloaded": 0,
                        "rows_mapped": 0,
                        "zero_row_observability": [{"zero_row_marker": "provider_returned_empty_list"}],
                    },
                }
            ],
        ), patch.object(
            sync_worker.client_registry_service,
            "update_platform_account_operational_metadata",
            side_effect=lambda **kwargs: metadata_calls.append(kwargs) or kwargs,
        ), patch.object(
            sync_worker.tiktok_ads_service,
            "sync_client",
            return_value={
                "rows_written": 0,
                "rows_downloaded": 0,
                "provider_row_count": 0,
                "rows_mapped": 0,
                "zero_row_observability": [{"zero_row_marker": "provider_returned_empty_list"}],
            },
        ), patch.object(
            sync_worker.sync_runs_store,
            "cleanup_superseded_tiktok_failed_runs",
            side_effect=lambda **kwargs: cleanup_calls.append(kwargs) or {"deleted_runs": 0, "deleted_chunks": 0, "superseded_run_count": 0},
        ):
            processed = sync_worker.process_next_chunk()

        self.assertTrue(processed)
        self.assertEqual(state["run"]["status"], "done")
        self.assertEqual(len(metadata_calls), 1)
        self.assertNotIn("backfill_completed_through", metadata_calls[0])
        run_metadata = state["run"].get("metadata") or {}
        self.assertTrue(bool(run_metadata.get("no_data_success")))
        self.assertEqual(run_metadata.get("zero_row_marker"), "provider_returned_empty_list")
        self.assertEqual(cleanup_calls, [{"account_ids": ["3986597205"]}])



    def test_tiktok_historical_parser_failure_marks_run_error_and_does_not_advance_backfill(self):
        state = self._build_state(job_type="historical_backfill", platform="tiktok_ads")

        metadata_calls = []

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
                state["run"]["error"] = kwargs.get("error")
            if isinstance(kwargs.get("metadata"), dict):
                existing = state["run"].get("metadata") if isinstance(state["run"].get("metadata"), dict) else {}
                merged = dict(existing)
                merged.update(kwargs.get("metadata") or {})
                state["run"]["metadata"] = merged
            return dict(state["run"])

        def _update_chunk_status(**kwargs):
            state["chunk"]["status"] = kwargs["status"]
            if kwargs.get("metadata") is not None:
                state["chunk"]["metadata"] = kwargs.get("metadata") or {}
            return dict(state["chunk"])

        def _update_progress(**kwargs):
            state["run"]["chunks_done"] = int(state["run"].get("chunks_done") or 0) + int(kwargs.get("chunks_done_delta") or 0)
            state["run"]["rows_written"] = int(state["run"].get("rows_written") or 0) + int(kwargs.get("rows_written_delta") or 0)
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
            sync_worker.sync_run_chunks_store,
            "list_sync_run_chunks",
            return_value=[
                {
                    "chunk_index": 0,
                    "status": "done",
                    "metadata": {
                        "rows_downloaded": 30,
                        "rows_mapped": 0,
                        "zero_row_observability": [{"zero_row_marker": "response_parsed_but_zero_rows_mapped"}],
                    },
                }
            ],
        ), patch.object(
            sync_worker.client_registry_service,
            "update_platform_account_operational_metadata",
            side_effect=lambda **kwargs: metadata_calls.append(kwargs) or kwargs,
        ), patch.object(
            sync_worker.tiktok_ads_service,
            "sync_client",
            return_value={
                "rows_written": 0,
                "rows_downloaded": 30,
                "provider_row_count": 30,
                "rows_mapped": 0,
                "zero_row_observability": [{"zero_row_marker": "response_parsed_but_zero_rows_mapped"}],
            },
        ):
            processed = sync_worker.process_next_chunk()

        self.assertTrue(processed)
        self.assertEqual(state["run"]["status"], "error")
        self.assertEqual(len(metadata_calls), 1)
        self.assertNotIn("backfill_completed_through", metadata_calls[0])
        self.assertNotIn("last_success_at", metadata_calls[0])
        self.assertIn("parser_failure", str(metadata_calls[0].get("last_error") or ""))
        run_metadata = state["run"].get("metadata") or {}
        self.assertTrue(bool(run_metadata.get("parser_failure")))

    def test_tiktok_historical_empty_success_does_not_advance_backfill_coverage(self):
        state = self._build_state(job_type="historical_backfill", platform="tiktok_ads")

        metadata_calls = []
        cleanup_calls = []

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
            if isinstance(kwargs.get("metadata"), dict):
                existing = state["run"].get("metadata") if isinstance(state["run"].get("metadata"), dict) else {}
                merged = dict(existing)
                merged.update(kwargs.get("metadata") or {})
                state["run"]["metadata"] = merged
            return dict(state["run"])

        def _update_chunk_status(**kwargs):
            state["chunk"]["status"] = kwargs["status"]
            if kwargs.get("metadata") is not None:
                state["chunk"]["metadata"] = kwargs.get("metadata") or {}
            return dict(state["chunk"])

        def _update_progress(**kwargs):
            state["run"]["chunks_done"] = int(state["run"].get("chunks_done") or 0) + int(kwargs.get("chunks_done_delta") or 0)
            state["run"]["rows_written"] = int(state["run"].get("rows_written") or 0) + int(kwargs.get("rows_written_delta") or 0)
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
            sync_worker.sync_run_chunks_store,
            "list_sync_run_chunks",
            return_value=[
                {
                    "chunk_index": 0,
                    "status": "done",
                    "metadata": {
                        "rows_downloaded": 0,
                        "rows_mapped": 0,
                        "zero_row_observability": [{"zero_row_marker": "provider_returned_empty_list"}],
                    },
                }
            ],
        ), patch.object(
            sync_worker.client_registry_service,
            "update_platform_account_operational_metadata",
            side_effect=lambda **kwargs: metadata_calls.append(kwargs) or kwargs,
        ), patch.object(
            sync_worker.tiktok_ads_service,
            "sync_client",
            return_value={
                "rows_written": 0,
                "rows_downloaded": 0,
                "provider_row_count": 0,
                "rows_mapped": 0,
                "zero_row_observability": [{"zero_row_marker": "provider_returned_empty_list"}],
            },
        ), patch.object(
            sync_worker.sync_runs_store,
            "cleanup_superseded_tiktok_failed_runs",
            side_effect=lambda **kwargs: cleanup_calls.append(kwargs) or {"deleted_runs": 0, "deleted_chunks": 0, "superseded_run_count": 0},
        ):
            processed = sync_worker.process_next_chunk()

        self.assertTrue(processed)
        self.assertEqual(state["run"]["status"], "done")
        self.assertEqual(len(metadata_calls), 1)
        self.assertNotIn("backfill_completed_through", metadata_calls[0])
        run_metadata = state["run"].get("metadata") or {}
        self.assertTrue(bool(run_metadata.get("no_data_success")))
        self.assertEqual(run_metadata.get("zero_row_marker"), "provider_returned_empty_list")
        self.assertEqual(cleanup_calls, [{"account_ids": ["3986597205"]}])



    def test_tiktok_historical_parser_failure_marks_run_error_and_does_not_advance_backfill(self):
        state = self._build_state(job_type="historical_backfill", platform="tiktok_ads")

        metadata_calls = []

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
                state["run"]["error"] = kwargs.get("error")
            if isinstance(kwargs.get("metadata"), dict):
                existing = state["run"].get("metadata") if isinstance(state["run"].get("metadata"), dict) else {}
                merged = dict(existing)
                merged.update(kwargs.get("metadata") or {})
                state["run"]["metadata"] = merged
            return dict(state["run"])

        def _update_chunk_status(**kwargs):
            state["chunk"]["status"] = kwargs["status"]
            if kwargs.get("metadata") is not None:
                state["chunk"]["metadata"] = kwargs.get("metadata") or {}
            return dict(state["chunk"])

        def _update_progress(**kwargs):
            state["run"]["chunks_done"] = int(state["run"].get("chunks_done") or 0) + int(kwargs.get("chunks_done_delta") or 0)
            state["run"]["rows_written"] = int(state["run"].get("rows_written") or 0) + int(kwargs.get("rows_written_delta") or 0)
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
            sync_worker.sync_run_chunks_store,
            "list_sync_run_chunks",
            return_value=[
                {
                    "chunk_index": 0,
                    "status": "done",
                    "metadata": {
                        "rows_downloaded": 30,
                        "rows_mapped": 0,
                        "zero_row_observability": [{"zero_row_marker": "response_parsed_but_zero_rows_mapped"}],
                    },
                }
            ],
        ), patch.object(
            sync_worker.client_registry_service,
            "update_platform_account_operational_metadata",
            side_effect=lambda **kwargs: metadata_calls.append(kwargs) or kwargs,
        ), patch.object(
            sync_worker.tiktok_ads_service,
            "sync_client",
            return_value={
                "rows_written": 0,
                "rows_downloaded": 30,
                "provider_row_count": 30,
                "rows_mapped": 0,
                "zero_row_observability": [{"zero_row_marker": "response_parsed_but_zero_rows_mapped"}],
            },
        ):
            processed = sync_worker.process_next_chunk()

        self.assertTrue(processed)
        self.assertEqual(state["run"]["status"], "error")
        self.assertEqual(len(metadata_calls), 1)
        self.assertNotIn("backfill_completed_through", metadata_calls[0])
        self.assertNotIn("last_success_at", metadata_calls[0])
        self.assertIn("parser_failure", str(metadata_calls[0].get("last_error") or ""))
        run_metadata = state["run"].get("metadata") or {}
        self.assertTrue(bool(run_metadata.get("parser_failure")))

    def test_tiktok_historical_empty_success_does_not_advance_backfill_coverage(self):
        state = self._build_state(job_type="historical_backfill", platform="tiktok_ads")

        metadata_calls = []
        cleanup_calls = []

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
            if isinstance(kwargs.get("metadata"), dict):
                existing = state["run"].get("metadata") if isinstance(state["run"].get("metadata"), dict) else {}
                merged = dict(existing)
                merged.update(kwargs.get("metadata") or {})
                state["run"]["metadata"] = merged
            return dict(state["run"])

        def _update_chunk_status(**kwargs):
            state["chunk"]["status"] = kwargs["status"]
            if kwargs.get("metadata") is not None:
                state["chunk"]["metadata"] = kwargs.get("metadata") or {}
            return dict(state["chunk"])

        def _update_progress(**kwargs):
            state["run"]["chunks_done"] = int(state["run"].get("chunks_done") or 0) + int(kwargs.get("chunks_done_delta") or 0)
            state["run"]["rows_written"] = int(state["run"].get("rows_written") or 0) + int(kwargs.get("rows_written_delta") or 0)
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
            sync_worker.sync_run_chunks_store,
            "list_sync_run_chunks",
            return_value=[
                {
                    "chunk_index": 0,
                    "status": "done",
                    "metadata": {
                        "rows_downloaded": 0,
                        "rows_mapped": 0,
                        "zero_row_observability": [{"zero_row_marker": "provider_returned_empty_list"}],
                    },
                }
            ],
        ), patch.object(
            sync_worker.client_registry_service,
            "update_platform_account_operational_metadata",
            side_effect=lambda **kwargs: metadata_calls.append(kwargs) or kwargs,
        ), patch.object(
            sync_worker.tiktok_ads_service,
            "sync_client",
            return_value={
                "rows_written": 0,
                "rows_downloaded": 0,
                "provider_row_count": 0,
                "rows_mapped": 0,
                "zero_row_observability": [{"zero_row_marker": "provider_returned_empty_list"}],
            },
        ), patch.object(
            sync_worker.sync_runs_store,
            "cleanup_superseded_tiktok_failed_runs",
            side_effect=lambda **kwargs: cleanup_calls.append(kwargs) or {"deleted_runs": 0, "deleted_chunks": 0, "superseded_run_count": 0},
        ):
            processed = sync_worker.process_next_chunk()

        self.assertTrue(processed)
        self.assertEqual(state["run"]["status"], "done")
        self.assertEqual(len(metadata_calls), 1)
        self.assertNotIn("backfill_completed_through", metadata_calls[0])
        run_metadata = state["run"].get("metadata") or {}
        self.assertTrue(bool(run_metadata.get("no_data_success")))
        self.assertEqual(run_metadata.get("zero_row_marker"), "provider_returned_empty_list")
        self.assertEqual(cleanup_calls, [{"account_ids": ["3986597205"]}])



    def test_tiktok_historical_parser_failure_marks_run_error_and_does_not_advance_backfill(self):
        state = self._build_state(job_type="historical_backfill", platform="tiktok_ads")

        metadata_calls = []

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
                state["run"]["error"] = kwargs.get("error")
            if isinstance(kwargs.get("metadata"), dict):
                existing = state["run"].get("metadata") if isinstance(state["run"].get("metadata"), dict) else {}
                merged = dict(existing)
                merged.update(kwargs.get("metadata") or {})
                state["run"]["metadata"] = merged
            return dict(state["run"])

        def _update_chunk_status(**kwargs):
            state["chunk"]["status"] = kwargs["status"]
            if kwargs.get("metadata") is not None:
                state["chunk"]["metadata"] = kwargs.get("metadata") or {}
            return dict(state["chunk"])

        def _update_progress(**kwargs):
            state["run"]["chunks_done"] = int(state["run"].get("chunks_done") or 0) + int(kwargs.get("chunks_done_delta") or 0)
            state["run"]["rows_written"] = int(state["run"].get("rows_written") or 0) + int(kwargs.get("rows_written_delta") or 0)
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
            sync_worker.sync_run_chunks_store,
            "list_sync_run_chunks",
            return_value=[
                {
                    "chunk_index": 0,
                    "status": "done",
                    "metadata": {
                        "rows_downloaded": 30,
                        "rows_mapped": 0,
                        "zero_row_observability": [{"zero_row_marker": "response_parsed_but_zero_rows_mapped"}],
                    },
                }
            ],
        ), patch.object(
            sync_worker.client_registry_service,
            "update_platform_account_operational_metadata",
            side_effect=lambda **kwargs: metadata_calls.append(kwargs) or kwargs,
        ), patch.object(
            sync_worker.tiktok_ads_service,
            "sync_client",
            return_value={
                "rows_written": 0,
                "rows_downloaded": 30,
                "provider_row_count": 30,
                "rows_mapped": 0,
                "zero_row_observability": [{"zero_row_marker": "response_parsed_but_zero_rows_mapped"}],
            },
        ):
            processed = sync_worker.process_next_chunk()

        self.assertTrue(processed)
        self.assertEqual(state["run"]["status"], "error")
        self.assertEqual(len(metadata_calls), 1)
        self.assertNotIn("backfill_completed_through", metadata_calls[0])
        self.assertNotIn("last_success_at", metadata_calls[0])
        self.assertIn("parser_failure", str(metadata_calls[0].get("last_error") or ""))
        run_metadata = state["run"].get("metadata") or {}
        self.assertTrue(bool(run_metadata.get("parser_failure")))

    def test_tiktok_historical_empty_success_does_not_advance_backfill_coverage(self):
        state = self._build_state(job_type="historical_backfill", platform="tiktok_ads")

        metadata_calls = []
        cleanup_calls = []

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
            if isinstance(kwargs.get("metadata"), dict):
                existing = state["run"].get("metadata") if isinstance(state["run"].get("metadata"), dict) else {}
                merged = dict(existing)
                merged.update(kwargs.get("metadata") or {})
                state["run"]["metadata"] = merged
            return dict(state["run"])

        def _update_chunk_status(**kwargs):
            state["chunk"]["status"] = kwargs["status"]
            if kwargs.get("metadata") is not None:
                state["chunk"]["metadata"] = kwargs.get("metadata") or {}
            return dict(state["chunk"])

        def _update_progress(**kwargs):
            state["run"]["chunks_done"] = int(state["run"].get("chunks_done") or 0) + int(kwargs.get("chunks_done_delta") or 0)
            state["run"]["rows_written"] = int(state["run"].get("rows_written") or 0) + int(kwargs.get("rows_written_delta") or 0)
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
            sync_worker.sync_run_chunks_store,
            "list_sync_run_chunks",
            return_value=[
                {
                    "chunk_index": 0,
                    "status": "done",
                    "metadata": {
                        "rows_downloaded": 0,
                        "rows_mapped": 0,
                        "zero_row_observability": [{"zero_row_marker": "provider_returned_empty_list"}],
                    },
                }
            ],
        ), patch.object(
            sync_worker.client_registry_service,
            "update_platform_account_operational_metadata",
            side_effect=lambda **kwargs: metadata_calls.append(kwargs) or kwargs,
        ), patch.object(
            sync_worker.tiktok_ads_service,
            "sync_client",
            return_value={
                "rows_written": 0,
                "rows_downloaded": 0,
                "provider_row_count": 0,
                "rows_mapped": 0,
                "zero_row_observability": [{"zero_row_marker": "provider_returned_empty_list"}],
            },
        ), patch.object(
            sync_worker.sync_runs_store,
            "cleanup_superseded_tiktok_failed_runs",
            side_effect=lambda **kwargs: cleanup_calls.append(kwargs) or {"deleted_runs": 0, "deleted_chunks": 0, "superseded_run_count": 0},
        ):
            processed = sync_worker.process_next_chunk()

        self.assertTrue(processed)
        self.assertEqual(state["run"]["status"], "done")
        self.assertEqual(len(metadata_calls), 1)
        self.assertNotIn("backfill_completed_through", metadata_calls[0])
        run_metadata = state["run"].get("metadata") or {}
        self.assertTrue(bool(run_metadata.get("no_data_success")))
        self.assertEqual(run_metadata.get("zero_row_marker"), "provider_returned_empty_list")
        self.assertEqual(cleanup_calls, [{"account_ids": ["3986597205"]}])



    def test_tiktok_historical_parser_failure_marks_run_error_and_does_not_advance_backfill(self):
        state = self._build_state(job_type="historical_backfill", platform="tiktok_ads")

        metadata_calls = []

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
                state["run"]["error"] = kwargs.get("error")
            if isinstance(kwargs.get("metadata"), dict):
                existing = state["run"].get("metadata") if isinstance(state["run"].get("metadata"), dict) else {}
                merged = dict(existing)
                merged.update(kwargs.get("metadata") or {})
                state["run"]["metadata"] = merged
            return dict(state["run"])

        def _update_chunk_status(**kwargs):
            state["chunk"]["status"] = kwargs["status"]
            if kwargs.get("metadata") is not None:
                state["chunk"]["metadata"] = kwargs.get("metadata") or {}
            return dict(state["chunk"])

        def _update_progress(**kwargs):
            state["run"]["chunks_done"] = int(state["run"].get("chunks_done") or 0) + int(kwargs.get("chunks_done_delta") or 0)
            state["run"]["rows_written"] = int(state["run"].get("rows_written") or 0) + int(kwargs.get("rows_written_delta") or 0)
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
            sync_worker.sync_run_chunks_store,
            "list_sync_run_chunks",
            return_value=[
                {
                    "chunk_index": 0,
                    "status": "done",
                    "metadata": {
                        "rows_downloaded": 30,
                        "rows_mapped": 0,
                        "zero_row_observability": [{"zero_row_marker": "response_parsed_but_zero_rows_mapped"}],
                    },
                }
            ],
        ), patch.object(
            sync_worker.client_registry_service,
            "update_platform_account_operational_metadata",
            side_effect=lambda **kwargs: metadata_calls.append(kwargs) or kwargs,
        ), patch.object(
            sync_worker.tiktok_ads_service,
            "sync_client",
            return_value={
                "rows_written": 0,
                "rows_downloaded": 30,
                "provider_row_count": 30,
                "rows_mapped": 0,
                "zero_row_observability": [{"zero_row_marker": "response_parsed_but_zero_rows_mapped"}],
            },
        ):
            processed = sync_worker.process_next_chunk()

        self.assertTrue(processed)
        self.assertEqual(state["run"]["status"], "error")
        self.assertEqual(len(metadata_calls), 1)
        self.assertNotIn("backfill_completed_through", metadata_calls[0])
        self.assertNotIn("last_success_at", metadata_calls[0])
        self.assertIn("parser_failure", str(metadata_calls[0].get("last_error") or ""))
        run_metadata = state["run"].get("metadata") or {}
        self.assertTrue(bool(run_metadata.get("parser_failure")))

    def test_tiktok_historical_empty_success_does_not_advance_backfill_coverage(self):
        state = self._build_state(job_type="historical_backfill", platform="tiktok_ads")

        metadata_calls = []
        cleanup_calls = []

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
            if isinstance(kwargs.get("metadata"), dict):
                existing = state["run"].get("metadata") if isinstance(state["run"].get("metadata"), dict) else {}
                merged = dict(existing)
                merged.update(kwargs.get("metadata") or {})
                state["run"]["metadata"] = merged
            return dict(state["run"])

        def _update_chunk_status(**kwargs):
            state["chunk"]["status"] = kwargs["status"]
            if kwargs.get("metadata") is not None:
                state["chunk"]["metadata"] = kwargs.get("metadata") or {}
            return dict(state["chunk"])

        def _update_progress(**kwargs):
            state["run"]["chunks_done"] = int(state["run"].get("chunks_done") or 0) + int(kwargs.get("chunks_done_delta") or 0)
            state["run"]["rows_written"] = int(state["run"].get("rows_written") or 0) + int(kwargs.get("rows_written_delta") or 0)
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
            sync_worker.sync_run_chunks_store,
            "list_sync_run_chunks",
            return_value=[
                {
                    "chunk_index": 0,
                    "status": "done",
                    "metadata": {
                        "rows_downloaded": 0,
                        "rows_mapped": 0,
                        "zero_row_observability": [{"zero_row_marker": "provider_returned_empty_list"}],
                    },
                }
            ],
        ), patch.object(
            sync_worker.client_registry_service,
            "update_platform_account_operational_metadata",
            side_effect=lambda **kwargs: metadata_calls.append(kwargs) or kwargs,
        ), patch.object(
            sync_worker.tiktok_ads_service,
            "sync_client",
            return_value={
                "rows_written": 0,
                "rows_downloaded": 0,
                "provider_row_count": 0,
                "rows_mapped": 0,
                "zero_row_observability": [{"zero_row_marker": "provider_returned_empty_list"}],
            },
        ), patch.object(
            sync_worker.sync_runs_store,
            "cleanup_superseded_tiktok_failed_runs",
            side_effect=lambda **kwargs: cleanup_calls.append(kwargs) or {"deleted_runs": 0, "deleted_chunks": 0, "superseded_run_count": 0},
        ):
            processed = sync_worker.process_next_chunk()

        self.assertTrue(processed)
        self.assertEqual(state["run"]["status"], "done")
        self.assertEqual(len(metadata_calls), 1)
        self.assertNotIn("backfill_completed_through", metadata_calls[0])
        run_metadata = state["run"].get("metadata") or {}
        self.assertTrue(bool(run_metadata.get("no_data_success")))
        self.assertEqual(run_metadata.get("zero_row_marker"), "provider_returned_empty_list")
        self.assertEqual(cleanup_calls, [{"account_ids": ["3986597205"]}])



    def test_tiktok_historical_parser_failure_marks_run_error_and_does_not_advance_backfill(self):
        state = self._build_state(job_type="historical_backfill", platform="tiktok_ads")

        metadata_calls = []

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
                state["run"]["error"] = kwargs.get("error")
            if isinstance(kwargs.get("metadata"), dict):
                existing = state["run"].get("metadata") if isinstance(state["run"].get("metadata"), dict) else {}
                merged = dict(existing)
                merged.update(kwargs.get("metadata") or {})
                state["run"]["metadata"] = merged
            return dict(state["run"])

        def _update_chunk_status(**kwargs):
            state["chunk"]["status"] = kwargs["status"]
            if kwargs.get("metadata") is not None:
                state["chunk"]["metadata"] = kwargs.get("metadata") or {}
            return dict(state["chunk"])

        def _update_progress(**kwargs):
            state["run"]["chunks_done"] = int(state["run"].get("chunks_done") or 0) + int(kwargs.get("chunks_done_delta") or 0)
            state["run"]["rows_written"] = int(state["run"].get("rows_written") or 0) + int(kwargs.get("rows_written_delta") or 0)
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
            sync_worker.sync_run_chunks_store,
            "list_sync_run_chunks",
            return_value=[
                {
                    "chunk_index": 0,
                    "status": "done",
                    "metadata": {
                        "rows_downloaded": 30,
                        "rows_mapped": 0,
                        "zero_row_observability": [{"zero_row_marker": "response_parsed_but_zero_rows_mapped"}],
                    },
                }
            ],
        ), patch.object(
            sync_worker.client_registry_service,
            "update_platform_account_operational_metadata",
            side_effect=lambda **kwargs: metadata_calls.append(kwargs) or kwargs,
        ), patch.object(
            sync_worker.tiktok_ads_service,
            "sync_client",
            return_value={
                "rows_written": 0,
                "rows_downloaded": 30,
                "provider_row_count": 30,
                "rows_mapped": 0,
                "zero_row_observability": [{"zero_row_marker": "response_parsed_but_zero_rows_mapped"}],
            },
        ):
            processed = sync_worker.process_next_chunk()

        self.assertTrue(processed)
        self.assertEqual(state["run"]["status"], "error")
        self.assertEqual(len(metadata_calls), 1)
        self.assertNotIn("backfill_completed_through", metadata_calls[0])
        self.assertNotIn("last_success_at", metadata_calls[0])
        self.assertIn("parser_failure", str(metadata_calls[0].get("last_error") or ""))
        run_metadata = state["run"].get("metadata") or {}
        self.assertTrue(bool(run_metadata.get("parser_failure")))

    def test_tiktok_historical_empty_success_does_not_advance_backfill_coverage(self):
        state = self._build_state(job_type="historical_backfill", platform="tiktok_ads")

        metadata_calls = []
        cleanup_calls = []

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
            if isinstance(kwargs.get("metadata"), dict):
                existing = state["run"].get("metadata") if isinstance(state["run"].get("metadata"), dict) else {}
                merged = dict(existing)
                merged.update(kwargs.get("metadata") or {})
                state["run"]["metadata"] = merged
            return dict(state["run"])

        def _update_chunk_status(**kwargs):
            state["chunk"]["status"] = kwargs["status"]
            if kwargs.get("metadata") is not None:
                state["chunk"]["metadata"] = kwargs.get("metadata") or {}
            return dict(state["chunk"])

        def _update_progress(**kwargs):
            state["run"]["chunks_done"] = int(state["run"].get("chunks_done") or 0) + int(kwargs.get("chunks_done_delta") or 0)
            state["run"]["rows_written"] = int(state["run"].get("rows_written") or 0) + int(kwargs.get("rows_written_delta") or 0)
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
            sync_worker.sync_run_chunks_store,
            "list_sync_run_chunks",
            return_value=[
                {
                    "chunk_index": 0,
                    "status": "done",
                    "metadata": {
                        "rows_downloaded": 0,
                        "rows_mapped": 0,
                        "zero_row_observability": [{"zero_row_marker": "provider_returned_empty_list"}],
                    },
                }
            ],
        ), patch.object(
            sync_worker.client_registry_service,
            "update_platform_account_operational_metadata",
            side_effect=lambda **kwargs: metadata_calls.append(kwargs) or kwargs,
        ), patch.object(
            sync_worker.tiktok_ads_service,
            "sync_client",
            return_value={
                "rows_written": 0,
                "rows_downloaded": 0,
                "provider_row_count": 0,
                "rows_mapped": 0,
                "zero_row_observability": [{"zero_row_marker": "provider_returned_empty_list"}],
            },
        ), patch.object(
            sync_worker.sync_runs_store,
            "cleanup_superseded_tiktok_failed_runs",
            side_effect=lambda **kwargs: cleanup_calls.append(kwargs) or {"deleted_runs": 0, "deleted_chunks": 0, "superseded_run_count": 0},
        ):
            processed = sync_worker.process_next_chunk()

        self.assertTrue(processed)
        self.assertEqual(state["run"]["status"], "done")
        self.assertEqual(len(metadata_calls), 1)
        self.assertNotIn("backfill_completed_through", metadata_calls[0])
        run_metadata = state["run"].get("metadata") or {}
        self.assertTrue(bool(run_metadata.get("no_data_success")))
        self.assertEqual(run_metadata.get("zero_row_marker"), "provider_returned_empty_list")
        self.assertEqual(cleanup_calls, [{"account_ids": ["3986597205"]}])



    def test_tiktok_historical_parser_failure_marks_run_error_and_does_not_advance_backfill(self):
        state = self._build_state(job_type="historical_backfill", platform="tiktok_ads")

        metadata_calls = []

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
                state["run"]["error"] = kwargs.get("error")
            if isinstance(kwargs.get("metadata"), dict):
                existing = state["run"].get("metadata") if isinstance(state["run"].get("metadata"), dict) else {}
                merged = dict(existing)
                merged.update(kwargs.get("metadata") or {})
                state["run"]["metadata"] = merged
            return dict(state["run"])

        def _update_chunk_status(**kwargs):
            state["chunk"]["status"] = kwargs["status"]
            if kwargs.get("metadata") is not None:
                state["chunk"]["metadata"] = kwargs.get("metadata") or {}
            return dict(state["chunk"])

        def _update_progress(**kwargs):
            state["run"]["chunks_done"] = int(state["run"].get("chunks_done") or 0) + int(kwargs.get("chunks_done_delta") or 0)
            state["run"]["rows_written"] = int(state["run"].get("rows_written") or 0) + int(kwargs.get("rows_written_delta") or 0)
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
            sync_worker.sync_run_chunks_store,
            "list_sync_run_chunks",
            return_value=[
                {
                    "chunk_index": 0,
                    "status": "done",
                    "metadata": {
                        "rows_downloaded": 30,
                        "rows_mapped": 0,
                        "zero_row_observability": [{"zero_row_marker": "response_parsed_but_zero_rows_mapped"}],
                    },
                }
            ],
        ), patch.object(
            sync_worker.client_registry_service,
            "update_platform_account_operational_metadata",
            side_effect=lambda **kwargs: metadata_calls.append(kwargs) or kwargs,
        ), patch.object(
            sync_worker.tiktok_ads_service,
            "sync_client",
            return_value={
                "rows_written": 0,
                "rows_downloaded": 30,
                "provider_row_count": 30,
                "rows_mapped": 0,
                "zero_row_observability": [{"zero_row_marker": "response_parsed_but_zero_rows_mapped"}],
            },
        ):
            processed = sync_worker.process_next_chunk()

        self.assertTrue(processed)
        self.assertEqual(state["run"]["status"], "error")
        self.assertEqual(len(metadata_calls), 1)
        self.assertNotIn("backfill_completed_through", metadata_calls[0])
        self.assertNotIn("last_success_at", metadata_calls[0])
        self.assertIn("parser_failure", str(metadata_calls[0].get("last_error") or ""))
        run_metadata = state["run"].get("metadata") or {}
        self.assertTrue(bool(run_metadata.get("parser_failure")))

    def test_tiktok_historical_empty_success_does_not_advance_backfill_coverage(self):
        state = self._build_state(job_type="historical_backfill", platform="tiktok_ads")

        metadata_calls = []
        cleanup_calls = []

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
            if isinstance(kwargs.get("metadata"), dict):
                existing = state["run"].get("metadata") if isinstance(state["run"].get("metadata"), dict) else {}
                merged = dict(existing)
                merged.update(kwargs.get("metadata") or {})
                state["run"]["metadata"] = merged
            return dict(state["run"])

        def _update_chunk_status(**kwargs):
            state["chunk"]["status"] = kwargs["status"]
            if kwargs.get("metadata") is not None:
                state["chunk"]["metadata"] = kwargs.get("metadata") or {}
            return dict(state["chunk"])

        def _update_progress(**kwargs):
            state["run"]["chunks_done"] = int(state["run"].get("chunks_done") or 0) + int(kwargs.get("chunks_done_delta") or 0)
            state["run"]["rows_written"] = int(state["run"].get("rows_written") or 0) + int(kwargs.get("rows_written_delta") or 0)
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
            sync_worker.sync_run_chunks_store,
            "list_sync_run_chunks",
            return_value=[
                {
                    "chunk_index": 0,
                    "status": "done",
                    "metadata": {
                        "rows_downloaded": 0,
                        "rows_mapped": 0,
                        "zero_row_observability": [{"zero_row_marker": "provider_returned_empty_list"}],
                    },
                }
            ],
        ), patch.object(
            sync_worker.client_registry_service,
            "update_platform_account_operational_metadata",
            side_effect=lambda **kwargs: metadata_calls.append(kwargs) or kwargs,
        ), patch.object(
            sync_worker.tiktok_ads_service,
            "sync_client",
            return_value={
                "rows_written": 0,
                "rows_downloaded": 0,
                "provider_row_count": 0,
                "rows_mapped": 0,
                "zero_row_observability": [{"zero_row_marker": "provider_returned_empty_list"}],
            },
        ), patch.object(
            sync_worker.sync_runs_store,
            "cleanup_superseded_tiktok_failed_runs",
            side_effect=lambda **kwargs: cleanup_calls.append(kwargs) or {"deleted_runs": 0, "deleted_chunks": 0, "superseded_run_count": 0},
        ):
            processed = sync_worker.process_next_chunk()

        self.assertTrue(processed)
        self.assertEqual(state["run"]["status"], "done")
        self.assertEqual(len(metadata_calls), 1)
        self.assertNotIn("backfill_completed_through", metadata_calls[0])
        run_metadata = state["run"].get("metadata") or {}
        self.assertTrue(bool(run_metadata.get("no_data_success")))
        self.assertEqual(run_metadata.get("zero_row_marker"), "provider_returned_empty_list")
        self.assertEqual(cleanup_calls, [{"account_ids": ["3986597205"]}])



    def test_tiktok_historical_parser_failure_marks_run_error_and_does_not_advance_backfill(self):
        state = self._build_state(job_type="historical_backfill", platform="tiktok_ads")

        metadata_calls = []

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
                state["run"]["error"] = kwargs.get("error")
            if isinstance(kwargs.get("metadata"), dict):
                existing = state["run"].get("metadata") if isinstance(state["run"].get("metadata"), dict) else {}
                merged = dict(existing)
                merged.update(kwargs.get("metadata") or {})
                state["run"]["metadata"] = merged
            return dict(state["run"])

        def _update_chunk_status(**kwargs):
            state["chunk"]["status"] = kwargs["status"]
            if kwargs.get("metadata") is not None:
                state["chunk"]["metadata"] = kwargs.get("metadata") or {}
            return dict(state["chunk"])

        def _update_progress(**kwargs):
            state["run"]["chunks_done"] = int(state["run"].get("chunks_done") or 0) + int(kwargs.get("chunks_done_delta") or 0)
            state["run"]["rows_written"] = int(state["run"].get("rows_written") or 0) + int(kwargs.get("rows_written_delta") or 0)
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
            sync_worker.sync_run_chunks_store,
            "list_sync_run_chunks",
            return_value=[
                {
                    "chunk_index": 0,
                    "status": "done",
                    "metadata": {
                        "rows_downloaded": 30,
                        "rows_mapped": 0,
                        "zero_row_observability": [{"zero_row_marker": "response_parsed_but_zero_rows_mapped"}],
                    },
                }
            ],
        ), patch.object(
            sync_worker.client_registry_service,
            "update_platform_account_operational_metadata",
            side_effect=lambda **kwargs: metadata_calls.append(kwargs) or kwargs,
        ), patch.object(
            sync_worker.tiktok_ads_service,
            "sync_client",
            return_value={
                "rows_written": 0,
                "rows_downloaded": 30,
                "provider_row_count": 30,
                "rows_mapped": 0,
                "zero_row_observability": [{"zero_row_marker": "response_parsed_but_zero_rows_mapped"}],
            },
        ):
            processed = sync_worker.process_next_chunk()

        self.assertTrue(processed)
        self.assertEqual(state["run"]["status"], "error")
        self.assertEqual(len(metadata_calls), 1)
        self.assertNotIn("backfill_completed_through", metadata_calls[0])
        self.assertNotIn("last_success_at", metadata_calls[0])
        self.assertIn("parser_failure", str(metadata_calls[0].get("last_error") or ""))
        run_metadata = state["run"].get("metadata") or {}
        self.assertTrue(bool(run_metadata.get("parser_failure")))

    def test_tiktok_historical_empty_success_does_not_advance_backfill_coverage(self):
        state = self._build_state(job_type="historical_backfill", platform="tiktok_ads")

        metadata_calls = []
        cleanup_calls = []

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
            if isinstance(kwargs.get("metadata"), dict):
                existing = state["run"].get("metadata") if isinstance(state["run"].get("metadata"), dict) else {}
                merged = dict(existing)
                merged.update(kwargs.get("metadata") or {})
                state["run"]["metadata"] = merged
            return dict(state["run"])

        def _update_chunk_status(**kwargs):
            state["chunk"]["status"] = kwargs["status"]
            if kwargs.get("metadata") is not None:
                state["chunk"]["metadata"] = kwargs.get("metadata") or {}
            return dict(state["chunk"])

        def _update_progress(**kwargs):
            state["run"]["chunks_done"] = int(state["run"].get("chunks_done") or 0) + int(kwargs.get("chunks_done_delta") or 0)
            state["run"]["rows_written"] = int(state["run"].get("rows_written") or 0) + int(kwargs.get("rows_written_delta") or 0)
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
            sync_worker.sync_run_chunks_store,
            "list_sync_run_chunks",
            return_value=[
                {
                    "chunk_index": 0,
                    "status": "done",
                    "metadata": {
                        "rows_downloaded": 0,
                        "rows_mapped": 0,
                        "zero_row_observability": [{"zero_row_marker": "provider_returned_empty_list"}],
                    },
                }
            ],
        ), patch.object(
            sync_worker.client_registry_service,
            "update_platform_account_operational_metadata",
            side_effect=lambda **kwargs: metadata_calls.append(kwargs) or kwargs,
        ), patch.object(
            sync_worker.tiktok_ads_service,
            "sync_client",
            return_value={
                "rows_written": 0,
                "rows_downloaded": 0,
                "provider_row_count": 0,
                "rows_mapped": 0,
                "zero_row_observability": [{"zero_row_marker": "provider_returned_empty_list"}],
            },
        ), patch.object(
            sync_worker.sync_runs_store,
            "cleanup_superseded_tiktok_failed_runs",
            side_effect=lambda **kwargs: cleanup_calls.append(kwargs) or {"deleted_runs": 0, "deleted_chunks": 0, "superseded_run_count": 0},
        ):
            processed = sync_worker.process_next_chunk()

        self.assertTrue(processed)
        self.assertEqual(state["run"]["status"], "done")
        self.assertEqual(len(metadata_calls), 1)
        self.assertNotIn("backfill_completed_through", metadata_calls[0])
        run_metadata = state["run"].get("metadata") or {}
        self.assertTrue(bool(run_metadata.get("no_data_success")))
        self.assertEqual(run_metadata.get("zero_row_marker"), "provider_returned_empty_list")
        self.assertEqual(cleanup_calls, [{"account_ids": ["3986597205"]}])



    def test_tiktok_historical_parser_failure_marks_run_error_and_does_not_advance_backfill(self):
        state = self._build_state(job_type="historical_backfill", platform="tiktok_ads")

        metadata_calls = []

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
                state["run"]["error"] = kwargs.get("error")
            if isinstance(kwargs.get("metadata"), dict):
                existing = state["run"].get("metadata") if isinstance(state["run"].get("metadata"), dict) else {}
                merged = dict(existing)
                merged.update(kwargs.get("metadata") or {})
                state["run"]["metadata"] = merged
            return dict(state["run"])

        def _update_chunk_status(**kwargs):
            state["chunk"]["status"] = kwargs["status"]
            if kwargs.get("metadata") is not None:
                state["chunk"]["metadata"] = kwargs.get("metadata") or {}
            return dict(state["chunk"])

        def _update_progress(**kwargs):
            state["run"]["chunks_done"] = int(state["run"].get("chunks_done") or 0) + int(kwargs.get("chunks_done_delta") or 0)
            state["run"]["rows_written"] = int(state["run"].get("rows_written") or 0) + int(kwargs.get("rows_written_delta") or 0)
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
            sync_worker.sync_run_chunks_store,
            "list_sync_run_chunks",
            return_value=[
                {
                    "chunk_index": 0,
                    "status": "done",
                    "metadata": {
                        "rows_downloaded": 30,
                        "rows_mapped": 0,
                        "zero_row_observability": [{"zero_row_marker": "response_parsed_but_zero_rows_mapped"}],
                    },
                }
            ],
        ), patch.object(
            sync_worker.client_registry_service,
            "update_platform_account_operational_metadata",
            side_effect=lambda **kwargs: metadata_calls.append(kwargs) or kwargs,
        ), patch.object(
            sync_worker.tiktok_ads_service,
            "sync_client",
            return_value={
                "rows_written": 0,
                "rows_downloaded": 30,
                "provider_row_count": 30,
                "rows_mapped": 0,
                "zero_row_observability": [{"zero_row_marker": "response_parsed_but_zero_rows_mapped"}],
            },
        ):
            processed = sync_worker.process_next_chunk()

        self.assertTrue(processed)
        self.assertEqual(state["run"]["status"], "error")
        self.assertEqual(len(metadata_calls), 1)
        self.assertNotIn("backfill_completed_through", metadata_calls[0])
        self.assertNotIn("last_success_at", metadata_calls[0])
        self.assertIn("parser_failure", str(metadata_calls[0].get("last_error") or ""))
        run_metadata = state["run"].get("metadata") or {}
        self.assertTrue(bool(run_metadata.get("parser_failure")))

    def test_tiktok_historical_empty_success_does_not_advance_backfill_coverage(self):
        state = self._build_state(job_type="historical_backfill", platform="tiktok_ads")

        metadata_calls = []
        cleanup_calls = []

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
            if isinstance(kwargs.get("metadata"), dict):
                existing = state["run"].get("metadata") if isinstance(state["run"].get("metadata"), dict) else {}
                merged = dict(existing)
                merged.update(kwargs.get("metadata") or {})
                state["run"]["metadata"] = merged
            return dict(state["run"])

        def _update_chunk_status(**kwargs):
            state["chunk"]["status"] = kwargs["status"]
            if kwargs.get("metadata") is not None:
                state["chunk"]["metadata"] = kwargs.get("metadata") or {}
            return dict(state["chunk"])

        def _update_progress(**kwargs):
            state["run"]["chunks_done"] = int(state["run"].get("chunks_done") or 0) + int(kwargs.get("chunks_done_delta") or 0)
            state["run"]["rows_written"] = int(state["run"].get("rows_written") or 0) + int(kwargs.get("rows_written_delta") or 0)
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
            sync_worker.sync_run_chunks_store,
            "list_sync_run_chunks",
            return_value=[
                {
                    "chunk_index": 0,
                    "status": "done",
                    "metadata": {
                        "rows_downloaded": 0,
                        "rows_mapped": 0,
                        "zero_row_observability": [{"zero_row_marker": "provider_returned_empty_list"}],
                    },
                }
            ],
        ), patch.object(
            sync_worker.client_registry_service,
            "update_platform_account_operational_metadata",
            side_effect=lambda **kwargs: metadata_calls.append(kwargs) or kwargs,
        ), patch.object(
            sync_worker.tiktok_ads_service,
            "sync_client",
            return_value={
                "rows_written": 0,
                "rows_downloaded": 0,
                "provider_row_count": 0,
                "rows_mapped": 0,
                "zero_row_observability": [{"zero_row_marker": "provider_returned_empty_list"}],
            },
        ), patch.object(
            sync_worker.sync_runs_store,
            "cleanup_superseded_tiktok_failed_runs",
            side_effect=lambda **kwargs: cleanup_calls.append(kwargs) or {"deleted_runs": 0, "deleted_chunks": 0, "superseded_run_count": 0},
        ):
            processed = sync_worker.process_next_chunk()

        self.assertTrue(processed)
        self.assertEqual(state["run"]["status"], "done")
        self.assertEqual(len(metadata_calls), 1)
        self.assertNotIn("backfill_completed_through", metadata_calls[0])
        run_metadata = state["run"].get("metadata") or {}
        self.assertTrue(bool(run_metadata.get("no_data_success")))
        self.assertEqual(run_metadata.get("zero_row_marker"), "provider_returned_empty_list")
        self.assertEqual(cleanup_calls, [{"account_ids": ["3986597205"]}])



    def test_tiktok_historical_parser_failure_marks_run_error_and_does_not_advance_backfill(self):
        state = self._build_state(job_type="historical_backfill", platform="tiktok_ads")

        metadata_calls = []

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
                state["run"]["error"] = kwargs.get("error")
            if isinstance(kwargs.get("metadata"), dict):
                existing = state["run"].get("metadata") if isinstance(state["run"].get("metadata"), dict) else {}
                merged = dict(existing)
                merged.update(kwargs.get("metadata") or {})
                state["run"]["metadata"] = merged
            return dict(state["run"])

        def _update_chunk_status(**kwargs):
            state["chunk"]["status"] = kwargs["status"]
            if kwargs.get("metadata") is not None:
                state["chunk"]["metadata"] = kwargs.get("metadata") or {}
            return dict(state["chunk"])

        def _update_progress(**kwargs):
            state["run"]["chunks_done"] = int(state["run"].get("chunks_done") or 0) + int(kwargs.get("chunks_done_delta") or 0)
            state["run"]["rows_written"] = int(state["run"].get("rows_written") or 0) + int(kwargs.get("rows_written_delta") or 0)
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
            sync_worker.sync_run_chunks_store,
            "list_sync_run_chunks",
            return_value=[
                {
                    "chunk_index": 0,
                    "status": "done",
                    "metadata": {
                        "rows_downloaded": 30,
                        "rows_mapped": 0,
                        "zero_row_observability": [{"zero_row_marker": "response_parsed_but_zero_rows_mapped"}],
                    },
                }
            ],
        ), patch.object(
            sync_worker.client_registry_service,
            "update_platform_account_operational_metadata",
            side_effect=lambda **kwargs: metadata_calls.append(kwargs) or kwargs,
        ), patch.object(
            sync_worker.tiktok_ads_service,
            "sync_client",
            return_value={
                "rows_written": 0,
                "rows_downloaded": 30,
                "provider_row_count": 30,
                "rows_mapped": 0,
                "zero_row_observability": [{"zero_row_marker": "response_parsed_but_zero_rows_mapped"}],
            },
        ):
            processed = sync_worker.process_next_chunk()

        self.assertTrue(processed)
        self.assertEqual(state["run"]["status"], "error")
        self.assertEqual(len(metadata_calls), 1)
        self.assertNotIn("backfill_completed_through", metadata_calls[0])
        self.assertNotIn("last_success_at", metadata_calls[0])
        self.assertIn("parser_failure", str(metadata_calls[0].get("last_error") or ""))
        run_metadata = state["run"].get("metadata") or {}
        self.assertTrue(bool(run_metadata.get("parser_failure")))

    def test_tiktok_historical_empty_success_does_not_advance_backfill_coverage(self):
        state = self._build_state(job_type="historical_backfill", platform="tiktok_ads")

        metadata_calls = []
        cleanup_calls = []

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
            if isinstance(kwargs.get("metadata"), dict):
                existing = state["run"].get("metadata") if isinstance(state["run"].get("metadata"), dict) else {}
                merged = dict(existing)
                merged.update(kwargs.get("metadata") or {})
                state["run"]["metadata"] = merged
            return dict(state["run"])

        def _update_chunk_status(**kwargs):
            state["chunk"]["status"] = kwargs["status"]
            if kwargs.get("metadata") is not None:
                state["chunk"]["metadata"] = kwargs.get("metadata") or {}
            return dict(state["chunk"])

        def _update_progress(**kwargs):
            state["run"]["chunks_done"] = int(state["run"].get("chunks_done") or 0) + int(kwargs.get("chunks_done_delta") or 0)
            state["run"]["rows_written"] = int(state["run"].get("rows_written") or 0) + int(kwargs.get("rows_written_delta") or 0)
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
            sync_worker.sync_run_chunks_store,
            "list_sync_run_chunks",
            return_value=[
                {
                    "chunk_index": 0,
                    "status": "done",
                    "metadata": {
                        "rows_downloaded": 0,
                        "rows_mapped": 0,
                        "zero_row_observability": [{"zero_row_marker": "provider_returned_empty_list"}],
                    },
                }
            ],
        ), patch.object(
            sync_worker.client_registry_service,
            "update_platform_account_operational_metadata",
            side_effect=lambda **kwargs: metadata_calls.append(kwargs) or kwargs,
        ), patch.object(
            sync_worker.tiktok_ads_service,
            "sync_client",
            return_value={
                "rows_written": 0,
                "rows_downloaded": 0,
                "provider_row_count": 0,
                "rows_mapped": 0,
                "zero_row_observability": [{"zero_row_marker": "provider_returned_empty_list"}],
            },
        ), patch.object(
            sync_worker.sync_runs_store,
            "cleanup_superseded_tiktok_failed_runs",
            side_effect=lambda **kwargs: cleanup_calls.append(kwargs) or {"deleted_runs": 0, "deleted_chunks": 0, "superseded_run_count": 0},
        ):
            processed = sync_worker.process_next_chunk()

        self.assertTrue(processed)
        self.assertEqual(state["run"]["status"], "done")
        self.assertEqual(len(metadata_calls), 1)
        self.assertNotIn("backfill_completed_through", metadata_calls[0])
        run_metadata = state["run"].get("metadata") or {}
        self.assertTrue(bool(run_metadata.get("no_data_success")))
        self.assertEqual(run_metadata.get("zero_row_marker"), "provider_returned_empty_list")
        self.assertEqual(cleanup_calls, [{"account_ids": ["3986597205"]}])



if __name__ == "__main__":
    unittest.main()
