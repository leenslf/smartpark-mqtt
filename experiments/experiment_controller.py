"""Experiment runner for SmartPark MQTT."""

from __future__ import annotations

import argparse
import signal
import subprocess
import threading
import time
from pathlib import Path
from typing import Sequence

from shared import DatabaseInit, ExperimentConfig
from shared.protocol import slot_ids_for_run
from sensors.publisher_logger import PublisherLogger
from sensors.sensor_node import SensorNode
from parking_controller.measurement import MeasurementLogger
from parking_controller import parking_controller

DEFAULT_NETEM_INTERFACE = "lo"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a SmartPark MQTT experiment.")
    parser.add_argument("--run-id", dest="run_id", help="Unique run identifier.")
    parser.add_argument("--qos", type=int, choices=(0, 1, 2), required=True)
    parser.add_argument("--n-slots", type=int, required=True)
    parser.add_argument("--transition-rate", type=float, default=1.0)
    parser.add_argument("--duration", "--duration-s", dest="duration_s", type=int, required=True)
    parser.add_argument("--network-condition", default=None)
    parser.add_argument("--loss", dest="loss_pct", type=float, default=0.0)
    parser.add_argument("--delay", dest="delay_ms", type=int, default=0)
    parser.add_argument("--db-path", default="data/experiment.db")
    parser.add_argument("--netem-interface", default=DEFAULT_NETEM_INTERFACE)
    # Integer seed for per-slot RNG. Slot i is seeded with base_seed + i,
    # making state-transition sequences and phase offsets fully reproducible.
    # Omit to run without seeding (legacy non-deterministic behaviour).
    parser.add_argument("--base-seed", dest="base_seed", type=int, default=None)
    # ±fraction of transition_interval added as per-tick jitter.
    # 0.0 disables jitter; default 0.2 gives ±20 % spread.
    parser.add_argument(
        "--jitter-factor", dest="jitter_factor", type=float, default=0.2,
        metavar="F",
    )
    # FSM transition mode applied to every slot.
    # "random" is realistic; "forced" maximises publish rate for load tests.
    parser.add_argument(
        "--mode", choices=("random", "forced"), default="random",
    )
    return parser


def build_config(args: argparse.Namespace) -> ExperimentConfig:
    started_at = time.time_ns() // 1_000_000
    run_id = args.run_id or f"run_{started_at}"
    network_condition = args.network_condition or infer_network_condition(args.loss_pct, args.delay_ms)
    return ExperimentConfig(
        run_id=run_id,
        qos=args.qos,
        n_slots=args.n_slots,
        transition_rate=args.transition_rate,
        duration_s=args.duration_s,
        network_condition=network_condition,
        loss_pct=args.loss_pct,
        delay_ms=args.delay_ms,
        started_at=started_at,
        db_path=args.db_path,
        base_seed=args.base_seed,
        jitter_factor=args.jitter_factor,
        mode=args.mode,
    )


def infer_network_condition(loss_pct: float, delay_ms: int) -> str:
    if loss_pct <= 0 and delay_ms <= 0:
        return "clean"
    if loss_pct > 0 and delay_ms > 0:
        return "lossy-delayed"
    if loss_pct > 0:
        return "lossy"
    return "high-latency"


def transition_interval_from_rate(transition_rate: float) -> float:
    if transition_rate <= 0:
        raise ValueError("transition_rate must be greater than 0")
    return 1.0 / transition_rate


def ensure_db_directory(db_path: str) -> None:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)


def install_signal_handlers(stop_event: threading.Event) -> dict[int, signal.Handlers]:
    previous: dict[int, signal.Handlers] = {}

    def handler(signum: int, frame: object) -> None:
        _ = signum, frame
        print("\nShutting down gracefully…", flush=True)
        stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        previous[sig] = signal.getsignal(sig)
        signal.signal(sig, handler)
    return previous


def restore_signal_handlers(previous: dict[int, signal.Handlers]) -> None:
    for sig, handler in previous.items():
        signal.signal(sig, handler)


