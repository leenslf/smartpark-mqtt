from __future__ import annotations

import queue
import threading
from collections.abc import Callable

from shared.protocol import Event


class EventBus:
    def __init__(self) -> None:
        self._queue: queue.Queue[Event | None] = queue.Queue()
        self._handlers: list[Callable[[Event], None]] = []
        self._thread: threading.Thread | None = None

    def publish(self, event: Event) -> None:
        self._queue.put(event)

    def subscribe(self, handler: Callable[[Event], None]) -> None:
        self._handlers.append(handler)

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._drain, name="parking-controller-event-bus", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if self._thread is None:
            return
        self._queue.put(None)
        self._thread.join(timeout=5)
        self._thread = None

    def _drain(self) -> None:
        while True:
            event = self._queue.get()
            try:
                if event is None:
                    return
                for handler in self._handlers:
                    handler(event)
            finally:
                self._queue.task_done()
