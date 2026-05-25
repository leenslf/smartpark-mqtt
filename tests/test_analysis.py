"""Tests for analysis.analyze."""

from __future__ import annotations

import os
import sqlite3
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from analysis.analyze import fetch_run_metrics


class TestAnalyze(unittest.TestCase):
    def test_fetch_run_metrics_reads_current_sqlite_schema(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "analysis.db")
            conn = sqlite3.connect(db_path)
            conn.executescript(
                """
                CREATE TABLE runs (
                    run_id TEXT PRIMARY KEY,
                    qos INTEGER,
                    n_slots INTEGER,
                    transition_rate REAL,
                    duration_s INTEGER,
                    network_condition TEXT,
                    loss_pct REAL,
                    delay_ms INTEGER,
                    started_at INTEGER
                );
                CREATE TABLE sent (
                    msg_id TEXT PRIMARY KEY,
                    run_id TEXT,
                    slot_id TEXT,
                    sent_ts INTEGER
                );
                CREATE TABLE received (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT,
                    msg_id TEXT,
                    slot_id TEXT,
                    sent_ts INTEGER,
                    recv_ts INTEGER,
                    is_duplicate INTEGER
                );
                """
            )
            conn.execute(
                """
                INSERT INTO runs (
                    run_id,
                    qos,
                    n_slots,
                    transition_rate,
                    duration_s,
                    network_condition,
                    loss_pct,
                    delay_ms,
                    started_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                ("run_001", 1, 1, 1.0, 30, "lossy-delayed", 2.0, 100, 1000),
            )
            conn.executemany(
                "INSERT INTO sent (msg_id, run_id, slot_id, sent_ts) VALUES (?, ?, ?, ?)",
                [
                    ("slot_01-0001", "run_001", "slot_01", 1000),
                    ("slot_01-0002", "run_001", "slot_01", 2000),
                    ("slot_01-0003", "run_001", "slot_01", 3000),
                ],
            )
            conn.executemany(
                """
                INSERT INTO received (
                    run_id,
                    msg_id,
                    slot_id,
                    sent_ts,
                    recv_ts,
                    is_duplicate
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                [
                    ("run_001", "slot_01-0001", "slot_01", 1000, 1100, 0),
                    ("run_001", "slot_01-0003", "slot_01", 3000, 3100, 0),
                    ("run_001", "slot_01-0002", "slot_01", 2000, 3300, 0),
                    ("run_001", "slot_01-0002", "slot_01", 2000, 3400, 1),
                ],
            )
            conn.commit()
            conn.close()

            metrics = fetch_run_metrics(db_path)

        self.assertEqual(len(metrics), 1)
        metric = metrics[0]
        self.assertEqual(metric.run_id, "run_001")
        self.assertEqual(metric.sent_count, 3)
        self.assertEqual(metric.received_count, 4)
        self.assertEqual(metric.unique_received_count, 3)
        self.assertEqual(metric.duplicate_count, 1)
        self.assertAlmostEqual(metric.delivery_rate, 1.0)
        self.assertAlmostEqual(metric.duplicate_rate, 0.25)
        self.assertAlmostEqual(metric.avg_latency_ms, 500.0)
        self.assertAlmostEqual(metric.p95_latency_ms, 1180.0)
        self.assertEqual(metric.out_of_order_count, 1)
        self.assertAlmostEqual(metric.out_of_order_rate, 1 / 3)


if __name__ == "__main__":
    unittest.main()
