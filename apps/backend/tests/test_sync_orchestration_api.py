import os
import unittest
from unittest.mock import patch
from datetime import date

try:
    from fastapi.testclient import TestClient
    from app.main import app
    from app.api import sync_orchestration
except Exception:
    TestClient = None
    app = None
    sync_orchestration = None


@unittest.skipIf(TestClient is None or app is None or sync_orchestration is None, "fastapi/testclient dependency not available")
class SyncOrchestrationApiTests(unittest.TestCase):
    def setUp(self):
        self.original_env = os.environ.copy()
        os.environ["APP_ENV"] = "test"
        os.environ["APP_AUTH_SECRET"] = "test-secret"
        self.client = TestClient(app)

        self.state: dict[str, object] = {"runs": {}, "chunks": []}

        self.original_list_platform_accounts = sync_orchestration.client_registry_service.list_platform_accounts
        self.original_create_run = sync_orchestration.sync_runs_store.create_sync_run
        self.original_create_historical_guarded = sync_orchestration.sync_runs_store.create_historical_sync_run_if_not_active
        self.original_get_batch_progress = sync_orchestration.sync_runs_store.get_batch_progress
        self.original_list_by_batch = sync_orchestration.sync_runs_store.list_sync_runs_by_batch
        self.original_list_for_account = sync_orchestration.sync_runs_store.list_sync_runs_for_account
        self.original_batch_progress_for_accounts = sync_orchestration.sync_runs_store.get_active_runs_progress_batch
        self.original_get_run = sync_orchestration.sync_runs_store.get_sync_run
        self.original_repair_run = sync_orchestration.sync_runs_store.repair_historical_sync_run
        self.original_retry_failed_run = sync_orchestration.sync_runs_store.retry_failed_historical_run
        self.original_create_chunk = sync_orchestration.sync_run_chunks_store.create_sync_run_chunk
        self.original_list_chunks = sync_orchestration.sync_run_chunks_store.list_sync_run_chunks

        def _list_platform_accounts(*, platform: str):
            if platform != "google_ads":
                return []
            return [
                {"id": "3986597205", "name": "A", "attached_client_id": 11},
                {"id": "1234567890", "name": "B", "attached_client_id": None},
            ]

        def _create_sync_run(**kwargs):
            run = {
                "job_id": kwargs["job_id"],
                "platform": kwargs["platform"],
                "status": kwargs["status"],
                "client_id": kwargs.get("client_id"),
                "account_id": kwargs.get("account_id"),
                "date_start": str(kwargs["date_start"]),
                "date_end": str(kwargs["date_end"]),
                "chunk_days": kwargs["chunk_days"],
                "job_type": kwargs.get("job_type"),
                "grain": kwargs.get("grain"),
                "chunks_total": kwargs.get("chunks_total", 0),
                "chunks_done": kwargs.get("chunks_done", 0),
                "rows_written": kwargs.get("rows_written", 0),
                "error": None,
                "created_at": "2026-03-03T00:00:00+00:00",
                "updated_at": "2026-03-03T00:00:00+00:00",
                "started_at": None,
                "finished_at": None,
                "batch_id": kwargs.get("batch_id"),
                "metadata": kwargs.get("metadata") or {},
            }
            self.state["runs"][run["job_id"]] = run
            return run

        def _create_historical_sync_run_if_not_active(**kwargs):
            platform = str(kwargs["platform"])
            account_id = str(kwargs.get("account_id") or "")
            grain = str(kwargs.get("grain") or "account_daily")
            date_start = str(kwargs["date_start"])
            date_end = str(kwargs["date_end"])
            existing = None
            for run in self.state["runs"].values():
                if (
                    run.get("platform") == platform
                    and str(run.get("account_id") or "") == account_id
                    and str(run.get("grain") or "account_daily") == grain
                    and run.get("job_type") == "historical_backfill"
                    and str(run.get("date_start")) == date_start
                    and str(run.get("date_end")) == date_end
                    and run.get("status") in {"queued", "running"}
                ):
                    existing = run
                    break
            if existing is not None:
                return {"created": False, "run": existing}

            created = _create_sync_run(
                **{
                    **kwargs,
                    "status": "queued",
                    "job_type": "historical_backfill",
                }
            )
            return {"created": True, "run": created}

        def _create_chunk(**kwargs):
            item = {
                "id": len(self.state["chunks"]) + 1,
                "job_id": kwargs["job_id"],
                "chunk_index": kwargs["chunk_index"],
                "status": kwargs["status"],
                "date_start": str(kwargs["date_start"]),
                "date_end": str(kwargs["date_end"]),
                "attempts": 0,
                "rows_written": 0,
                "duration_ms": None,
                "started_at": None,
                "finished_at": None,
                "created_at": "2026-03-03T00:00:00+00:00",
                "updated_at": "2026-03-03T00:00:00+00:00",
                "error": None,
                "metadata": kwargs.get("metadata") or {},
            }
            self.state["chunks"].append(item)
            return item

        def _list_sync_runs_by_batch(batch_id: str):
            return [r for r in self.state["runs"].values() if r.get("batch_id") == batch_id]

        def _list_sync_runs_for_account(*, platform: str, account_id: str, limit: int = 50):
            selected = [
                r
                for r in self.state["runs"].values()
                if r.get("platform") == platform and r.get("account_id") == account_id
            ]
            return selected[:limit]

        def _get_active_runs_progress_batch(*, platform: str, account_ids: list[str]):
            results: list[dict[str, object]] = []
            for account_id in account_ids:
                runs = [
                    r
                    for r in self.state["runs"].values()
                    if r.get("platform") == platform
                    and r.get("account_id") == account_id
                    and str(r.get("status") or "").lower() in {"queued", "running", "pending"}
                ]
                runs.sort(key=lambda item: str(item.get("created_at") or ""), reverse=True)
                if len(runs) <= 0:
                    results.append({"account_id": account_id, "active_run": None})
                    continue

                selected_run = runs[0]
                chunks = [c for c in self.state["chunks"] if c.get("job_id") == selected_run.get("job_id")]
                done_chunks = len([c for c in chunks if str(c.get("status") or "").lower() in {"done", "success", "completed"}])
                error_chunks = len([c for c in chunks if str(c.get("status") or "").lower() in {"error", "failed"}])
                results.append(
                    {
                        "account_id": account_id,
                        "active_run": {
                            "job_id": selected_run.get("job_id"),
                            "job_type": selected_run.get("job_type"),
                            "status": selected_run.get("status"),
                            "date_start": selected_run.get("date_start"),
                            "date_end": selected_run.get("date_end"),
                            "chunks_done": done_chunks,
                            "chunks_total": len(chunks),
                            "errors_count": error_chunks,
                        },
                    }
                )
            return results

        def _get_sync_run(job_id: str):
            return self.state["runs"].get(job_id)

        def _list_sync_run_chunks(job_id: str):
            selected = [c for c in self.state["chunks"] if c.get("job_id") == job_id]
            selected.sort(key=lambda item: int(item.get("chunk_index") or 0))
            return selected

        def _get_batch_progress(batch_id: str):
            selected = [r for r in self.state["runs"].values() if r.get("batch_id") == batch_id]
            return {
                "batch_id": batch_id,
                "total_runs": len(selected),
                "status_counts": {
                    "queued": len([r for r in selected if r.get("status") == "queued"]),
                    "running": len([r for r in selected if r.get("status") == "running"]),
                    "done": len([r for r in selected if r.get("status") == "done"]),
                    "error": len([r for r in selected if r.get("status") == "error"]),
                },
                "chunks_total_sum": sum(int(r.get("chunks_total") or 0) for r in selected),
                "chunks_done_sum": sum(int(r.get("chunks_done") or 0) for r in selected),
                "rows_written_sum": sum(int(r.get("rows_written") or 0) for r in selected),
            }

        def _repair_historical_sync_run(*, job_id: str, stale_after_minutes: int, repair_source: str = "api"):
            run = self.state["runs"].get(job_id)
            if run is None:
                return {"outcome": "not_found", "job_id": job_id}

            status = str(run.get("status") or "").lower()
            if status not in {"queued", "running"}:
                return {"outcome": "noop_not_active", "job_id": job_id, "run": run}

            chunks = [c for c in self.state["chunks"] if c.get("job_id") == job_id]
            active = [c for c in chunks if str(c.get("status") or "").lower() in {"queued", "running", "pending"}]
            stale = [c for c in active if bool(c.get("force_stale"))]
            if len(active) > 0 and len(stale) != len(active):
                return {
                    "outcome": "noop_active_fresh",
                    "job_id": job_id,
                    "active_chunks": len(active),
                    "stale_chunks": len(stale),
                    "run": run,
                }

            reason = "all_chunks_terminal_reconcile"
            stale_closed = 0
            if len(stale) > 0:
                reason = "stale_chunk_timeout"
                stale_closed = len(stale)
                for chunk in stale:
                    chunk["status"] = "error"
                    chunk["error"] = "stale_timeout"
                    metadata = dict(chunk.get("metadata") or {})
                    metadata["repair_reason"] = "stale_timeout"
                    metadata["repair_source"] = repair_source
                    chunk["metadata"] = metadata

            error_chunks = len([c for c in chunks if str(c.get("status") or "").lower() in {"error", "failed"}])
            done_chunks = len([c for c in chunks if str(c.get("status") or "").lower() in {"done", "success", "completed"}])
            run["status"] = "error" if error_chunks > 0 or stale_closed > 0 else "done"
            run["error"] = None if run["status"] == "done" else f"repair:{reason}"
            run["chunks_total"] = len(chunks)
            run["chunks_done"] = done_chunks
            run["rows_written"] = sum(int(c.get("rows_written") or 0) for c in chunks)
            metadata = dict(run.get("metadata") or {})
            metadata["repair"] = {
                "reason": reason,
                "source": repair_source,
                "stale_after_minutes": stale_after_minutes,
                "stale_chunks_closed": stale_closed,
                "final_status": run["status"],
            }
            run["metadata"] = metadata
            return {
                "outcome": "repaired",
                "reason": reason,
                "job_id": job_id,
                "stale_chunks_closed": stale_closed,
                "final_status": run["status"],
                "run": run,
            }

        def _retry_failed_historical_run(*, source_job_id: str, retry_job_id: str, trigger_source: str = "manual"):
            run = self.state["runs"].get(source_job_id)
            if run is None:
                return {"outcome": "not_found", "source_job_id": source_job_id}

            if str(run.get("job_type") or "").lower() != "historical_backfill" or str(run.get("status") or "").lower() not in {"done", "error"}:
                return {
                    "outcome": "not_retryable",
                    "source_job_id": source_job_id,
                    "platform": run.get("platform"),
                    "account_id": run.get("account_id"),
                    "status": run.get("status"),
                }

            for existing in self.state["runs"].values():
                metadata = existing.get("metadata") or {}
                if (
                    str(existing.get("status") or "").lower() in {"queued", "running"}
                    and str(existing.get("job_type") or "").lower() == "historical_backfill"
                    and str(metadata.get("retry_of_job_id") or "") == source_job_id
                    and str(metadata.get("retry_reason") or "") == "failed_chunks"
                ):
                    return {
                        "outcome": "already_exists",
                        "source_job_id": source_job_id,
                        "retry_job_id": existing.get("job_id"),
                        "platform": run.get("platform"),
                        "account_id": run.get("account_id"),
                        "status": existing.get("status") or "queued",
                        "chunks_created": int(existing.get("chunks_total") or 0),
                        "failed_chunks_count": int(existing.get("chunks_total") or 0),
                    }

            failed_chunks = [
                chunk
                for chunk in self.state["chunks"]
                if chunk.get("job_id") == source_job_id and str(chunk.get("status") or "").lower() in {"error", "failed"}
            ]
            if len(failed_chunks) <= 0:
                return {
                    "outcome": "no_failed_chunks",
                    "source_job_id": source_job_id,
                    "platform": run.get("platform"),
                    "account_id": run.get("account_id"),
                    "status": run.get("status"),
                }

            failed_chunks.sort(key=lambda item: int(item.get("chunk_index") or 0))
            retry_run = _create_sync_run(
                job_id=retry_job_id,
                platform=run.get("platform"),
                status="queued",
                date_start=date.fromisoformat(str(failed_chunks[0].get("date_start"))),
                date_end=date.fromisoformat(str(failed_chunks[-1].get("date_end"))),
                chunk_days=run.get("chunk_days") or 1,
                client_id=run.get("client_id"),
                account_id=run.get("account_id"),
                metadata={
                    **(run.get("metadata") or {}),
                    "retry_of_job_id": source_job_id,
                    "retry_reason": "failed_chunks",
                    "trigger_source": trigger_source,
                },
                job_type="historical_backfill",
                grain=run.get("grain"),
                chunks_total=len(failed_chunks),
                chunks_done=0,
                rows_written=0,
            )
            for idx, chunk in enumerate(failed_chunks):
                _create_chunk(
                    job_id=retry_job_id,
                    chunk_index=idx,
                    status="queued",
                    date_start=date.fromisoformat(str(chunk.get("date_start"))),
                    date_end=date.fromisoformat(str(chunk.get("date_end"))),
                    metadata={
                        "retry_of_job_id": source_job_id,
                        "retry_of_chunk_index": int(chunk.get("chunk_index") or 0),
                        "retry_reason": "failed_chunks",
                    },
                )

            return {
                "outcome": "created",
                "source_job_id": source_job_id,
                "retry_job_id": retry_job_id,
                "platform": run.get("platform"),
                "account_id": run.get("account_id"),
                "status": "queued",
                "chunks_created": len(failed_chunks),
                "failed_chunks_count": len(failed_chunks),
                "run": retry_run,
            }

        sync_orchestration.client_registry_service.list_platform_accounts = _list_platform_accounts
        sync_orchestration.sync_runs_store.create_sync_run = _create_sync_run
        sync_orchestration.sync_runs_store.create_historical_sync_run_if_not_active = _create_historical_sync_run_if_not_active
        sync_orchestration.sync_runs_store.list_sync_runs_by_batch = _list_sync_runs_by_batch
        sync_orchestration.sync_runs_store.list_sync_runs_for_account = _list_sync_runs_for_account
        sync_orchestration.sync_runs_store.get_active_runs_progress_batch = _get_active_runs_progress_batch
        sync_orchestration.sync_runs_store.get_sync_run = _get_sync_run
        sync_orchestration.sync_runs_store.get_batch_progress = _get_batch_progress
        sync_orchestration.sync_runs_store.repair_historical_sync_run = _repair_historical_sync_run
        sync_orchestration.sync_runs_store.retry_failed_historical_run = _retry_failed_historical_run
        sync_orchestration.sync_run_chunks_store.create_sync_run_chunk = _create_chunk
        sync_orchestration.sync_run_chunks_store.list_sync_run_chunks = _list_sync_run_chunks

    def tearDown(self):
        sync_orchestration.client_registry_service.list_platform_accounts = self.original_list_platform_accounts
        sync_orchestration.sync_runs_store.create_sync_run = self.original_create_run
        sync_orchestration.sync_runs_store.create_historical_sync_run_if_not_active = self.original_create_historical_guarded
        sync_orchestration.sync_runs_store.get_batch_progress = self.original_get_batch_progress
        sync_orchestration.sync_runs_store.list_sync_runs_by_batch = self.original_list_by_batch
        sync_orchestration.sync_runs_store.list_sync_runs_for_account = self.original_list_for_account
        sync_orchestration.sync_runs_store.get_active_runs_progress_batch = self.original_batch_progress_for_accounts
        sync_orchestration.sync_runs_store.get_sync_run = self.original_get_run
        sync_orchestration.sync_runs_store.repair_historical_sync_run = self.original_repair_run
        sync_orchestration.sync_runs_store.retry_failed_historical_run = self.original_retry_failed_run
        sync_orchestration.sync_run_chunks_store.create_sync_run_chunk = self.original_create_chunk
        sync_orchestration.sync_run_chunks_store.list_sync_run_chunks = self.original_list_chunks
        os.environ.clear()
        os.environ.update(self.original_env)

    def _auth_headers(self):
        response = self.client.post(
            "/auth/login",
            json={"email": "admin@example.com", "password": "admin123", "role": "agency_admin"},
        )
        self.assertEqual(response.status_code, 200)
        token = response.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}

    def test_batch_enqueue_and_status_polling(self):
        headers = self._auth_headers()
        create_response = self.client.post(
            "/agency/sync-runs/batch",
            headers=headers,
            json={
                "platform": "google_ads",
                "account_ids": ["3986597205", "123-456-7890"],
                "job_type": "manual",
                "start_date": str(date(2026, 2, 1)),
                "end_date": str(date(2026, 2, 7)),
                "chunk_days": 3,
                "grain": "account_daily",
            },
        )
        self.assertEqual(create_response.status_code, 200)
        create_payload = create_response.json()
        self.assertEqual(create_payload["created_count"], 1)
        self.assertEqual(len(create_payload["runs"]), 1)
        self.assertTrue(create_payload["batch_id"])
        self.assertIn("1234567890", create_payload["invalid_account_ids"])

        batch_id = create_payload["batch_id"]
        status_response = self.client.get(f"/agency/sync-runs/batch/{batch_id}", headers=headers)
        self.assertEqual(status_response.status_code, 200)
        status_payload = status_response.json()
        self.assertEqual(status_payload["progress"]["total_runs"], 1)
        self.assertGreater(status_payload["progress"]["chunks_total"], 0)
        self.assertEqual(len(status_payload["runs"]), 1)


    def test_reconciles_stale_run_progress_from_chunks_for_batch_and_account(self):
        headers = self._auth_headers()
        create_response = self.client.post(
            "/agency/sync-runs/batch",
            headers=headers,
            json={
                "platform": "google_ads",
                "account_ids": ["3986597205"],
                "job_type": "manual",
                "start_date": str(date(2026, 2, 1)),
                "end_date": str(date(2026, 2, 4)),
                "chunk_days": 1,
            },
        )
        self.assertEqual(create_response.status_code, 200)
        payload = create_response.json()
        batch_id = payload["batch_id"]
        job_id = payload["runs"][0]["job_id"]

        run_state = self.state["runs"][job_id]
        run_state["status"] = "done"
        run_state["chunks_total"] = 113
        run_state["chunks_done"] = 80
        run_state["rows_written"] = 999

        chunks = [c for c in self.state["chunks"] if c.get("job_id") == job_id]
        for idx, chunk in enumerate(chunks):
            chunk["status"] = "done"
            chunk["rows_written"] = 1
            chunk["chunk_index"] = idx

        status_response = self.client.get(f"/agency/sync-runs/batch/{batch_id}", headers=headers)
        self.assertEqual(status_response.status_code, 200)
        status_payload = status_response.json()
        self.assertEqual(status_payload["progress"]["done"], 1)
        self.assertEqual(status_payload["progress"]["running"], 0)
        self.assertEqual(status_payload["progress"]["chunks_done"], len(chunks))
        self.assertEqual(status_payload["progress"]["chunks_total"], len(chunks))
        self.assertEqual(status_payload["progress"]["percent"], 100.0)

        run_payload = status_payload["runs"][0]
        self.assertEqual(run_payload["status"], "done")
        self.assertEqual(run_payload["chunks_done"], len(chunks))
        self.assertEqual(run_payload["chunks_total"], len(chunks))
        self.assertEqual(run_payload["percent_complete"], 100.0)

        logs_response = self.client.get("/agency/sync-runs/accounts/google_ads/3986597205?limit=10", headers=headers)
        self.assertEqual(logs_response.status_code, 200)
        logs_payload = logs_response.json()
        self.assertEqual(logs_payload["runs"][0]["percent_complete"], 100.0)


    def test_progress_and_terminal_status_rules_from_chunk_truth(self):
        headers = self._auth_headers()
        created = self.client.post(
            "/agency/sync-runs/batch",
            headers=headers,
            json={
                "platform": "google_ads",
                "account_ids": ["3986597205"],
                "job_type": "manual",
                "start_date": str(date(2026, 2, 1)),
                "end_date": str(date(2026, 2, 5)),
                "chunk_days": 1,
            },
        )
        self.assertEqual(created.status_code, 200)
        job_id = created.json()["runs"][0]["job_id"]

        # Case A: 2 done, 3 active -> running, percent = 40% based on chunks only.
        chunks = [c for c in self.state["chunks"] if c.get("job_id") == job_id]
        for idx, chunk in enumerate(chunks):
            if idx < 2:
                chunk["status"] = "done"
                chunk["rows_written"] = 0
            else:
                chunk["status"] = "queued"
                chunk["rows_written"] = 5000

        run_response = self.client.get(f"/agency/sync-runs/{job_id}", headers=headers)
        self.assertEqual(run_response.status_code, 200)
        run_payload = run_response.json()
        self.assertEqual(run_payload["status"], "running")
        self.assertEqual(run_payload["chunks_done"], 2)
        self.assertEqual(run_payload["chunks_total"], len(chunks))
        self.assertEqual(run_payload["percent_complete"], 40.0)

        # Case B: all terminal with errors -> partial, not active.
        for idx, chunk in enumerate(chunks):
            chunk["status"] = "done" if idx < 3 else "error"

        run_response_2 = self.client.get(f"/agency/sync-runs/{job_id}", headers=headers)
        self.assertEqual(run_response_2.status_code, 200)
        run_payload_2 = run_response_2.json()
        self.assertEqual(run_payload_2["status"], "partial")
        self.assertEqual(run_payload_2["error_chunks"], 2)
        self.assertEqual(run_payload_2["active_chunks"], 0)
        self.assertEqual(run_payload_2["percent_complete"], 60.0)

    def test_account_runs_and_chunk_details_shape(self):
        headers = self._auth_headers()
        created = self.client.post(
            "/agency/sync-runs/batch",
            headers=headers,
            json={
                "platform": "google_ads",
                "account_ids": ["3986597205"],
                "job_type": "manual",
                "start_date": str(date(2026, 2, 1)),
                "end_date": str(date(2026, 2, 7)),
                "chunk_days": 2,
            },
        )
        self.assertEqual(created.status_code, 200)
        job_id = created.json()["runs"][0]["job_id"]

        logs_response = self.client.get("/agency/sync-runs/accounts/google_ads/3986597205?limit=10", headers=headers)
        self.assertEqual(logs_response.status_code, 200)
        logs_payload = logs_response.json()
        self.assertEqual(logs_payload["platform"], "google_ads")
        self.assertEqual(logs_payload["account_id"], "3986597205")
        self.assertEqual(logs_payload["limit"], 10)
        self.assertEqual(len(logs_payload["runs"]), 1)
        self.assertEqual(logs_payload["runs"][0]["job_id"], job_id)
        self.assertEqual(logs_payload["runs"][0]["trigger_source"], "manual")

        run_response = self.client.get(f"/agency/sync-runs/{job_id}", headers=headers)
        self.assertEqual(run_response.status_code, 200)
        self.assertEqual(run_response.json()["job_id"], job_id)

        chunks_response = self.client.get(f"/agency/sync-runs/{job_id}/chunks", headers=headers)
        self.assertEqual(chunks_response.status_code, 200)
        chunks_payload = chunks_response.json()
        self.assertEqual(chunks_payload["job_id"], job_id)
        self.assertGreaterEqual(len(chunks_payload["chunks"]), 1)
        self.assertIn("chunk_index", chunks_payload["chunks"][0])

    def test_accounts_progress_batch_returns_active_run_and_null_entries(self):
        headers = self._auth_headers()
        created = self.client.post(
            "/agency/sync-runs/batch",
            headers=headers,
            json={
                "platform": "google_ads",
                "account_ids": ["3986597205"],
                "job_type": "rolling_refresh",
                "start_date": str(date(2026, 1, 1)),
                "end_date": str(date(2026, 1, 3)),
                "chunk_days": 1,
            },
        )
        self.assertEqual(created.status_code, 200)
        job_id = created.json()["runs"][0]["job_id"]

        run = self.state["runs"][job_id]
        run["status"] = "running"
        run["job_type"] = "rolling_refresh"

        chunks = [c for c in self.state["chunks"] if c.get("job_id") == job_id]
        self.assertGreater(len(chunks), 0)
        chunks[0]["status"] = "done"
        if len(chunks) > 1:
            chunks[1]["status"] = "error"

        response = self.client.post(
            "/agency/sync-runs/accounts/google_ads/progress",
            headers=headers,
            json={"account_ids": ["3986597205", "missing-account"]},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["platform"], "google_ads")
        self.assertEqual(payload["requested_count"], 2)
        self.assertEqual(len(payload["results"]), 2)

        first = payload["results"][0]
        self.assertEqual(first["account_id"], "3986597205")
        self.assertEqual(first["active_run"]["job_id"], job_id)
        self.assertEqual(first["active_run"]["job_type"], "rolling_refresh")
        self.assertEqual(first["active_run"]["status"], "running")
        self.assertEqual(first["active_run"]["chunks_done"], 1)
        self.assertEqual(first["active_run"]["chunks_total"], len(chunks))
        self.assertEqual(first["active_run"]["errors_count"], 1 if len(chunks) > 1 else 0)

        second = payload["results"][1]
        self.assertEqual(second["account_id"], "missing-account")
        self.assertIsNone(second["active_run"])

    def test_accounts_progress_batch_validates_empty_and_max_limit(self):
        headers = self._auth_headers()

        empty_response = self.client.post(
            "/agency/sync-runs/accounts/google_ads/progress",
            headers=headers,
            json={"account_ids": []},
        )
        self.assertEqual(empty_response.status_code, 400)

        too_many_ids = [f"acc-{idx}" for idx in range(201)]
        limit_response = self.client.post(
            "/agency/sync-runs/accounts/google_ads/progress",
            headers=headers,
            json={"account_ids": too_many_ids},
        )
        self.assertEqual(limit_response.status_code, 400)

    def test_accounts_progress_batch_keeps_requested_scope(self):
        headers = self._auth_headers()

        first = self.client.post(
            "/agency/sync-runs/batch",
            headers=headers,
            json={
                "platform": "google_ads",
                "account_ids": ["3986597205"],
                "job_type": "manual",
                "start_date": str(date(2026, 2, 1)),
                "end_date": str(date(2026, 2, 1)),
                "chunk_days": 1,
            },
        )
        self.assertEqual(first.status_code, 200)
        first_job_id = first.json()["runs"][0]["job_id"]
        self.state["runs"][first_job_id]["status"] = "running"

        self.state["runs"]["job-other"] = {
            "job_id": "job-other",
            "platform": "google_ads",
            "status": "running",
            "client_id": 11,
            "account_id": "unrequested",
            "date_start": "2026-02-01",
            "date_end": "2026-02-02",
            "chunk_days": 1,
            "job_type": "rolling_refresh",
            "grain": "account_daily",
            "chunks_total": 1,
            "chunks_done": 0,
            "rows_written": 0,
            "error": None,
            "created_at": "2026-03-03T00:00:00+00:00",
            "updated_at": "2026-03-03T00:00:00+00:00",
            "started_at": None,
            "finished_at": None,
            "batch_id": "seed",
            "metadata": {},
        }

        response = self.client.post(
            "/agency/sync-runs/accounts/google_ads/progress",
            headers=headers,
            json={"account_ids": ["3986597205"]},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["requested_count"], 1)
        self.assertEqual(len(payload["results"]), 1)
        self.assertEqual(payload["results"][0]["account_id"], "3986597205")

    def test_historical_duplicate_request_returns_already_exists_without_new_chunks(self):
        headers = self._auth_headers()
        payload = {
            "platform": "google_ads",
            "account_ids": ["3986597205"],
            "job_type": "historical_backfill",
            "start_date": str(date(2026, 1, 1)),
            "end_date": str(date(2026, 1, 10)),
            "chunk_days": 5,
        }

        first = self.client.post("/agency/sync-runs/batch", headers=headers, json=payload)
        self.assertEqual(first.status_code, 200)
        first_payload = first.json()
        self.assertEqual(first_payload["created_count"], 1)
        self.assertEqual(first_payload["already_exists_count"], 0)
        self.assertEqual(first_payload["results"][0]["result"], "created")
        first_job_id = first_payload["runs"][0]["job_id"]
        chunks_after_first = len(self.state["chunks"])

        second = self.client.post("/agency/sync-runs/batch", headers=headers, json=payload)
        self.assertEqual(second.status_code, 200)
        second_payload = second.json()
        self.assertEqual(second_payload["created_count"], 0)
        self.assertEqual(second_payload["already_exists_count"], 1)
        self.assertEqual(len(second_payload["runs"]), 0)
        self.assertEqual(second_payload["results"][0]["result"], "already_exists")
        self.assertEqual(second_payload["results"][0]["job_id"], first_job_id)
        self.assertEqual(second_payload["results"][0]["status"], "queued")
        self.assertEqual(len(self.state["runs"]), 1)
        self.assertEqual(len(self.state["chunks"]), chunks_after_first)

    def test_batch_defaults_to_account_daily_grain_when_flag_off(self):
        headers = self._auth_headers()
        with patch.dict(os.environ, {"ENTITY_GRAINS_ENABLED": "0", "ROLLING_ENTITY_GRAINS_ENABLED": "0"}, clear=False):
            response = self.client.post(
                "/agency/sync-runs/batch",
                headers=headers,
                json={
                    "platform": "google_ads",
                    "account_ids": ["3986597205"],
                    "job_type": "historical_backfill",
                    "start_date": str(date(2026, 1, 1)),
                    "end_date": str(date(2026, 1, 3)),
                    "chunk_days": 1,
                },
            )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["created_count"], 1)
        self.assertEqual(payload["grains"], ["account_daily"])
        self.assertNotIn("keyword_daily", payload["grains"])
        self.assertEqual(payload["results"][0]["grain"], "account_daily")

    def test_batch_google_legacy_missing_grain_expands_when_flag_on(self):
        headers = self._auth_headers()
        with patch.dict(os.environ, {"ENTITY_GRAINS_ENABLED": "1"}, clear=False):
            response = self.client.post(
                "/agency/sync-runs/batch",
                headers=headers,
                json={
                    "platform": "google_ads",
                    "account_ids": ["3986597205"],
                    "job_type": "historical_backfill",
                    "start_date": str(date(2026, 1, 1)),
                    "end_date": str(date(2026, 1, 3)),
                    "chunk_days": 1,
                },
            )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["grains"], ["account_daily", "campaign_daily", "ad_group_daily", "keyword_daily", "ad_daily"])
        self.assertEqual(payload["created_count"], 5)
        self.assertEqual([item["grain"] for item in payload["runs"]], ["account_daily", "campaign_daily", "ad_group_daily", "keyword_daily", "ad_daily"])

    def test_batch_google_legacy_account_daily_expands_when_flag_on(self):
        headers = self._auth_headers()
        with patch.dict(os.environ, {"ROLLING_ENTITY_GRAINS_ENABLED": "1", "ENTITY_GRAINS_ENABLED": "0"}, clear=False):
            response = self.client.post(
                "/agency/sync-runs/batch",
                headers=headers,
                json={
                    "platform": "google_ads",
                    "account_ids": ["3986597205"],
                    "job_type": "historical_backfill",
                    "start_date": str(date(2026, 1, 1)),
                    "end_date": str(date(2026, 1, 3)),
                    "chunk_days": 1,
                    "grain": "account_daily",
                },
            )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["grains"], ["account_daily", "campaign_daily", "ad_group_daily", "keyword_daily", "ad_daily"])
        self.assertEqual(payload["created_count"], 5)
        self.assertEqual([item["grain"] for item in payload["runs"]], ["account_daily", "campaign_daily", "ad_group_daily", "keyword_daily", "ad_daily"])

    def test_batch_google_explicit_grains_missing_keyword_does_not_auto_add_when_flag_on(self):
        headers = self._auth_headers()
        with patch.dict(os.environ, {"ENTITY_GRAINS_ENABLED": "1"}, clear=False):
            response = self.client.post(
                "/agency/sync-runs/batch",
                headers=headers,
                json={
                    "platform": "google_ads",
                    "account_ids": ["3986597205"],
                    "job_type": "historical_backfill",
                    "start_date": str(date(2026, 1, 1)),
                    "end_date": str(date(2026, 1, 3)),
                    "chunk_days": 1,
                    "grains": ["account_daily", "campaign_daily", "ad_group_daily", "ad_daily"],
                },
            )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["grains"], ["account_daily", "campaign_daily", "ad_group_daily", "ad_daily"])
        self.assertNotIn("keyword_daily", payload["grains"])
        self.assertEqual(payload["created_count"], 4)

    def test_batch_non_google_does_not_auto_expand_when_flag_on(self):
        headers = self._auth_headers()
        with patch.dict(os.environ, {"ENTITY_GRAINS_ENABLED": "1"}, clear=False):
            response = self.client.post(
                "/agency/sync-runs/batch",
                headers=headers,
                json={
                    "platform": "meta_ads",
                    "account_ids": ["3986597205"],
                    "job_type": "historical_backfill",
                    "start_date": str(date(2026, 1, 1)),
                    "end_date": str(date(2026, 1, 3)),
                    "chunk_days": 1,
                },
            )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["grains"], ["account_daily"])
        self.assertNotIn("keyword_daily", payload["grains"])

    def test_batch_creates_one_run_per_requested_grain(self):
        headers = self._auth_headers()
        response = self.client.post(
            "/agency/sync-runs/batch",
            headers=headers,
            json={
                "platform": "google_ads",
                "account_ids": ["3986597205"],
                "job_type": "historical_backfill",
                "start_date": str(date(2026, 1, 1)),
                "end_date": str(date(2026, 1, 3)),
                "chunk_days": 1,
                "grains": ["account_daily", "campaign_daily"],
            },
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["created_count"], 2)
        self.assertEqual({item["grain"] for item in payload["runs"]}, {"account_daily", "campaign_daily"})

    def test_batch_dedupe_is_scoped_by_grain(self):
        headers = self._auth_headers()
        sync_orchestration.sync_runs_store.create_sync_run(
            job_id="existing-account",
            platform="google_ads",
            status="running",
            date_start=date(2026, 1, 1),
            date_end=date(2026, 1, 3),
            chunk_days=1,
            client_id=11,
            account_id="3986597205",
            metadata={},
            batch_id="seed",
            job_type="historical_backfill",
            grain="account_daily",
            chunks_total=3,
            chunks_done=1,
            rows_written=5,
        )

        response = self.client.post(
            "/agency/sync-runs/batch",
            headers=headers,
            json={
                "platform": "google_ads",
                "account_ids": ["3986597205"],
                "job_type": "historical_backfill",
                "start_date": str(date(2026, 1, 1)),
                "end_date": str(date(2026, 1, 3)),
                "chunk_days": 1,
                "grains": ["account_daily", "campaign_daily"],
            },
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["created_count"], 1)
        self.assertEqual(payload["already_exists_count"], 1)

        by_grain = {item["grain"]: item for item in payload["results"]}
        self.assertEqual(by_grain["account_daily"]["result"], "already_exists")
        self.assertEqual(by_grain["account_daily"]["job_id"], "existing-account")
        self.assertEqual(by_grain["campaign_daily"]["result"], "created")

    def test_batch_rejects_invalid_grain(self):
        headers = self._auth_headers()
        response = self.client.post(
            "/agency/sync-runs/batch",
            headers=headers,
            json={
                "platform": "google_ads",
                "account_ids": ["3986597205"],
                "job_type": "historical_backfill",
                "start_date": str(date(2026, 1, 1)),
                "end_date": str(date(2026, 1, 3)),
                "chunk_days": 1,
                "grains": ["invalid_grain"],
            },
        )
        self.assertEqual(response.status_code, 422)

    def test_batch_deduplicates_duplicate_grains_in_payload(self):
        headers = self._auth_headers()
        response = self.client.post(
            "/agency/sync-runs/batch",
            headers=headers,
            json={
                "platform": "google_ads",
                "account_ids": ["3986597205"],
                "job_type": "historical_backfill",
                "start_date": str(date(2026, 1, 1)),
                "end_date": str(date(2026, 1, 3)),
                "chunk_days": 1,
                "grains": ["campaign_daily", "campaign_daily"],
            },
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["created_count"], 1)
        self.assertEqual(payload["grains"], ["campaign_daily"])
        self.assertEqual(len(payload["runs"]), 1)

    def test_historical_batch_mixed_created_and_already_exists_results(self):
        headers = self._auth_headers()
        preexisting = sync_orchestration.sync_runs_store.create_sync_run(
            job_id="existing-historical",
            platform="google_ads",
            status="running",
            date_start=date(2026, 1, 1),
            date_end=date(2026, 1, 5),
            chunk_days=2,
            client_id=11,
            account_id="3986597205",
            metadata={"source": "manual", "job_type": "historical_backfill"},
            batch_id="seed-batch",
            job_type="historical_backfill",
            grain="account_daily",
            chunks_total=3,
            chunks_done=1,
            rows_written=10,
        )
        self.assertIsNotNone(preexisting)

        response = self.client.post(
            "/agency/sync-runs/batch",
            headers=headers,
            json={
                "platform": "google_ads",
                "account_ids": ["3986597205", "1111111111"],
                "job_type": "historical_backfill",
                "start_date": str(date(2026, 1, 1)),
                "end_date": str(date(2026, 1, 5)),
                "chunk_days": 2,
            },
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["created_count"], 0)
        self.assertEqual(payload["already_exists_count"], 1)
        self.assertIn("1111111111", payload["invalid_account_ids"])
        self.assertEqual(len(payload["results"]), 1)
        self.assertEqual(payload["results"][0]["result"], "already_exists")
        self.assertEqual(payload["results"][0]["job_id"], "existing-historical")

    def test_non_historical_job_type_is_not_deduped(self):
        headers = self._auth_headers()
        payload = {
            "platform": "google_ads",
            "account_ids": ["3986597205"],
            "job_type": "manual",
            "start_date": str(date(2026, 2, 1)),
            "end_date": str(date(2026, 2, 2)),
            "chunk_days": 1,
        }

        first = self.client.post("/agency/sync-runs/batch", headers=headers, json=payload)
        second = self.client.post("/agency/sync-runs/batch", headers=headers, json=payload)
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)

        first_payload = first.json()
        second_payload = second.json()
        self.assertEqual(first_payload["created_count"], 1)
        self.assertEqual(second_payload["created_count"], 1)
        self.assertEqual(first_payload["already_exists_count"], 0)
        self.assertEqual(second_payload["already_exists_count"], 0)
        self.assertEqual(len(self.state["runs"]), 2)

    def test_repair_endpoint_not_found(self):
        headers = self._auth_headers()
        response = self.client.post("/agency/sync-runs/missing-job/repair", headers=headers)
        self.assertEqual(response.status_code, 404)
        payload = response.json()
        self.assertEqual(payload["detail"]["outcome"], "not_found")

    def test_repair_endpoint_noop_not_active_for_terminal_run(self):
        headers = self._auth_headers()
        sync_orchestration.sync_runs_store.create_sync_run(
            job_id="terminal-run",
            platform="google_ads",
            status="done",
            date_start=date(2026, 1, 1),
            date_end=date(2026, 1, 2),
            chunk_days=1,
            client_id=11,
            account_id="3986597205",
            metadata={},
            batch_id="seed",
            job_type="historical_backfill",
            grain="account_daily",
            chunks_total=2,
            chunks_done=2,
            rows_written=100,
        )
        response = self.client.post("/agency/sync-runs/terminal-run/repair", headers=headers)
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["outcome"], "noop_not_active")
        self.assertEqual(payload["run"]["status"], "done")

    def test_repair_endpoint_finalizes_active_run_when_chunks_already_terminal(self):
        headers = self._auth_headers()
        sync_orchestration.sync_runs_store.create_sync_run(
            job_id="stuck-terminal",
            platform="google_ads",
            status="running",
            date_start=date(2026, 1, 1),
            date_end=date(2026, 1, 3),
            chunk_days=1,
            client_id=11,
            account_id="3986597205",
            metadata={},
            batch_id="seed",
            job_type="historical_backfill",
            grain="account_daily",
            chunks_total=3,
            chunks_done=0,
            rows_written=0,
        )
        for idx in range(3):
            sync_orchestration.sync_run_chunks_store.create_sync_run_chunk(
                job_id="stuck-terminal",
                chunk_index=idx,
                status="done",
                date_start=date(2026, 1, 1),
                date_end=date(2026, 1, 1),
                rows_written=5,
                metadata={},
            )
        response = self.client.post("/agency/sync-runs/stuck-terminal/repair", headers=headers)
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["outcome"], "repaired")
        self.assertEqual(payload["reason"], "all_chunks_terminal_reconcile")
        self.assertEqual(payload["final_status"], "done")
        self.assertEqual(payload["run"]["status"], "done")

    def test_repair_endpoint_closes_stale_active_chunks_and_finishes_with_error(self):
        headers = self._auth_headers()
        sync_orchestration.sync_runs_store.create_sync_run(
            job_id="stale-run",
            platform="google_ads",
            status="running",
            date_start=date(2026, 1, 1),
            date_end=date(2026, 1, 2),
            chunk_days=1,
            client_id=11,
            account_id="3986597205",
            metadata={},
            batch_id="seed",
            job_type="historical_backfill",
            grain="account_daily",
            chunks_total=2,
            chunks_done=0,
            rows_written=0,
        )
        chunk = sync_orchestration.sync_run_chunks_store.create_sync_run_chunk(
            job_id="stale-run",
            chunk_index=0,
            status="running",
            date_start=date(2026, 1, 1),
            date_end=date(2026, 1, 1),
            metadata={},
        )
        chunk["force_stale"] = True
        response = self.client.post("/agency/sync-runs/stale-run/repair", headers=headers)
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["outcome"], "repaired")
        self.assertEqual(payload["reason"], "stale_chunk_timeout")
        self.assertEqual(payload["final_status"], "error")
        self.assertEqual(payload["stale_chunks_closed"], 1)

    def test_repair_endpoint_noop_when_active_chunks_are_fresh(self):
        headers = self._auth_headers()
        sync_orchestration.sync_runs_store.create_sync_run(
            job_id="fresh-run",
            platform="google_ads",
            status="running",
            date_start=date(2026, 1, 1),
            date_end=date(2026, 1, 2),
            chunk_days=1,
            client_id=11,
            account_id="3986597205",
            metadata={},
            batch_id="seed",
            job_type="historical_backfill",
            grain="account_daily",
            chunks_total=2,
            chunks_done=0,
            rows_written=0,
        )
        sync_orchestration.sync_run_chunks_store.create_sync_run_chunk(
            job_id="fresh-run",
            chunk_index=0,
            status="running",
            date_start=date(2026, 1, 1),
            date_end=date(2026, 1, 1),
            metadata={},
        )
        response = self.client.post("/agency/sync-runs/fresh-run/repair", headers=headers)
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["outcome"], "noop_active_fresh")
        self.assertEqual(payload["run"]["status"], "running")

    def test_repair_endpoint_repeat_call_is_stable(self):
        headers = self._auth_headers()
        sync_orchestration.sync_runs_store.create_sync_run(
            job_id="repeat-run",
            platform="google_ads",
            status="running",
            date_start=date(2026, 1, 1),
            date_end=date(2026, 1, 2),
            chunk_days=1,
            client_id=11,
            account_id="3986597205",
            metadata={},
            batch_id="seed",
            job_type="historical_backfill",
            grain="account_daily",
            chunks_total=1,
            chunks_done=0,
            rows_written=0,
        )
        stale_chunk = sync_orchestration.sync_run_chunks_store.create_sync_run_chunk(
            job_id="repeat-run",
            chunk_index=0,
            status="running",
            date_start=date(2026, 1, 1),
            date_end=date(2026, 1, 1),
            metadata={},
        )
        stale_chunk["force_stale"] = True

        first = self.client.post("/agency/sync-runs/repeat-run/repair", headers=headers)
        second = self.client.post("/agency/sync-runs/repeat-run/repair", headers=headers)
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(first.json()["outcome"], "repaired")
        self.assertEqual(second.json()["outcome"], "noop_not_active")

    def test_retry_failed_endpoint_not_found(self):
        headers = self._auth_headers()
        response = self.client.post("/agency/sync-runs/missing-source/retry-failed", headers=headers)
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["detail"]["outcome"], "not_found")

    def test_retry_failed_endpoint_not_retryable_for_non_historical_or_active(self):
        headers = self._auth_headers()
        sync_orchestration.sync_runs_store.create_sync_run(
            job_id="manual-run",
            platform="google_ads",
            status="done",
            date_start=date(2026, 1, 1),
            date_end=date(2026, 1, 1),
            chunk_days=1,
            client_id=11,
            account_id="3986597205",
            metadata={},
            batch_id="seed",
            job_type="manual",
            grain="account_daily",
            chunks_total=1,
            chunks_done=1,
            rows_written=10,
        )
        response = self.client.post("/agency/sync-runs/manual-run/retry-failed", headers=headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["outcome"], "not_retryable")

    def test_retry_failed_endpoint_created_and_then_already_exists(self):
        headers = self._auth_headers()
        sync_orchestration.sync_runs_store.create_sync_run(
            job_id="source-error-run",
            platform="google_ads",
            status="error",
            date_start=date(2026, 1, 1),
            date_end=date(2026, 1, 7),
            chunk_days=2,
            client_id=11,
            account_id="3986597205",
            metadata={},
            batch_id="seed",
            job_type="historical_backfill",
            grain="account_daily",
            chunks_total=3,
            chunks_done=2,
            rows_written=10,
        )
        sync_orchestration.sync_run_chunks_store.create_sync_run_chunk(
            job_id="source-error-run",
            chunk_index=0,
            status="done",
            date_start=date(2026, 1, 1),
            date_end=date(2026, 1, 2),
            metadata={},
        )
        sync_orchestration.sync_run_chunks_store.create_sync_run_chunk(
            job_id="source-error-run",
            chunk_index=1,
            status="error",
            date_start=date(2026, 1, 3),
            date_end=date(2026, 1, 4),
            metadata={},
        )

        created = self.client.post("/agency/sync-runs/source-error-run/retry-failed", headers=headers)
        self.assertEqual(created.status_code, 200)
        created_payload = created.json()
        self.assertEqual(created_payload["outcome"], "created")
        self.assertEqual(created_payload["chunks_created"], 1)
        retry_job_id = created_payload["retry_job_id"]

        again = self.client.post("/agency/sync-runs/source-error-run/retry-failed", headers=headers)
        self.assertEqual(again.status_code, 200)
        again_payload = again.json()
        self.assertEqual(again_payload["outcome"], "already_exists")
        self.assertEqual(again_payload["retry_job_id"], retry_job_id)

    def test_retry_failed_endpoint_no_failed_chunks(self):
        headers = self._auth_headers()
        sync_orchestration.sync_runs_store.create_sync_run(
            job_id="source-done-run",
            platform="google_ads",
            status="done",
            date_start=date(2026, 1, 1),
            date_end=date(2026, 1, 2),
            chunk_days=1,
            client_id=11,
            account_id="3986597205",
            metadata={},
            batch_id="seed",
            job_type="historical_backfill",
            grain="account_daily",
            chunks_total=1,
            chunks_done=1,
            rows_written=10,
        )
        sync_orchestration.sync_run_chunks_store.create_sync_run_chunk(
            job_id="source-done-run",
            chunk_index=0,
            status="done",
            date_start=date(2026, 1, 1),
            date_end=date(2026, 1, 2),
            metadata={},
        )

        response = self.client.post("/agency/sync-runs/source-done-run/retry-failed", headers=headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["outcome"], "no_failed_chunks")


if __name__ == "__main__":
    unittest.main()
