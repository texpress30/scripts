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
        self.original_get_batch_progress = sync_orchestration.sync_runs_store.get_batch_progress
        self.original_list_by_batch = sync_orchestration.sync_runs_store.list_sync_runs_by_batch
        self.original_create_chunk = sync_orchestration.sync_run_chunks_store.create_sync_run_chunk

        def _list_platform_accounts(*, platform: str):
            if platform != "google_ads":
                return []
            return [
                {"id": "3986597205", "name": "A", "attached_client_id": 11},
                {"id": "1234567890", "name": "B", "attached_client_id": 22},
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
                "batch_id": kwargs.get("batch_id"),
            }
            self.state["runs"][run["job_id"]] = run
            return run

        def _create_chunk(**kwargs):
            self.state["chunks"].append(dict(kwargs))
            return {
                "job_id": kwargs["job_id"],
                "chunk_index": kwargs["chunk_index"],
                "status": kwargs["status"],
                "date_start": str(kwargs["date_start"]),
                "date_end": str(kwargs["date_end"]),
            }

        def _list_sync_runs_by_batch(batch_id: str):
            return [r for r in self.state["runs"].values() if r.get("batch_id") == batch_id]

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
        sync_orchestration.sync_runs_store.list_sync_runs_by_batch = _list_sync_runs_by_batch
        sync_orchestration.sync_runs_store.get_batch_progress = _get_batch_progress
        sync_orchestration.sync_run_chunks_store.create_sync_run_chunk = _create_chunk

    def tearDown(self):
        sync_orchestration.client_registry_service.list_platform_accounts = self.original_list_platform_accounts
        sync_orchestration.sync_runs_store.create_sync_run = self.original_create_run
        sync_orchestration.sync_runs_store.get_batch_progress = self.original_get_batch_progress
        sync_orchestration.sync_runs_store.list_sync_runs_by_batch = self.original_list_by_batch
        sync_orchestration.sync_run_chunks_store.create_sync_run_chunk = self.original_create_chunk
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
        self.assertEqual(create_payload["created_count"], 2)
        self.assertEqual(len(create_payload["runs"]), 2)
        self.assertTrue(create_payload["batch_id"])

        batch_id = create_payload["batch_id"]
        status_response = self.client.get(f"/agency/sync-runs/batch/{batch_id}", headers=headers)
        self.assertEqual(status_response.status_code, 200)
        status_payload = status_response.json()
        self.assertEqual(status_payload["progress"]["total_runs"], 2)
        self.assertGreater(status_payload["progress"]["chunks_total"], 0)
        self.assertEqual(len(status_payload["runs"]), 2)


if __name__ == "__main__":
    unittest.main()
