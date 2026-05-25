import json

import paho.mqtt.client as mqtt
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import QLabel, QMainWindow, QVBoxLayout, QWidget

from shared.protocol import COMMAND_TOPIC
from ui.signals import ParkingSignals
from ui.widgets.alert_banner import AlertBanner
from ui.widgets.slot_grid import SlotGrid
from ui.widgets.summary_panel import SummaryPanel

_HEADER_STYLE = (
    "color: #ECEFF1; font-size: 15px; font-weight: bold; "
    "background-color: #102027; padding: 6px 0px; border-radius: 4px;"
)


class ParkingDashboard(QMainWindow):
    def __init__(self, slot_ids: list, broker_host: str, broker_port: int):
        super().__init__()
        self.setWindowTitle("SmartPark — Live Operations")

        # 1. WIDGET SETUP
        self.signals = ParkingSignals()

        header = QLabel("SmartPark  ·  Live Lot Operations")
        header.setAlignment(Qt.AlignCenter)
        header.setStyleSheet(_HEADER_STYLE)

        self._banner  = AlertBanner()
        self._summary = SummaryPanel()
        self._grid    = SlotGrid(slot_ids)

        central = QWidget()
        central.setStyleSheet("background-color: #162329;")
        layout  = QVBoxLayout(central)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)
        layout.addWidget(header)
        layout.addWidget(self._banner)
        layout.addWidget(self._summary)
        layout.addWidget(self._grid, stretch=1)
        self.setCentralWidget(central)

        self.signals.slot_updated.connect(self._grid.update_slot)
        self.signals.summary_updated.connect(self._summary.update)
        self.signals.alert_triggered.connect(self._banner.set_active)
        self._grid.reserve_requested.connect(self._on_reserve_requested)

        # 2. MQTT SETUP — deferred so the window appears before the blocking connect
        self._broker_host = broker_host
        self._broker_port = broker_port
        self._client = mqtt.Client()
        self._client.on_connect = self._on_connect
        self._client.on_message = self._on_message
        QTimer.singleShot(0, self._connect_mqtt)

    def _connect_mqtt(self):
        try:
            self._client.connect(self._broker_host, self._broker_port, keepalive=60)
        except Exception as exc:
            print(f"[MQTT] Could not connect to {self._broker_host}:{self._broker_port} — {exc}")
        self._client.loop_start()

    # 3. on_connect
    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            client.subscribe("parking/telemetry/+", qos=1)
            client.subscribe("parking/system/#",    qos=1)
            self.signals.connected.emit()
        else:
            print(f"[MQTT] Connection refused (rc={rc})")

    # 4. on_message
    def _on_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload)
        except Exception as exc:
            print(f"[MQTT] Bad payload on {msg.topic}: {exc}")
            return

        topic = msg.topic
        if topic.startswith("parking/telemetry/"):
            self.signals.slot_updated.emit(payload["slot_id"], payload["state"])
        elif topic == "parking/system/summary":
            free, occupied, reserved = (
                payload["free"], payload["occupied"], payload["reserved"]
            )
            self.signals.summary_updated.emit(free, occupied, reserved)
            total = free + occupied + reserved
            ratio = occupied / total if total > 0 else 0.0
            self.signals.alert_triggered.emit(ratio > 0.90)

    # 5. Reservation handler
    def _on_reserve_requested(self, slot_id: str):
        topic   = COMMAND_TOPIC.format(slot_id=slot_id)
        payload = json.dumps({"command": "RESERVE", "slot_id": slot_id})
        self._client.publish(topic, payload, qos=1)
        self._grid.update_slot(slot_id, "REQUESTING")

    # 6. closeEvent
    def closeEvent(self, event):
        self._client.loop_stop()
        self._client.disconnect()
        super().closeEvent(event)
