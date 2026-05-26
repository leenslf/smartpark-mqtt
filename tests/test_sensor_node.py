"""Unit and integration tests for sensors.sensor_node."""

from __future__ import annotations  # keep annotations lazy so stubs injected by other test modules don't break type hints

import json
import os
import random
import re
import socket
import sys
import threading
import time
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock, patch

import paho.mqtt.client as mqtt

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from shared.protocol import BROKER_HOST, BROKER_PORT, MIN_HOLD_TIMES
from sensors.sensor_node import SensorNode


class TestSensorNodeCore(unittest.TestCase):
    # A1
    def test_constructor_parameters_and_defaults(self):
        sim = SensorNode(slot_id="slot_01")

        self.assertEqual(sim.slot_id, "slot_01")
        self.assertEqual(sim.broker_host, BROKER_HOST)
        self.assertEqual(sim.broker_port, BROKER_PORT)
        self.assertEqual(sim.qos, 0)
        self.assertEqual(sim.min_hold_times, dict(MIN_HOLD_TIMES))
        self.assertEqual(sim.transition_interval, 1.0)
        self.assertEqual(sim.mode, "random")
        self.assertEqual(sim._state, "FREE")
        self.assertEqual(sim.jitter_factor, 0.2)
        self.assertIsInstance(sim._rng, random.Random)

    # A2
    def test_fsm_min_hold_times_in_alternate_mode(self):
        sim = SensorNode(slot_id="slot_fsm", mode="alternate", seed=42)

        sim._state = "FREE"
        sim._state_entered_at = time.time() - 4.9
        sim._maybe_transition_state()
        self.assertEqual(sim._state, "FREE")

        sim._state_entered_at = time.time() - 5.1
        sim._maybe_transition_state()
        self.assertEqual(sim._state, "OCCUPIED")

        sim._state_entered_at = time.time() - 9.9
        sim._maybe_transition_state()
        self.assertEqual(sim._state, "OCCUPIED")

        sim._state_entered_at = time.time() - 10.1
        sim._maybe_transition_state()
        self.assertEqual(sim._state, "FREE")

    # A6
    def test_publish_loop_order_wait_then_transition_build_publish(self):
        sim = SensorNode(slot_id="slot_loop", mode="alternate", seed=42)
        events: list[str] = []
        wait_calls = [0]

        class RecordingEvent:
            def is_set(self_inner) -> bool:
                return False

            def wait(self_inner, timeout: float) -> bool:
                wait_calls[0] += 1
                if wait_calls[0] == 1:
                    events.append("phase_offset")
                    return False
                else:
                    events.append("wait")
                    return wait_calls[0] >= 3

        sim._stop_event = RecordingEvent()  # type: ignore[assignment]

        def fake_transition() -> bool:
            events.append("transition")
            return True

        def fake_publish() -> None:
            events.append("publish")

        sim._maybe_transition_state = fake_transition  # type: ignore[assignment]
        sim._publish_current_state = fake_publish  # type: ignore[assignment]

        sim._run_loop()

        self.assertEqual(events, ["phase_offset", "wait", "transition", "publish", "wait"])

    # A4
    def test_publish_uses_topic_json_and_qos(self):
        sim = SensorNode(slot_id="77", qos=1, seed=0)
        client = Mock()
        client.publish.return_value = SimpleNamespace(mid=42)
        sim._client = client

        sim._state = "OCCUPIED"
        sim._message_counter = 0
        sim._publish_current_state()

        client.publish.assert_called_once()
        topic, json_payload = client.publish.call_args.args[:2]
        qos_value = client.publish.call_args.kwargs.get("qos")

        self.assertEqual(topic, "parking/telemetry/77")
        self.assertEqual(qos_value, 1)
        parsed = json.loads(json_payload)
        self.assertSetEqual(set(parsed.keys()), {"msg_id", "slot_id", "state", "sent_ts", "qos"})
        self.assertEqual(parsed["msg_id"], "77-0001")
        self.assertEqual(parsed["slot_id"], "77")
        self.assertIn(parsed["state"], {"FREE", "OCCUPIED"})
        self.assertIsInstance(parsed["sent_ts"], int)
        self.assertEqual(parsed["qos"], 1)

    # A5
    def test_publish_logs_once_per_publish_when_logger_is_injected(self):
        logger = MagicMock()
        sim = SensorNode(slot_id="77", qos=1, logger=logger, seed=0)
        client = Mock()
        client.publish.return_value = SimpleNamespace(mid=42)
        sim._client = client

        sim._state = "FREE"
        sim._message_counter = 0
        sim._publish_current_state()

        logger.log.assert_called_once()
        event = logger.log.call_args.args[0]
        self.assertEqual(event.msg_id, "77-0001")
        self.assertEqual(event.slot_id, "77")
        self.assertEqual(event.state, "FREE")
        self.assertIsInstance(event.sent_ts, int)
        self.assertEqual(event.recv_ts, 0)
        self.assertEqual(event.qos, 1)
        self.assertEqual(event.raw_topic, "parking/telemetry/77")

    # A3
    def test_on_publish_logs_msg_id_and_clears_pending(self):
        sim = SensorNode(slot_id="slot_cb")
        sim._pending_mid_to_msg_id[7] = "slot_cb-0001"

        with patch("builtins.print") as mock_print:
            sim._on_publish(client=Mock(), userdata=None, mid=7)

        self.assertNotIn(7, sim._pending_mid_to_msg_id)
        mock_print.assert_called_once_with("[slot slot_cb] published slot_cb-0001")

    def test_start_stop_clean_shutdown_with_event(self):
        sim = SensorNode(slot_id="slot_shutdown")
        sim._client = Mock()

        def fake_run_loop() -> None:
            sim._stop_event.wait(0.2)

        sim._run_loop = fake_run_loop  # type: ignore[assignment]

        sim.start()
        self.assertTrue(sim._thread is not None and sim._thread.is_alive())

        sim.stop()

        self.assertTrue(sim._stop_event.is_set())
        self.assertFalse(sim._thread is not None and sim._thread.is_alive())
        sim._client.connect.assert_called_once()
        sim._client.loop_start.assert_called_once()
        sim._client.loop_stop.assert_called_once()
        sim._client.disconnect.assert_called_once()

    # C1
    def test_seeded_reproducibility(self):
        kwargs = dict(
            slot_id="slot_repro",
            seed=123,
            transition_interval=0.1,
            jitter_factor=0.0,
            mode="random",
            min_hold_times={"FREE": 0, "OCCUPIED": 0, "RESERVED": 300},
        )
        sim1 = SensorNode(**kwargs)
        sim2 = SensorNode(**kwargs)
        sim1._client = Mock()
        sim2._client = Mock()

        states1: list[str] = []
        states2: list[str] = []
        for _ in range(20):
            sim1._state_entered_at = time.time() - 1000
            sim2._state_entered_at = time.time() - 1000
            sim1._maybe_transition_state()
            sim2._maybe_transition_state()
            states1.append(sim1._state)
            states2.append(sim2._state)

        self.assertEqual(states1, states2)

    # C2
    def test_different_seeds_diverge(self):
        common_kwargs = dict(
            slot_id="slot_div",
            transition_interval=0.1,
            jitter_factor=0.0,
            mode="random",
            min_hold_times={"FREE": 0, "OCCUPIED": 0, "RESERVED": 300},
        )
        sim1 = SensorNode(**common_kwargs, seed=100)
        sim2 = SensorNode(**common_kwargs, seed=200)

        states1: list[str] = []
        states2: list[str] = []
        for _ in range(20):
            sim1._state_entered_at = time.time() - 1000
            sim2._state_entered_at = time.time() - 1000
            sim1._maybe_transition_state()
            sim2._maybe_transition_state()
            states1.append(sim1._state)
            states2.append(sim2._state)

        self.assertNotEqual(states1, states2)

    # C3
    def test_phase_offset_occurs_before_loop(self):
        sim = SensorNode(slot_id="slot_phase", seed=42, transition_interval=1.0, jitter_factor=0.0)
        wait_timeouts: list[float] = []
        call_count = [0]

        class RecordingEvent:
            def is_set(self_inner) -> bool:
                return False

            def wait(self_inner, timeout: float) -> bool:
                call_count[0] += 1
                wait_timeouts.append(timeout)
                return call_count[0] >= 2

        sim._stop_event = RecordingEvent()  # type: ignore[assignment]
        sim._maybe_transition_state = lambda: False  # type: ignore[assignment]

        sim._run_loop()

        self.assertEqual(len(wait_timeouts), 2)
        # First wait is the phase offset: in [0, transition_interval)
        self.assertGreaterEqual(wait_timeouts[0], 0.0)
        self.assertLess(wait_timeouts[0], 1.0)
        # Second wait is the first tick; jitter_factor=0 → exactly transition_interval
        self.assertAlmostEqual(wait_timeouts[1], 1.0, places=9)

    # C4
    def test_jitter_varies_sleep_duration(self):
        sim = SensorNode(slot_id="slot_jitter", seed=7, transition_interval=1.0, jitter_factor=0.2)
        wait_timeouts: list[float] = []
        call_count = [0]

        class RecordingEvent:
            def is_set(self_inner) -> bool:
                return False

            def wait(self_inner, timeout: float) -> bool:
                call_count[0] += 1
                wait_timeouts.append(timeout)
                return call_count[0] >= 10  # 1 phase offset + 9 ticks

        sim._stop_event = RecordingEvent()  # type: ignore[assignment]
        sim._maybe_transition_state = lambda: False  # type: ignore[assignment]

        sim._run_loop()

        tick_sleeps = wait_timeouts[1:]  # skip phase offset
        self.assertEqual(len(tick_sleeps), 9)
        for t in tick_sleeps:
            self.assertGreaterEqual(t, 0.8)
            self.assertLessEqual(t, 1.2)
        self.assertFalse(all(t == tick_sleeps[0] for t in tick_sleeps))

    # C5
    def test_no_publish_without_transition(self):
        sim = SensorNode(
            slot_id="slot_nopub",
            mode="random",
            seed=0,
            min_hold_times={"FREE": 999, "OCCUPIED": 999, "RESERVED": 300},
        )
        client = Mock()
        sim._client = client

        results = [sim._maybe_transition_state() for _ in range(10)]

        self.assertTrue(all(r is False for r in results))
        client.publish.assert_not_called()

    # C6
    def test_payload_schema_matches_protocol(self):
        sim = SensorNode(slot_id="slot_schema", qos=2, seed=1)
        sim._state = "FREE"
        sim._message_counter = 0
        client = Mock()
        client.publish.return_value = SimpleNamespace(mid=1)
        sim._client = client

        sim._publish_current_state()

        client.publish.assert_called_once()
        json_str = client.publish.call_args.args[1]
        payload = json.loads(json_str)

        self.assertSetEqual(set(payload.keys()), {"slot_id", "state", "msg_id", "sent_ts", "qos"})
        self.assertRegex(payload["msg_id"], r"^.+-\d{4}$")
        self.assertIsInstance(payload["sent_ts"], int)
        now_ms = time.time_ns() // 1_000_000
        self.assertLessEqual(abs(payload["sent_ts"] - now_ms), 2000)
        self.assertEqual(payload["qos"], 2)


