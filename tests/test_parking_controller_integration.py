"""Integration tests for parking_controller.ParkingSubscriber.

These tests are written to be resilient while the parking controller implementation is
still evolving. They focus on contract-level behavior from shared.protocol and
avoid brittle assumptions about internal implementation details.
"""

from __future__ import annotations

import inspect
import json
import os
import socket
import sqlite3
import sys
import tempfile
import time
import unittest
from importlib import import_module
from types import SimpleNamespace
from typing import Any, Callable

import paho.mqtt.client as mqtt

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from shared.protocol import (
    BROKER_HOST,
    BROKER_PORT,
    MESSAGES_TABLE_SCHEMA,
    TELEMETRY_TOPIC,
    build_status_message,
)


def _get_parking_controller_class() -> type | None:
    module = import_module("parking_controller.parking_controller")
    return getattr(module, "ParkingSubscriber", None)


def _broker_available(host: str = BROKER_HOST, port: int = BROKER_PORT) -> bool:
    try:
        with socket.create_connection((host, port), timeout=1.0):
            return True
    except OSError:
        return False


def _build_parking_controller_instance(cls: type, db_path: str):
    signature = inspect.signature(cls)
    kwargs: dict[str, Any] = {}

    for name, parameter in signature.parameters.items():
        if parameter.default is not inspect._empty:
            continue

        if name in {"db_path", "sqlite_db_path", "database_path"}:
            kwargs[name] = db_path
        elif name in {"experiment_id", "run_id"}:
            kwargs[name] = "it_parking_controller"
        elif name in {"broker_host", "host"}:
            kwargs[name] = BROKER_HOST
        elif name in {"broker_port", "port"}:
            kwargs[name] = BROKER_PORT
        elif name in {"network_condition", "condition"}:
            kwargs[name] = "clean"
        elif name in {"client", "mqtt_client"}:
            kwargs[name] = mqtt.Client()
        else:
            raise unittest.SkipTest(
                f"Unsupported required constructor parameter for integration tests: {name!r}"
            )

    parking_controller = cls(**kwargs)

    for attr_name in ("db_path", "sqlite_db_path", "database_path"):
        if hasattr(parking_controller, attr_name):
            setattr(parking_controller, attr_name, db_path)

    return parking_controller


def _find_message_handler(parking_controller: Any) -> Callable[..., Any]:
    for name in ("on_message", "_on_message", "handle_message", "_handle_message"):
        method = getattr(parking_controller, name, None)
        if callable(method):
            return method
    raise unittest.SkipTest("ParkingController does not expose a message handler callback yet")


def _dispatch_message(parking_controller: Any, topic: str, payload_bytes: bytes) -> None:
    handler = _find_message_handler(parking_controller)
    msg = SimpleNamespace(topic=topic, payload=payload_bytes)

    param_count = len(inspect.signature(handler).parameters)
    if param_count == 3:
        handler(None, None, msg)
    elif param_count == 2:
        handler(None, msg)
    elif param_count == 1:
        handler(msg)
    else:
        raise unittest.SkipTest(
            f"Unsupported callback signature for handler {handler.__name__}: {param_count} args"
        )


