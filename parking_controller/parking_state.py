from __future__ import annotations

import threading
from collections.abc import Callable

from shared.protocol import Event, RESERVATION_TIMEOUT_S


class ParkingLotState:
    def __init__(self, slot_ids: list[str]) -> None:
        self._states = {slot_id: "FREE" for slot_id in slot_ids}
        self._timers: dict[str, threading.Timer] = {}

    def update(self, event: Event) -> None:
        timer = self._timers.get(event.slot_id)
        if timer is not None and timer.is_alive():
            return  # reservation active — block sensor-driven FREE/OCCUPIED until timeout
        self._states[event.slot_id] = event.state
        if event.slot_id in self._timers:
            del self._timers[event.slot_id]

    def transition_to_reserved(
        self,
        slot_id: str,
        on_expiry_callback: Callable[[], None],
    ) -> bool:
        if self._states.get(slot_id) != "FREE":
            return False
        self._states[slot_id] = "RESERVED"
        timer = threading.Timer(RESERVATION_TIMEOUT_S, on_expiry_callback)
        timer.daemon = True
        timer.start()
        self._timers[slot_id] = timer
        return True

    def is_reservation_active(self, slot_id: str) -> bool:
        timer = self._timers.get(slot_id)
        return timer is not None and timer.is_alive()

    def get_counts(self) -> dict:
        free = sum(1 for state in self._states.values() if state == "FREE")
        occupied = sum(1 for state in self._states.values() if state == "OCCUPIED")
        reserved = sum(1 for state in self._states.values() if state == "RESERVED")
        return {
            "free": free,
            "occupied": occupied,
            "reserved": reserved,
            "total": len(self._states),
        }

    def snapshot(self) -> dict:
        return dict(self._states)
