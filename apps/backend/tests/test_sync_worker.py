import unittest
from datetime import date
from unittest.mock import patch

from app.workers import sync_worker


class SyncWorkerTests(unittest.TestCase):
    def test_process_next_chunk_once_marks_done_and_updates_progress(self):
        state = {
            "run": {
                "job_id": "job-1",
                "platform": "google_ads",
                "status": "queued",
                "client_id": 101,
                "account_id": "3986597205",
                "job_type": "manual",
                "chunk_days": 7,
                "chunks_done": 0,
                "rows_written": 0,
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
        }

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
            if kwargs.get("mark_finished"):
                state["run"]["finished_at"] = "2026-03-03T00:00:00+00:00"
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
            sync_worker.google_ads_service,
            "sync_customer_for_client",
            return_value={"inserted_rows": 9},
        ):
            processed = sync_worker.process_next_chunk()

        self.assertTrue(processed)
        self.assertEqual(state["chunk"]["status"], "done")
        self.assertEqual(state["chunk"]["rows_written"], 9)
        self.assertEqual(state["run"]["chunks_done"], 1)
        self.assertEqual(state["run"]["rows_written"], 9)
        self.assertEqual(state["run"]["status"], "done")


if __name__ == "__main__":
    unittest.main()
