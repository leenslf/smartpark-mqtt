from __future__ import annotations

import json
import logging
import time
from collections.abc import Callable
from typing import Any

import paho.mqtt.client as mqtt

from parking_controller.parking_state import ParkingLotState
from shared.protocol import (
    BROKER_HOST,
    BROKER_PORT,
    COMMAND_SUBSCRIBE_WILDCARD,
    COMMAND_TOPIC_PREFIX,
    Event,
    TELEMETRY_TOPIC,
    TELEMETRY_WILDCARD,
)


class MQTTConsumer:
    def __init__(
        self,
        broker_host: str = BROKER_HOST,
        broker_port: int = BROKER_PORT,
        on_event: Callable[[Event], None] | None = None,
        parking_lot_state: ParkingLotState | None = None,
    ) -> None:
        self.broker_host = broker_host
        self.broker_port = broker_port
        self.on_event = on_event or (lambda event: None)
        self._parking_lot_state = parking_lot_state
        self._client = mqtt.Client()
        self._client.on_message = self.on_message

    def connect(self) -> None:
        self._client.connect(self.broker_host, self.broker_port)
        self._client.subscribe(TELEMETRY_WILDCARD, qos=0)
        self._client.subscribe(COMMAND_SUBSCRIBE_WILDCARD, qos=1)
        self._client.loop_start()

    def publish(self, topic: str, payload: str, qos: int = 0) -> None:
        self._client.publish(topic, payload, qos=qos)

    def disconnect(self) -> None:
        self._client.loop_stop()
        self._client.disconnect()

    def on_message(self, client: mqtt.Client, userdata: Any, msg: mqtt.MQTTMessage) -> None:
        recv_ts = time.time_ns() // 1_000_000
        _ = client, userdata
        if msg.topic.startswith(COMMAND_TOPIC_PREFIX):
            self.handle_command(msg)
            return
        payload = json.loads(msg.payload)
        event = Event(
            slot_id=payload["slot_id"],
            state=payload["state"],
            msg_id=payload["msg_id"],
            sent_ts=payload["sent_ts"],
            recv_ts=recv_ts,
            qos=payload.get("qos", 0),
            raw_topic=msg.topic,
        )
        self.on_event(event)

        # If the slot has an active reservation, the sensor's raw message already
        # reached the UI directly via the broker. Re-publish the authoritative
        # RESERVED state to correct what the UI displays.
        if (
            self._parking_lot_state is not None
            and self._parking_lot_state.is_reservation_active(event.slot_id)
        ):
            ts = time.time_ns() // 1_000_000
            correction = json.dumps({
                "slot_id": event.slot_id,
                "state": "RESERVED",
                "msg_id": f"{event.slot_id}-lock-{ts}",
                "sent_ts": ts,
                "qos": 1,
            })
            self._client.publish(
                TELEMETRY_TOPIC.format(slot_id=event.slot_id), correction, qos=1
            )

    def handle_command(self, msg: mqtt.MQTTMessage) -> None:
        try:
            payload = json.loads(msg.payload)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            logging.warning("[handle_command] bad payload: %s", exc)
            return
        slot_id = payload.get("slot_id")
        command = payload.get("command")
        if command != "RESERVE":
            logging.warning("[handle_command] unknown command %r for slot %r", command, slot_id)
            return
        if self._parking_lot_state is None:
            return
        if self._parking_lot_state.transition_to_reserved(
            slot_id,
            on_expiry_callback=lambda: self._on_reservation_expired(slot_id),
        ):
            ts = time.time_ns() // 1_000_000
            event = Event(
                slot_id=slot_id,
                state="RESERVED",
                msg_id=f"{slot_id}-cmd-{ts}",
                sent_ts=ts,
                recv_ts=ts,
                qos=1,
                raw_topic=TELEMETRY_TOPIC.format(slot_id=slot_id),
            )
            self.on_event(event)
            out = json.dumps({
                "slot_id": event.slot_id,
                "state": event.state,
                "msg_id": event.msg_id,
                "sent_ts": event.sent_ts,
                "qos": event.qos,
            })
            self._client.publish(TELEMETRY_TOPIC.format(slot_id=slot_id), out, qos=1)

    def _on_reservation_expired(self, slot_id: str) -> None:
        ts = time.time_ns() // 1_000_000
        event = Event(
            slot_id=slot_id,
            state="FREE",
            msg_id=f"{slot_id}-cmd-{ts}",
            sent_ts=ts,
            recv_ts=ts,
            qos=1,
            raw_topic=TELEMETRY_TOPIC.format(slot_id=slot_id),
        )
        self.on_event(event)
        out = json.dumps({
            "slot_id": event.slot_id,
            "state": event.state,
            "msg_id": event.msg_id,
            "sent_ts": event.sent_ts,
            "qos": event.qos,
        })
        self._client.publish(TELEMETRY_TOPIC.format(slot_id=slot_id), out, qos=1)
