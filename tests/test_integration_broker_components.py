"""Integration test: SensorNode publishers + ParkingController pipeline via Mosquitto.

Exercises real components end-to-end — no mocking of the MQTT client.
Requires a running Mosquitto broker on localhost:1883.
"""

from __future__ import annotations

import os
import re
import shutil
import socket
import sqlite3
import sys
import tempfile
import time
import unittest
from collections import defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from shared.db import DatabaseInit
from shared.protocol import BROKER_HOST, BROKER_PORT, ExperimentConfig
from sensors.sensor_node import SensorNode
from parking_controller import parking_controller


def broker_available(host: str = BROKER_HOST, port: int = BROKER_PORT) -> bool:
    try:
        with socket.create_connection((host, port), timeout=1.0):
            return True
    except OSError:
        return False


@unittest.skipUnless(broker_available(), "Mosquitto broker is not reachable on localhost:1883")
class TestPublisherParkingControllerBrokerIntegration(unittest.TestCase):
    def _cleanup_dir(self, path: str) -> None:
        for _ in range(5):
            try:
                shutil.rmtree(path)
                return
            except PermissionError:
                time.sleep(0.2)

    def test_sensor_nodes_and_parking_controller_exchange_telemetry_via_broker(self) -> None:
        slot_ids = [f"slot_{i:02d}" for i in range(1, 4)]
        run_id = f"integration_{int(time.time())}"
        msg_id_pattern = re.compile(r"^slot_\d{2}-\d{4}$")

        tmpdir = tempfile.mkdtemp(prefix="smartpark_it_")
        db_init = None
        measurement = None
        simulators = []
        try:
            db_path = os.path.join(tmpdir, "integration.db")
            db_init = DatabaseInit(db_path)
            db_init.initialize()

            config = ExperimentConfig(
                run_id=run_id,
                qos=1,
                n_slots=3,
                transition_rate=2.0,
                duration_s=5,
                network_condition="localhost",
                loss_pct=0.0,
                delay_ms=0,
                started_at=time.time_ns() // 1_000_000,
                db_path=db_path,
            )

            simulators = [
                SensorNode(
                    slot_id=slot_id,
                    qos=1,
                    transition_interval=0.35,
                    mode="random",
                    seed=index,
                    jitter_factor=0.0,
                    min_hold_times={"FREE": 0, "OCCUPIED": 0, "RESERVED": 300},
                )
                for index, slot_id in enumerate(slot_ids, start=1)
            ]

            measurement = parking_controller.start(config, enable_logging=True)
            for sim in simulators:
                sim.start()

            time.sleep(4.0)

            for sim in simulators:
                sim.stop()
            simulators = []
            time.sleep(1.0)

            parking_controller.stop()
            measurement.flush()
            measurement.close()
            measurement = None

            with sqlite3.connect(db_path) as conn:
                rows = conn.execute(
                    """
                    SELECT slot_id, msg_id, sent_ts, recv_ts, is_duplicate
                    FROM received
                    WHERE run_id = ?
                    ORDER BY id
                    """,
                    (run_id,),
                ).fetchall()

            self.assertGreaterEqual(len(rows), 6, "Expected at least 2 messages per slot")

            seen_slots = {row[0] for row in rows}
            self.assertSetEqual(seen_slots, set(slot_ids))

            counters_by_slot: dict[str, list[int]] = defaultdict(list)
            for slot_id, msg_id, sent_ts, recv_ts, is_duplicate in rows:
                self.assertRegex(msg_id, msg_id_pattern)
                self.assertTrue(msg_id.startswith(f"{slot_id}-"))
                self.assertGreaterEqual(recv_ts, sent_ts)
                self.assertEqual(is_duplicate, 0)
                counters_by_slot[slot_id].append(int(msg_id.rsplit("-", 1)[1]))

            for slot_id in slot_ids:
                counters = counters_by_slot[slot_id]
                self.assertGreaterEqual(len(counters), 2)
                self.assertEqual(counters, sorted(counters), f"{slot_id}: counters not in order")
                self.assertEqual(counters[0], 1, f"{slot_id}: first received counter is not 1")

        finally:
            for sim in simulators:
                try:
                    sim.stop()
                except Exception:
                    pass
            try:
                parking_controller.stop()
            except Exception:
                pass
            if measurement is not None:
                try:
                    measurement.close()
                except Exception:
                    pass
            if db_init is not None:
                db_init.close()
            self._cleanup_dir(tmpdir)


if __name__ == "__main__":
    unittest.main()
