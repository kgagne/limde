"""HistoryStore: the SQLite history (buckets, raw samples, import, pruning, restarts)."""
from pathlib import Path
import json
import sqlite3
import sys
import tempfile
import time
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import tinybar  # noqa: E402

BUCKET = tinybar.HISTORY_BUCKET_SECONDS


class HistoryStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.db = self.dir / "history.sqlite"
        self.legacy = self.dir / "history.jsonl"
        self.stores = []

    def tearDown(self):
        for store in self.stores:
            store.close()
        self.tmp.cleanup()

    def store(self):
        store = tinybar.HistoryStore(self.db, self.legacy)
        self.stores.append(store)
        return store

    def rows(self, sql):
        db = sqlite3.connect(self.db)
        try:
            return db.execute(sql).fetchall()
        finally:
            db.close()

    def test_bucket_and_raw_samples_written_at_bucket_end(self):
        store = self.store()
        start = int(time.time()) // BUCKET * BUCKET - 2 * BUCKET
        store.add_sample("power_w", 6.0, start + 1)
        store.add_sample("power_w", 8.0, start + 6)
        store.add_sample("cpu_percent", 50.0, start + 2)
        self.assertEqual(self.rows("SELECT count(*) FROM buckets"), [(0,)])

        store.add_sample("power_w", 9.0, start + BUCKET + 1)  # next bucket: flushes

        self.assertEqual(
            self.rows("SELECT metric, sample_count, avg, min, max FROM buckets ORDER BY metric"),
            [("cpu_percent", 1, 50.0, 50.0, 50.0), ("power_w", 2, 7.0, 6.0, 8.0)],
        )
        # Raw samples only for metrics read every 5 s or slower (power, not the 2 s CPU).
        self.assertEqual(
            self.rows("SELECT time, metric, value FROM samples ORDER BY time"),
            [(start + 1.0, "power_w", 6.0), (start + 6.0, "power_w", 8.0)],
        )
        self.assertEqual(store.records[-1]["metrics"]["power_w"]["avg"], 7.0)

    def test_reload_keeps_graph_window_in_memory(self):
        store = self.store()
        now = int(time.time()) // BUCKET * BUCKET
        old = now - 10 * 24 * 3600  # in the database, older than the graph's 7 days
        for start in (old, now - 2 * BUCKET):
            store.add_sample("power_w", 5.0, start + 1)
            store.flush()
            store.current_start = None
        store.close()

        again = self.store()
        self.assertEqual([r["start_epoch"] for r in again.records], [now - 2 * BUCKET])
        self.assertEqual(self.rows("SELECT count(*) FROM buckets"), [(2,)])

    def test_restart_within_a_bucket_merges_the_halves(self):
        start = int(time.time()) // BUCKET * BUCKET - BUCKET
        first = self.store()
        first.add_sample("power_w", 4.0, start + 1)
        first.flush()
        first.close()

        second = self.store()
        second.add_sample("power_w", 10.0, start + 100)
        second.add_sample("power_w", 10.0, start + 105)
        second.flush()

        self.assertEqual(
            self.rows("SELECT sample_count, coverage_seconds, avg, min, max FROM buckets"),
            [(3, 15, 8.0, 4.0, 10.0)],
        )

    def test_imports_jsonl_once_and_keeps_it_renamed(self):
        start = int(time.time()) // BUCKET * BUCKET - BUCKET
        record = tinybar.bucket_record(start, BUCKET, {
            "power_w": {"sample_count": 3, "coverage_seconds": 15,
                        "avg": 7.5, "min": 7.0, "max": 8.0},
        })
        self.legacy.write_text("not json\n" + json.dumps(record) + "\n")

        store = self.store()

        self.assertFalse(self.legacy.exists())
        self.assertTrue(self.dir.joinpath("history.jsonl.imported").exists())
        self.assertEqual(
            self.rows("SELECT start, metric, sample_count, avg FROM buckets"),
            [(start, "power_w", 3, 7.5)],
        )
        self.assertEqual(store.records[0]["metrics"]["power_w"]["avg"], 7.5)

    def test_prune_drops_rows_older_than_retention(self):
        store = self.store()
        old = time.time() - tinybar.HISTORY_RETENTION_SECONDS - 3600
        store.add_sample("power_w", 5.0, old)
        store.flush()
        store.current_start = None
        self.assertEqual(self.rows("SELECT count(*) FROM samples"), [(1,)])

        store.last_prune = 0
        store.prune_if_needed()

        self.assertEqual(self.rows("SELECT count(*) FROM buckets"), [(0,)])
        self.assertEqual(self.rows("SELECT count(*) FROM samples"), [(0,)])

    def test_unwritable_database_keeps_panel_running(self):
        bad = self.dir / "dir-not-file"
        bad.mkdir()
        with mock.patch.object(tinybar, "HISTORY_DB", bad):
            store = tinybar.HistoryStore(bad, self.legacy)
        self.assertIsNone(store.db)
        store.add_sample("power_w", 5.0, time.time() - 2 * BUCKET)
        store.flush()
        self.assertEqual(len(store.records), 1)


if __name__ == "__main__":
    unittest.main()
