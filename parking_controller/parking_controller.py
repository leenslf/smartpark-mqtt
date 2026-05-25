"""Thin coordinator for parking controller components."""

from __future__ import annotations

import argparse
import signal
import threading
from typing import Sequence

from parking_controller.measurement import MeasurementLogger
from shared.protocol import BROKER_HOST, BROKER_PORT, ExperimentConfig, slot_ids_for_run
from parking_controller.alerts import AlertService
from parking_controller.bus import EventBus
from parking_controller.consumer import MQTTConsumer
from parking_controller.parking_state import ParkingLotState
from parking_controller.summary_publisher import SummaryPublisher

_bus: EventBus | None = None
_consumer: MQTTConsumer | None = None
_measurement: MeasurementLogger | None = None
_state: ParkingLotState | None = None
_alerts: AlertService | None = None
_summary: SummaryPublisher | None = None


def start(
    config: ExperimentConfig | None = None,
    *,
    broker_host: str = BROKER_HOST,
    broker_port: int = BROKER_PORT,
    slot_ids: list[str] | None = None,
    enable_logging: bool = False,
) -> MeasurementLogger | None:
    global _bus, _consumer, _measurement, _state, _alerts, _summary

    stop()

    resolved_slot_ids = slot_ids if slot_ids is not None else slot_ids_for_run(config)
    _state = ParkingLotState(resolved_slot_ids)
    _alerts = AlertService(_state)
    _bus = EventBus()

    # Consumer is constructed before bus.start() so its publish method is available
    # to SummaryPublisher. The socket is not opened until _consumer.connect() below.
    _consumer = MQTTConsumer(broker_host, broker_port, _bus.publish, _state)
    _summary = SummaryPublisher(_state, _consumer.publish)

    if enable_logging:
        _measurement = MeasurementLogger(config.db_path, config.run_id)
        _bus.subscribe(_measurement.record)

    _bus.subscribe(_state.update)
    _bus.subscribe(_alerts.check)
    _bus.subscribe(_summary.on_event)

    try:
        _bus.start()
        _consumer.connect()
        return _measurement
    except Exception:
        if _consumer is not None:
            _consumer.disconnect()
            _consumer = None
        if _bus is not None:
            _bus.stop()
            _bus = None
        if _measurement is not None:
            _measurement.close()
            _measurement = None
        _state = None
        _alerts = None
        _summary = None
        raise


def stop() -> None:
    global _bus, _consumer, _measurement, _state, _alerts, _summary

    if _consumer is not None:
        _consumer.disconnect()
        _consumer = None
    if _bus is not None:
        _bus.stop()
        _bus = None
    _measurement = None
    _state = None
    _alerts = None
    _summary = None


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="SmartPark parking controller")
    parser.add_argument("--slots",  type=int, default=10,          help="Number of parking slots")
    parser.add_argument("--broker", type=str, default="localhost",  help="MQTT broker host")
    parser.add_argument("--port",   type=int, default=1883,         help="MQTT broker port")
    args = parser.parse_args(argv)

    slot_ids = [f"slot_{i + 1:02d}" for i in range(args.slots)]

    stop_event = threading.Event()

    def _handler(signum: int, frame: object) -> None:
        _ = signum, frame
        print("\nShutting down gracefully…", flush=True)
        stop_event.set()

    signal.signal(signal.SIGINT, _handler)
    signal.signal(signal.SIGTERM, _handler)

    start(broker_host=args.broker, broker_port=args.port, slot_ids=slot_ids)
    print(
        f"Parking controller started — {args.slots} slots, broker={args.broker}:{args.port}",
        flush=True,
    )

    stop_event.wait()
    stop()
    print("Parking controller stopped.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