class TestSensorNodeIntegration(unittest.TestCase):
    def _broker_available(self, host: str = "localhost", port: int = 1883) -> bool:
        try:
            with socket.create_connection((host, port), timeout=1.0):
                return True
        except OSError:
            return False

    # A7
    def test_one_sensor_node_10s_json_arrives_at_broker(self):
        if not self._broker_available():
            self.skipTest("MQTT broker not available on localhost:1883")
        if not hasattr(mqtt, "MQTTMessage"):
            # Another test module injected a stub paho into sys.modules before
            # the real library was imported.  The stub lacks a real network
            # stack, so this integration test cannot run meaningfully.
            self.skipTest("paho stub active — real paho not available in this process")

        slot_id = f"testslot_{int(time.time())}"
        topic = f"parking/telemetry/{slot_id}"
        received: list[dict] = []
        lock = threading.Lock()

        parking_controller = mqtt.Client()

        def on_message(client: mqtt.Client, userdata, msg: mqtt.MQTTMessage) -> None:
            _ = client, userdata
            payload = json.loads(msg.payload.decode("utf-8"))
            with lock:
                received.append({"topic": msg.topic, "payload": payload})

        parking_controller.on_message = on_message
        parking_controller.connect("localhost", 1883)
        parking_controller.subscribe(topic, qos=1)
        parking_controller.loop_start()

        sensor_node = SensorNode(
            slot_id=slot_id,
            qos=1,
            transition_interval=1.0,
            mode="alternate",
            seed=99,
            min_hold_times={"FREE": 1, "OCCUPIED": 1, "RESERVED": 300},
        )

        try:
            sensor_node.start()
            time.sleep(10.0)
            sensor_node.stop()
            time.sleep(0.5)
        finally:
            parking_controller.loop_stop()
            parking_controller.disconnect()

        self.assertGreaterEqual(len(received), 3)

        counters: list[int] = []
        seen_states: set[str] = set()
        pattern = re.compile(rf"^{re.escape(slot_id)}-(\d{{4}})$")

        for item in received:
            msg = item["payload"]
            self.assertEqual(item["topic"], topic)
            self.assertSetEqual(set(msg.keys()), {"msg_id", "slot_id", "state", "sent_ts", "qos"})
            self.assertEqual(msg["slot_id"], slot_id)
            self.assertIn(msg["state"], {"FREE", "OCCUPIED"})
            self.assertIsInstance(msg["sent_ts"], int)

            match = pattern.match(msg["msg_id"])
            self.assertIsNotNone(match)
            counters.append(int(match.group(1)))
            seen_states.add(msg["state"])

        self.assertIn("FREE", seen_states)
        self.assertIn("OCCUPIED", seen_states)

        self.assertEqual(counters, sorted(counters))
        self.assertEqual(counters[0], 1)
        self.assertEqual(counters, list(range(1, len(counters) + 1)))


if __name__ == "__main__":
    unittest.main()
