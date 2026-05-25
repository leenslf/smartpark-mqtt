"""Sensor node launcher for SmartPark live/demo mode."""

from __future__ import annotations

import argparse
import signal
import threading
from typing import Sequence

from sensors.sensor_node import SensorNode


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Launch N SensorNode instances for live/demo mode.")
    parser.add_argument("--slots",    type=int,   default=10,          help="Number of sensor nodes to start")
    parser.add_argument("--broker",   type=str,   default="localhost",  help="MQTT broker host")
    parser.add_argument("--port",     type=int,   default=1883,         help="MQTT broker port")
    parser.add_argument("--interval", type=float, default=8.0,          help="Transition interval per slot in seconds")
    parser.add_argument("--jitter",   type=float, default=0.3,          help="Jitter factor applied to interval")
    parser.add_argument(
        "--seed", type=int, default=42,
        help="Base random seed; slot i uses seed+i. Pass 0 to disable seeding (fully random).",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    slot_ids = [f"slot_{i + 1:02d}" for i in range(args.slots)]
    # seed=0 is the sentinel for "no seeding"; map it to None for SensorNode
    base_seed: int | None = args.seed if args.seed != 0 else None

    nodes: list[SensorNode] = []
    for i, slot_id in enumerate(slot_ids):
        seed = base_seed + i if base_seed is not None else None
        node = SensorNode(
            slot_id=slot_id,
            broker_host=args.broker,
            broker_port=args.port,
            transition_interval=args.interval,
            jitter_factor=args.jitter,
            seed=seed,
            logger=None,  # live mode — no SQLite logging
        )
        nodes.append(node)

    stop_event = threading.Event()

    def _handler(signum: int, frame: object) -> None:
        _ = signum, frame
        print("\nShutting down gracefully…", flush=True)
        stop_event.set()

    signal.signal(signal.SIGINT, _handler)
    signal.signal(signal.SIGTERM, _handler)

    for node in nodes:
        node.start()

    print(
        f"Started {len(nodes)} sensor nodes → broker={args.broker}:{args.port}"
        f"  interval={args.interval}s  jitter=±{args.jitter * 100:.0f}%",
        flush=True,
    )

    stop_event.wait()

    for node in nodes:
        node.stop()

    print("All sensor nodes stopped.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
