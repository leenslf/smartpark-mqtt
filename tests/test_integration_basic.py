import os
import re
import socket
import sqlite3
import sys
import tempfile
import time

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


def main() -> int:
    if not broker_available():
        print("FAIL: Mosquitto broker is not reachable on localhost:1883")
        return 1

    slot_ids = [f"slot_{i:02d}" for i in range(1, 4)]
    run_id = f"integration_{int(time.time())}"
    msg_id_pattern = re.compile(r"^slot_\d{2}-\d{4}$")

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "integration.db")
        DatabaseInit(db_path).initialize()
        config = ExperimentConfig(
            run_id=run_id,
            qos=1,
            n_slots=3,
            transition_rate=0.5,
            duration_s=15,
            network_condition="localhost",
            loss_pct=0.0,
            delay_ms=0,
            started_at=time.time_ns() // 1_000_000,
            db_path=db_path,
        )
        measurement = None
        simulators = [
            SensorNode(
                slot_id=slot_id,
                qos=1,
                transition_interval=2.0,
                mode="random",
                min_hold_times={"FREE": 2, "OCCUPIED": 2, "RESERVED": 300},
            )
            for slot_id in slot_ids
        ]

        try:
            measurement = parking_controller.start(config, enable_logging=True)
            for sim in simulators:
                sim.start()
            time.sleep(15)
            for sim in simulators:
                sim.stop()
            time.sleep(2.5)
            parking_controller.stop()
            if measurement is not None:
                measurement.flush()
                measurement.close()

            conn = sqlite3.connect(db_path)
            rows = conn.execute(
                """
                SELECT slot_id, msg_id, sent_ts, recv_ts, is_duplicate
                FROM received
                WHERE run_id = ?
                ORDER BY id
                """,
                (run_id,),
            ).fetchall()
            conn.close()

            seen_slots = {row[0] for row in rows}
            assert seen_slots == set(slot_ids), f"expected rows for {slot_ids}, got {sorted(seen_slots)}"
            assert rows, "expected at least one row in received"
            for slot_id, msg_id, sent_ts, recv_ts, is_duplicate in rows:
                assert msg_id_pattern.match(msg_id), f"bad msg_id: {msg_id}"
                assert msg_id.startswith(f"{slot_id}-"), f"msg_id {msg_id} does not match slot {slot_id}"
                assert recv_ts >= sent_ts, f"recv_ts < sent_ts for {msg_id}"
                assert is_duplicate == 0, f"duplicate flag set for {msg_id}"

            print("PASS: parking controller and 3 sensor nodes exchanged telemetry through Mosquitto.")
            print("PASS: SQLite rows cover all slots, timestamps are ordered, and duplicates stayed at 0.")
            return 0
        except Exception as exc:
            print(f"FAIL: {exc}")
            return 1
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


if __name__ == "__main__":
    raise SystemExit(main())
