from __future__ import annotations

from collections.abc import Callable

from shared.protocol import ALERT_THRESHOLD, Event
from parking_controller.parking_state import ParkingLotState


class AlertService:
    def __init__(self, state: ParkingLotState, threshold: float = ALERT_THRESHOLD) -> None:
        self.state = state
        self.threshold = threshold
        self._handlers: list[Callable[[dict], None]] = []

    def register_handler(self, cb: Callable[[dict], None]) -> None:
        self._handlers.append(cb)

    def check(self, event: Event) -> None:
        _ = event
        counts = self.state.get_counts()
        total = counts["total"]
        if total == 0:
            return
        if counts["occupied"] / total > self.threshold:
            for handler in self._handlers: # look at this
                handler(counts)