class TestParkingControllerIntegration(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self._tmp_dir.name, "parking_controller_it.db")

        cls = _get_parking_controller_class()
        if cls is None:
            self.skipTest("ParkingSubscriber class is not implemented in parking_controller/parking_controller.py")

        self.parking_controller = _build_parking_controller_instance(cls, self.db_path)
        self._ensure_messages_table()

    def tearDown(self) -> None:
        self._tmp_dir.cleanup()

    def _ensure_messages_table(self) -> None:
        init_methods = ("init_db", "_init_db", "setup_db", "_setup_db")
        for method_name in init_methods:
            method = getattr(self.parking_controller, method_name, None)
            if callable(method):
                method()
                return

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(MESSAGES_TABLE_SCHEMA)
            conn.commit()

    def _read_rows(self) -> list[tuple[Any, ...]]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                SELECT slot_id, state, qos, msg_id, sent_ts, recv_ts, is_duplicate, network_condition
                FROM messages
                ORDER BY id ASC
                """
            )
            return cursor.fetchall()

    def test_telemetry_message_persists_to_sqlite(self) -> None:
        msg = build_status_message("slot_42", "OCCUPIED", msg_counter=1, qos=1)
        msg["sent_ts"] = int(time.time() * 1000)

        topic = TELEMETRY_TOPIC.format(slot_id="slot_42")
        _dispatch_message(self.parking_controller, topic, json.dumps(msg).encode("utf-8"))

        rows = self._read_rows()
        self.assertGreaterEqual(len(rows), 1)

        slot_id, state, qos, msg_id, sent_ts, recv_ts, is_duplicate, network_condition = rows[-1]
        self.assertEqual(slot_id, "slot_42")
        self.assertEqual(state, "OCCUPIED")
        self.assertEqual(qos, 1)
        self.assertEqual(msg_id, msg["msg_id"])
        self.assertEqual(sent_ts, msg["sent_ts"])
        self.assertIsInstance(recv_ts, int)
        self.assertIn(int(is_duplicate), (0, 1))
        self.assertIsInstance(network_condition, str)

    def test_duplicate_msg_id_is_detected(self) -> None:
        topic = TELEMETRY_TOPIC.format(slot_id="slot_42")
        msg = build_status_message("slot_42", "FREE", msg_counter=7, qos=0)
        msg["sent_ts"] = int(time.time() * 1000)
        encoded = json.dumps(msg).encode("utf-8")

        _dispatch_message(self.parking_controller, topic, encoded)
        _dispatch_message(self.parking_controller, topic, encoded)

        rows = self._read_rows()
        self.assertGreaterEqual(len(rows), 1)

        duplicate_flags = [int(row[6]) for row in rows if row[3] == msg["msg_id"]]
        self.assertTrue(duplicate_flags, "No row found for duplicate msg_id")
        self.assertGreaterEqual(max(duplicate_flags), 1)

    def test_invalid_json_does_not_crash_and_does_not_insert(self) -> None:
        topic = TELEMETRY_TOPIC.format(slot_id="slot_bad")
        before = len(self._read_rows())

        _dispatch_message(self.parking_controller, topic, b"{not-valid-json")

        after = len(self._read_rows())
        self.assertEqual(after, before)


@unittest.skipUnless(_broker_available(), "MQTT broker not available on configured host/port")
class TestParkingControllerLiveBrokerIntegration(unittest.TestCase):
    def test_live_message_is_received_and_processed(self) -> None:
        cls = _get_parking_controller_class()
        if cls is None:
            self.skipTest("ParkingSubscriber class is not implemented in parking_controller/parking_controller.py")

        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = os.path.join(tmp_dir, "parking_controller_live.db")
            parking_controller = _build_parking_controller_instance(cls, db_path)

            start = getattr(parking_controller, "start", None)
            stop = getattr(parking_controller, "stop", None)
            if not callable(start) or not callable(stop):
                self.skipTest("ParkingController does not expose start/stop lifecycle methods yet")

            with sqlite3.connect(db_path) as conn:
                conn.execute(MESSAGES_TABLE_SCHEMA)
                conn.commit()

            start()
            try:
                publisher = mqtt.Client()
                publisher.connect(BROKER_HOST, BROKER_PORT)
                publisher.loop_start()
                try:
                    msg = build_status_message("slot_live", "FREE", msg_counter=1, qos=0)
                    msg["sent_ts"] = int(time.time() * 1000)
                    topic = TELEMETRY_TOPIC.format(slot_id="slot_live")
                    publisher.publish(topic, json.dumps(msg), qos=0)
                    time.sleep(1.0)
                finally:
                    publisher.loop_stop()
                    publisher.disconnect()
            finally:
                stop()

            with sqlite3.connect(db_path) as conn:
                count = conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0]

            self.assertGreaterEqual(count, 1)


if __name__ == "__main__":
    unittest.main()
