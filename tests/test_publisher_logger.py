"""Tests for sensors.publisher_logger."""

import os
import sqlite3
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from shared.protocol import Event
from sensors.publisher_logger import PublisherLogger


class TestPublisherLogger(unittest.TestCase):
    def test_log_writes_sent_row(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "publisher_logger.db")

            conn = sqlite3.connect(db_path)
            conn.execute(
                """
                CREATE TABLE sent (
                    msg_id TEXT PRIMARY KEY,
                    run_id TEXT,
                    slot_id TEXT,
                    sent_ts INTEGER
                )
                """
            )
            conn.commit()
            conn.close()

            logger = PublisherLogger(db_path=db_path, run_id="run_001")
            event = Event(
                slot_id="slot_01",
                state="FREE",
                msg_id="slot_01-0001",
                sent_ts=1234567890,
                recv_ts=0,
                qos=1,
                raw_topic="parking/telemetry/slot_01",
            )

            logger.log(event)
            logger.close()

            check = sqlite3.connect(db_path)
            row = check.execute(
                "SELECT run_id, msg_id, slot_id, sent_ts FROM sent"
            ).fetchone()
            check.close()

            self.assertEqual(row, ("run_001", "slot_01-0001", "slot_01", 1234567890))


if __name__ == "__main__":
    unittest.main()
