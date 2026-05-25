# Central PyQt5 signals for inter-component communication
from PyQt5.QtCore import QObject, pyqtSignal


class ParkingSignals(QObject):
    slot_updated    = pyqtSignal(str, str)       # slot_id, new_state
    summary_updated = pyqtSignal(int, int, int)  # free, occupied, reserved
    alert_triggered = pyqtSignal(bool)           # True = alert active
    connected       = pyqtSignal()               # broker connection confirmed
