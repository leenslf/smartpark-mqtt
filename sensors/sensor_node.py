"""Sensor node publisher for SmartPark MQTT."""

from __future__ import annotations

import json
import random
import threading
import time
from typing import Any

import paho.mqtt.client as mqtt

from shared.protocol import (
	BROKER_HOST,
	BROKER_PORT,
	HEADLESS_TRANSITIONS,
	MIN_HOLD_TIMES,
	TELEMETRY_TOPIC,
	Event,
	build_status_message,
)
from sensors.publisher_logger import PublisherLogger


class SensorNode:
	"""Publishes parking slot telemetry with a simple FREE/OCCUPIED FSM.

	Publishes ONLY on state transitions — no periodic heartbeat.
	All topic strings, payload schemas, and constants come from
	shared.protocol so this class never duplicates protocol definitions.
	"""

	def __init__(
		self,
		slot_id: str,
		broker_host: str = BROKER_HOST,
		broker_port: int = BROKER_PORT,
		qos: int = 0,
		min_hold_times: dict[str, int] | None = None,
		transition_interval: float = 1.0,
		mode: str = "random",
		logger: PublisherLogger | None = None,
		seed: int | None = None,
		jitter_factor: float = 0.2,
	) -> None:
		self.slot_id = slot_id
		self.broker_host = broker_host
		self.broker_port = broker_port
		self.qos = qos
		# Use protocol defaults, allow per-instance override
		self.min_hold_times = dict(min_hold_times or MIN_HOLD_TIMES)
		self.transition_interval = transition_interval
		self.mode = mode
		self.logger = logger
		self.jitter_factor = jitter_factor
		self._rng = random.Random(seed)

		self._state = "FREE"
		self._state_entered_at = time.time()
		self._message_counter = 0
		self._stop_event = threading.Event()
		self._thread: threading.Thread | None = None
		self._pending_mid_to_msg_id: dict[int, str] = {}

		self._client = mqtt.Client()
		self._client.on_publish = self._on_publish

	@property
	def topic(self) -> str:
		"""Telemetry topic for this slot, derived from protocol constant."""
		return TELEMETRY_TOPIC.format(slot_id=self.slot_id)

	def start(self) -> None:
		"""Connect to broker and start the publish loop thread."""
		if self._thread and self._thread.is_alive():
			return

		self._stop_event.clear()
		self._client.connect(self.broker_host, self.broker_port)
		self._client.loop_start()

		self._thread = threading.Thread(
			target=self._run_loop,
			name=f"slot-{self.slot_id}",
			daemon=True,
		)
		self._thread.start()

	def stop(self) -> None:
		"""Stop publish loop and disconnect cleanly from broker."""
		self._stop_event.set()

		if self._thread and self._thread.is_alive():
			self._thread.join(timeout=5)

		self._client.loop_stop()
		self._client.disconnect()

	def _on_publish(
		self,
		client: mqtt.Client,
		userdata: Any,
		mid: int,
		reason_code: Any = None,
		properties: Any = None,
	) -> None:
		"""MQTT publish callback — logs the matching message id."""
		_ = client, userdata, reason_code, properties
		msg_id = self._pending_mid_to_msg_id.pop(mid, "unknown")
		print(f"[slot {self.slot_id}] published {msg_id}")

	# ---- main loop --------------------------------------------------------

	def _run_loop(self) -> None:
		offset = self._rng.uniform(0, self.transition_interval)
		if self._stop_event.wait(offset):
			return

		while not self._stop_event.is_set():
			jittered = self.transition_interval * self._rng.uniform(
				1.0 - self.jitter_factor,
				1.0 + self.jitter_factor,
			)
			if self._stop_event.wait(jittered):
				break

			transitioned = self._maybe_transition_state()
			if transitioned:
				self._publish_current_state()

	def _maybe_transition_state(self) -> bool:
		"""Attempt an FSM transition. Returns True if state changed."""
		now = time.time()
		min_hold = float(self.min_hold_times.get(self._state, 0))
		held_for = now - self._state_entered_at

		if held_for < min_hold:
			return False

		# Determine valid next states from protocol FSM
		reachable = HEADLESS_TRANSITIONS.get(self._state, set())
		if not reachable:
			return False

		if self.mode == "random":
			should_switch = self._rng.choice([True, False])
		else:
			# "forced" mode: always transition (used by ExperimentController)
			should_switch = True

		if should_switch:
			previous = self._state
			# In headless mode each state has exactly one reachable target,
			# but we pick from the set for forward-compatibility.
			self._state = self._rng.choice(sorted(reachable))
			self._state_entered_at = now
			print(f"[slot {self.slot_id}] state {previous} -> {self._state}")
			return True

		return False

	# ---- publish -----------------------------------------------------------

	def _publish_current_state(self) -> None:
		"""Build payload via protocol, stamp sent_ts, publish, and log."""
		self._message_counter += 1

		# Use protocol builder — keeps payload schema in one place
		payload = build_status_message(
			slot_id=self.slot_id,
			state=self._state,
			msg_counter=self._message_counter,
			qos=self.qos,
		)

		# Stamp sent_ts as late as possible before publish() — integer ms
		payload["sent_ts"] = time.time_ns() // 1_000_000

		raw = json.dumps(payload)
		result = self._client.publish(self.topic, raw, qos=self.qos)
		self._pending_mid_to_msg_id[result.mid] = payload["msg_id"]

		# Log via PublisherLogger (ground-truth for loss calculation)
		if self.logger is not None:
			event = Event(
				slot_id=payload["slot_id"],
				state=payload["state"],
				msg_id=payload["msg_id"],
				sent_ts=payload["sent_ts"],
				recv_ts=0,
				qos=self.qos,
				raw_topic=self.topic,
			)
			self.logger.log(event)


if __name__ == "__main__":
	sensor_node = SensorNode(slot_id="slot_01", qos=0)
	sensor_node.start()
	try:
		time.sleep(10)
	finally:
		sensor_node.stop()
