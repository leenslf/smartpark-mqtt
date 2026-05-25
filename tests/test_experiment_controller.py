"""Tests for experiments.experiment_controller."""

from __future__ import annotations

import os
import sys
import threading
import types
import unittest
from argparse import Namespace

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

if "paho.mqtt.client" not in sys.modules:
    paho_module = types.ModuleType("paho")
    mqtt_module = types.ModuleType("paho.mqtt")
    mqtt_client_module = types.ModuleType("paho.mqtt.client")

    class DummyClient:
        def __init__(self, *args: object, **kwargs: object) -> None:
            _ = args, kwargs

        def connect(self, *args: object, **kwargs: object) -> None:
            _ = args, kwargs

        def loop_start(self) -> None:
            return None

        def loop_stop(self) -> None:
            return None

        def disconnect(self) -> None:
            return None

        def publish(self, *args: object, **kwargs: object):
            _ = args, kwargs
            return types.SimpleNamespace(mid=1)

    mqtt_client_module.Client = DummyClient
    mqtt_module.client = mqtt_client_module
    paho_module.mqtt = mqtt_module
    sys.modules["paho"] = paho_module
    sys.modules["paho.mqtt"] = mqtt_module
    sys.modules["paho.mqtt.client"] = mqtt_client_module

from experiments import experiment_controller as controller


class TestExperimentController(unittest.TestCase):
    def test_build_config_maps_loss_and_delay_cli_arguments(self):
        args = Namespace(
            run_id="run_cli",
            qos=1,
            n_slots=4,
            transition_rate=2.5,
            duration_s=30,
            network_condition=None,
            loss_pct=7.5,
            delay_ms=125,
            db_path="data/test.db",
            netem_interface="lo",
            base_seed=None,
            jitter_factor=0.2,
            mode="random",
        )

        config = controller.build_config(args)

        self.assertEqual(config.run_id, "run_cli")
        self.assertEqual(config.loss_pct, 7.5)
        self.assertEqual(config.delay_ms, 125)
        self.assertEqual(config.network_condition, "lossy-delayed")

    def test_run_experiment_enforces_required_startup_and_shutdown_order(self):
        test_case = self
        call_order: list[str] = []
        stop_event = threading.Event()
        stop_event.set()
        config = controller.ExperimentConfig(
            run_id="run_order",
            qos=1,
            n_slots=2,
            transition_rate=2.0,
            duration_s=10,
            network_condition="lossy-delayed",
            loss_pct=4.0,
            delay_ms=150,
            started_at=1_000,
            db_path="data/test.db",
        )

        class FakeDatabase:
            def __init__(self, db_path: str) -> None:
                self.db_path = db_path

            def initialize(self) -> None:
                call_order.append("db.initialize")

            def insert_run(self, run_config: controller.ExperimentConfig) -> None:
                test_case.assertEqual(run_config.run_id, "run_order")
                call_order.append("db.insert_run")

            def close(self) -> None:
                call_order.append("db.close")

        class FakeMeasurementLogger:
            def flush(self) -> None:
                call_order.append("measurement.flush")

            def close(self) -> None:
                call_order.append("measurement.close")

        class FakePublisherLogger:
            created = 0

            def __init__(self, db_path: str, run_id: str) -> None:
                _ = db_path, run_id
                type(self).created += 1
                self.index = type(self).created

            def close(self) -> None:
                call_order.append(f"publisher.close.{self.index}")

        class FakeSensorNode:
            def __init__(self, slot_id: str, **kwargs: object) -> None:
                _ = kwargs
                self.slot_id = slot_id

            def start(self) -> None:
                call_order.append(f"sim.start.{self.slot_id}")

            def stop(self) -> None:
                call_order.append(f"sim.stop.{self.slot_id}")

        measurement_logger = FakeMeasurementLogger()
        FakePublisherLogger.created = 0

        original_database_init = controller.DatabaseInit
        original_apply_netem = controller.apply_netem
        original_clear_netem = controller.clear_netem
        original_parking_controller_start = controller.parking_controller.start
        original_parking_controller_stop = controller.parking_controller.stop
        original_publisher_logger = controller.PublisherLogger
        original_sensor_node = controller.SensorNode

        try:
            controller.DatabaseInit = FakeDatabase
            controller.apply_netem = lambda loss_pct, delay_ms, interface: call_order.append("apply_netem")
            controller.clear_netem = lambda interface: call_order.append("clear_netem")
            controller.parking_controller.start = lambda run_config, enable_logging=False: call_order.append("parking_controller.start") or measurement_logger
            controller.parking_controller.stop = lambda: call_order.append("parking_controller.stop")
            controller.PublisherLogger = FakePublisherLogger
            controller.SensorNode = FakeSensorNode

            controller._run_experiment(config, netem_interface="lo", stop_event=stop_event)
        finally:
            controller.DatabaseInit = original_database_init
            controller.apply_netem = original_apply_netem
            controller.clear_netem = original_clear_netem
            controller.parking_controller.start = original_parking_controller_start
            controller.parking_controller.stop = original_parking_controller_stop
            controller.PublisherLogger = original_publisher_logger
            controller.SensorNode = original_sensor_node

        self.assertLess(call_order.index("db.initialize"), call_order.index("db.insert_run"))
        self.assertLess(call_order.index("db.insert_run"), call_order.index("apply_netem"))
        self.assertLess(call_order.index("apply_netem"), call_order.index("parking_controller.start"))
        self.assertLess(call_order.index("parking_controller.start"), call_order.index("sim.start.slot_01"))
        self.assertLess(call_order.index("parking_controller.start"), call_order.index("sim.start.slot_02"))
        self.assertLess(call_order.index("sim.stop.slot_01"), call_order.index("parking_controller.stop"))
        self.assertLess(call_order.index("sim.stop.slot_02"), call_order.index("parking_controller.stop"))
        self.assertLess(call_order.index("parking_controller.stop"), call_order.index("measurement.flush"))
        self.assertLess(call_order.index("measurement.flush"), call_order.index("measurement.close"))
        self.assertLess(call_order.index("measurement.close"), call_order.index("publisher.close.1"))
        self.assertLess(call_order.index("measurement.close"), call_order.index("publisher.close.2"))
        self.assertLess(call_order.index("publisher.close.2"), call_order.index("clear_netem"))
        self.assertLess(call_order.index("clear_netem"), call_order.index("db.close"))


if __name__ == "__main__":
    unittest.main()
