from __future__ import annotations

import queue
import sqlite3
import threading

from shared.protocol import Event


class MeasurementLogger:
    def __init__(self, db_path: str, run_id: str) -> None:
        self.db_path = db_path
        self.run_id = run_id
        self._seen_ids: set[str] = set()
        self._queue: queue.Queue[tuple[str, str, str, int, int, int] | None] = queue.Queue()
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._thread = threading.Thread(target=self._drain, name=f"measurement-{run_id}", daemon=True)
        self._thread.start()

    def record(self, event: Event) -> None:
        is_duplicate = 1 if event.msg_id in self._seen_ids else 0
        self._seen_ids.add(event.msg_id)
        self._queue.put_nowait(
            (self.run_id, event.msg_id, event.slot_id, event.sent_ts, event.recv_ts, is_duplicate)
        )

    def flush(self) -> None:
        self._queue.join()

    def close(self) -> None:
        self._queue.put(None)
        self._thread.join()
        self._conn.close()

    def _drain(self) -> None:
        while True:
            item = self._queue.get()
            try:
                if item is None:
                    return
                self._conn.execute(
                    """
                    INSERT INTO received (
                        run_id,
                        msg_id,
                        slot_id,
                        sent_ts,
                        recv_ts,
                        is_duplicate
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    item,
                )
                self._conn.commit()
            finally:
                self._queue.task_done()
