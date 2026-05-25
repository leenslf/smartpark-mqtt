"""Async publisher-side logger for sent telemetry events."""

from __future__ import annotations

import queue
import sqlite3
import threading

from shared.protocol import Event


class PublisherLogger:
    def __init__(self, db_path: str, run_id: str) -> None:
        self.db_path = db_path
        self.run_id = run_id
        self._queue: queue.Queue[tuple[str, str, str, int] | None] = queue.Queue()
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._thread = threading.Thread(target=self._drain_queue, name=f"publisher-log-{run_id}", daemon=True)
        self._thread.start()

    def log(self, event: Event) -> None:
        self._queue.put_nowait((self.run_id, event.msg_id, event.slot_id, event.sent_ts))

    def close(self) -> None:
        self._queue.put(None)
        self._thread.join()
        self._conn.close()

    def _drain_queue(self) -> None:
        while True:
            item = self._queue.get()
            if item is None:
                break
            self._conn.execute(
                "INSERT INTO sent (run_id, msg_id, slot_id, sent_ts) VALUES (?, ?, ?, ?)",
                item,
            )
            self._conn.commit()