def clear_netem(interface: str = DEFAULT_NETEM_INTERFACE) -> None:
    try:
        subprocess.run(
            ["tc", "qdisc", "del", "dev", interface, "root"],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except FileNotFoundError:
        pass


def apply_netem(loss_pct: float, delay_ms: int, interface: str = DEFAULT_NETEM_INTERFACE) -> None:
    clear_netem(interface)

    command = ["tc", "qdisc", "replace", "dev", interface, "root", "netem"]
    if delay_ms > 0:
        command.extend(["delay", f"{delay_ms}ms"])
    if loss_pct > 0:
        command.extend(["loss", f"{loss_pct}%"])
    if command[-1] == "netem":
        return

    subprocess.run(command, check=True)


def _run_experiment(
    config: ExperimentConfig,
    *,
    netem_interface: str = DEFAULT_NETEM_INTERFACE,
    stop_event: threading.Event | None = None,
) -> None:
    ensure_db_directory(config.db_path)

    database = DatabaseInit(config.db_path)
    measurement_logger: MeasurementLogger | None = None
    publisher_loggers: list[PublisherLogger] = []
    simulators: list[SensorNode] = []
    local_stop_event = stop_event or threading.Event()
    installed_handlers = None if stop_event is not None else install_signal_handlers(local_stop_event)
    run_error: Exception | None = None

    try:
        database.initialize()
        database.insert_run(config)
        apply_netem(config.loss_pct, config.delay_ms, netem_interface)
        measurement_logger = parking_controller.start(config, enable_logging=True)

        transition_interval = transition_interval_from_rate(config.transition_rate)
        for i, slot_id in enumerate(slot_ids_for_run(config)):
            logger = PublisherLogger(config.db_path, config.run_id)
            # Derive a unique seed per slot so slots are desynchronised but
            # the whole run is still reproducible from base_seed alone.
            slot_seed = config.base_seed + i if config.base_seed is not None else None
            simulator = SensorNode(
                slot_id=slot_id,
                qos=config.qos,
                transition_interval=transition_interval,
                logger=logger,
                seed=slot_seed,
                jitter_factor=config.jitter_factor,
                mode=config.mode,
            )
            publisher_loggers.append(logger)
            simulators.append(simulator)
            simulator.start()

        local_stop_event.wait(config.duration_s)
    except Exception as exc:
        run_error = exc
    finally:
        cleanup_error = shutdown_experiment(
            simulators=simulators,
            measurement_logger=measurement_logger,
            publisher_loggers=publisher_loggers,
            database=database,
            netem_interface=netem_interface,
        )
        if installed_handlers is not None:
            restore_signal_handlers(installed_handlers)

    if run_error is not None:
        raise run_error
    if cleanup_error is not None:
        raise cleanup_error


def shutdown_experiment(
    *,
    simulators: Sequence[SensorNode],
    measurement_logger: MeasurementLogger | None,
    publisher_loggers: Sequence[PublisherLogger],
    database: DatabaseInit,
    netem_interface: str,
) -> Exception | None:
    errors: list[Exception] = []

    for simulator in simulators:
        try:
            simulator.stop()
        except Exception as exc:
            errors.append(exc)

    try:
        parking_controller.stop()
    except Exception as exc:
        errors.append(exc)

    if measurement_logger is not None:
        try:
            measurement_logger.flush()
        except Exception as exc:
            errors.append(exc)
        try:
            measurement_logger.close()
        except Exception as exc:
            errors.append(exc)

    for logger in publisher_loggers:
        try:
            logger.close()
        except Exception as exc:
            errors.append(exc)

    try:
        clear_netem(netem_interface)
    except Exception as exc:
        errors.append(exc)

    try:
        database.close()
    except Exception as exc:
        errors.append(exc)

    return errors[0] if errors else None


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    config = build_config(args)
    _run_experiment(config, netem_interface=args.netem_interface)
    return 0


def run_experiment(config: ExperimentConfig) -> None:
    _run_experiment(config)


if __name__ == "__main__":
    raise SystemExit(main())
