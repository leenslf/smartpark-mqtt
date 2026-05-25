import argparse
import sys

from PyQt5.QtWidgets import QApplication

from ui.dashboard import ParkingDashboard


def main():
    parser = argparse.ArgumentParser(description="SmartPark Dashboard")
    parser.add_argument("--slots",  type=int, default=10,        help="Number of parking slots")
    parser.add_argument("--broker", type=str, default="localhost", help="MQTT broker host")
    parser.add_argument("--port",   type=int, default=1883,       help="MQTT broker port")
    args = parser.parse_args()

    slot_ids = [f"slot_{i+1:02d}" for i in range(args.slots)]

    app = QApplication(sys.argv)
    window = ParkingDashboard(slot_ids, args.broker, args.port)
    window.resize(900, 600)
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
