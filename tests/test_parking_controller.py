"""Tests for parking_controller components."""

import json
import os
import sqlite3
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from shared.protocol import Event
from parking_controller.alerts import AlertService
from parking_controller.consumer import MQTTConsumer
from parking_controller.measurement import MeasurementLogger
from parking_controller.parking_state import ParkingLotState


class TestMQTTConsumer(unittest.TestCase):
    def test_on_message_sets_recv_ts_before_json_loads(self):
        order: list[str] = []
        captured: list[Event] = []
        consumer = MQTTConsumer("localhost", 1883, captured.append)
        msg = SimpleNamespace(
            payload=b'{"slot_id":"slot_01","state":"FREE","msg_id":"slot_01-0001","sent_ts":1000,"qos":1}',
            topic="parking/telemetry/slot_01",
        )
        original_json_loads = json.loads

        def fake_time_ns() -> int:
            order.append("time")
            return 2_345_000_000

        def fake_json_loads(payload: bytes) -> dict:
            order.append("json")
            return original_json_loads(payload)

        with patch("parking_controller.consumer.time.time_ns", side_effect=fake_time_ns), patch(
            "parking_controller.consumer.json.loads", side_effect=fake_json_loads
        ):
            consumer.on_message(None, None, msg)

        self.assertEqual(order, ["time", "json"])
        self.assertEqual(captured[0].recv_ts, 2345)


class TestMeasurementLogger(unittest.TestCase):
    def test_record_marks_duplicate_on_second_arrival(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "measurement.db")
            conn = sqlite3.connect(db_path)
            conn.execute(
                """
                CREATE TABLE received (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT,
                    msg_id TEXT,
                    slot_id TEXT,
                    sent_ts INTEGER,
                    recv_ts INTEGER,
                    is_duplicate INTEGER
                )
                """
            )
            conn.commit()
            conn.close()

            logger = MeasurementLogger(db_path, "run_001")
            event = Event(
                slot_id="slot_01",
                state="FREE",
                msg_id="slot_01-0001",
                sent_ts=1000,
                recv_ts=1100,
                qos=1,
                raw_topic="parking/telemetry/slot_01",
            )

            logger.record(event)
            logger.record(event)
            logger.close()

            check = sqlite3.connect(db_path)
            rows = check.execute(
                "SELECT msg_id, is_duplicate FROM received ORDER BY id"
            ).fetchall()
            check.close()

            self.assertEqual(rows, [("slot_01-0001", 0), ("slot_01-0001", 1)])


class TestParkingLotState(unittest.TestCase):
    def test_get_counts_after_updates(self):
        state = ParkingLotState(["slot_01", "slot_02", "slot_03"])

        state.update(
            Event("slot_01", "OCCUPIED", "slot_01-0001", 1000, 1100, 1, "parking/telemetry/slot_01")
        )
        state.update(
            Event("slot_02", "RESERVED", "slot_02-0001", 1001, 1101, 1, "parking/telemetry/slot_02")
        )

        self.assertEqual(
            state.get_counts(),
            {"free": 1, "occupied": 1, "reserved": 1, "total": 3},
        )


    def test_update_blocked_while_reservation_active(self):
        state = ParkingLotState(["slot_01"])
        state.transition_to_reserved("slot_01", lambda: None)

        # Sensor fires FREE/OCCUPIED — both should be ignored
        state.update(Event("slot_01", "FREE", "slot_01-0002", 1000, 1100, 1, "parking/telemetry/slot_01"))
        self.assertEqual(state.snapshot()["slot_01"], "RESERVED")

        state.update(Event("slot_01", "OCCUPIED", "slot_01-0003", 1001, 1101, 1, "parking/telemetry/slot_01"))
        self.assertEqual(state.snapshot()["slot_01"], "RESERVED")

    def test_update_allowed_after_timer_cancelled(self):
        import threading

        released: list[None] = []

        def expiry():
            released.append(None)

        state = ParkingLotState(["slot_01"])
        state.transition_to_reserved("slot_01", expiry)

        # Cancel the timer to simulate expiry
        timer = state._timers["slot_01"]
        timer.cancel()
        timer.join()

        # Now update should go through (timer is no longer alive)
        state.update(Event("slot_01", "FREE", "slot_01-0004", 1000, 1100, 1, "parking/telemetry/slot_01"))
        self.assertEqual(state.snapshot()["slot_01"], "FREE")
        self.assertNotIn("slot_01", state._timers)


class TestAlertService(unittest.TestCase):
    def test_check_fires_only_when_threshold_is_exceeded(self):
        state = ParkingLotState(["slot_01", "slot_02", "slot_03"])
        service = AlertService(state, threshold=0.5)
        fired: list[dict] = []
        service.register_handler(fired.append)

        first = Event("slot_01", "OCCUPIED", "slot_01-0001", 1000, 1100, 1, "parking/telemetry/slot_01")
        second = Event("slot_02", "OCCUPIED", "slot_02-0001", 1001, 1101, 1, "parking/telemetry/slot_02")

        state.update(first)
        service.check(first)
        self.assertEqual(fired, [])

        state.update(second)
        service.check(second)
        self.assertEqual(len(fired), 1)
        self.assertEqual(fired[0], {"free": 1, "occupied": 2, "reserved": 0, "total": 3})


if __name__ == "__main__":
    unittest.main()
