import os
import unittest
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
        self.original_get_run = sync_orchestration.sync_runs_store.get_sync_run
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
            date_start = str(kwargs["date_start"])
            date_end = str(kwargs["date_end"])
            existing = None
            for run in self.state["runs"].values():
                if (
                    run.get("platform") == platform
                    and str(run.get("account_id") or "") == account_id
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

        sync_orchestration.client_registry_service.list_platform_accounts = _list_platform_accounts
        sync_orchestration.sync_runs_store.create_sync_run = _create_sync_run
        sync_orchestration.sync_runs_store.create_historical_sync_run_if_not_active = _create_historical_sync_run_if_not_active
        sync_orchestration.sync_runs_store.list_sync_runs_by_batch = _list_sync_runs_by_batch
        sync_orchestration.sync_runs_store.list_sync_runs_for_account = _list_sync_runs_for_account
        sync_orchestration.sync_runs_store.get_sync_run = _get_sync_run
        sync_orchestration.sync_runs_store.get_batch_progress = _get_batch_progress
        sync_orchestration.sync_run_chunks_store.create_sync_run_chunk = _create_chunk
        sync_orchestration.sync_run_chunks_store.list_sync_run_chunks = _list_sync_run_chunks

    def tearDown(self):
        sync_orchestration.client_registry_service.list_platform_accounts = self.original_list_platform_accounts
        sync_orchestration.sync_runs_store.create_sync_run = self.original_create_run
        sync_orchestration.sync_runs_store.create_historical_sync_run_if_not_active = self.original_create_historical_guarded
        sync_orchestration.sync_runs_store.get_batch_progress = self.original_get_batch_progress
        sync_orchestration.sync_runs_store.list_sync_runs_by_batch = self.original_list_by_batch
        sync_orchestration.sync_runs_store.list_sync_runs_for_account = self.original_list_for_account
        sync_orchestration.sync_runs_store.get_sync_run = self.original_get_run
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


if __name__ == "__main__":
    unittest.main()
