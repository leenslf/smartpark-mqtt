from __future__ import annotations

import json
from collections.abc import Callable

from parking_controller.parking_state import ParkingLotState
from shared.protocol import SUMMARY_TOPIC, Event, build_summary_message


class SummaryPublisher:
    def __init__(
        self,
        state: ParkingLotState,
        publish_fn: Callable[[str, str, int], None],
    ) -> None:
        self._state = state
        self._publish = publish_fn

    def on_event(self, event: Event) -> None:
        _ = event
        counts = self._state.get_counts()
        payload = json.dumps(
            build_summary_message(counts["free"], counts["occupied"], counts["reserved"])
        )
        self._publish(SUMMARY_TOPIC, payload, 0)
