"""
Manual regression script for the SmartPark dashboard UI.

Drives the dashboard with synthetic QTimer updates — no live broker required.
Exercises:
  - Normal state (alert strip neutral)
  - Threshold crossing (occupied > 90 % → alert strip active)
  - Multiple consecutive above-threshold updates (alert must persist)
  - Recovery below threshold (alert strip clears)
  - Second threshold crossing (proves strip survives multiple cycles)
  - Full-recovery shutdown

Usage:
    python -m ui.test_dashboard_manual
"""

import sys

from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import QApplication

from ui.dashboard import ParkingDashboard

SLOT_IDS = [f"slot_{i + 1:02d}" for i in range(10)]

# Each scenario: (label, free, occupied, reserved, {slot_id: state, ...})
# The script prints each label so the operator can observe each transition.
_SCENARIOS = [
    # 0 — normal, 30 % occupied  (ratio=0.30 → no alert)
    ("Normal (30 % occupied — banner should be neutral)",
     7, 3, 0,
     {"slot_01": "FREE", "slot_02": "FREE", "slot_03": "OCCUPIED",
      "slot_04": "FREE", "slot_05": "OCCUPIED", "slot_06": "FREE",
      "slot_07": "FREE", "slot_08": "OCCUPIED", "slot_09": "FREE", "slot_10": "FREE"}),

    # 1 — threshold crossing: 10/10 = 100 %  (ratio=1.0 > 0.90 → ALERT)
    ("Threshold crossed: 100 % occupied — banner should turn RED",
     0, 10, 0,
     {"slot_01": "OCCUPIED", "slot_02": "OCCUPIED", "slot_03": "OCCUPIED",
      "slot_04": "OCCUPIED", "slot_05": "OCCUPIED", "slot_06": "OCCUPIED",
      "slot_07": "OCCUPIED", "slot_08": "OCCUPIED", "slot_09": "OCCUPIED",
      "slot_10": "OCCUPIED"}),

    # 2 — second consecutive above-threshold update (banner must persist)
    ("Still at 100 % (2nd update) — banner must REMAIN active",
     0, 10, 0,
     {"slot_01": "OCCUPIED"}),

    # 3 — third consecutive above-threshold update (banner must persist)
    ("Still at 100 % (3rd update) — banner must REMAIN active",
     0, 10, 0,
     {}),

    # 4 — 10/11 ≈ 90.9 %  (ratio still > 0.90 → ALERT persists)
    ("~91 % occupied (one RESERVED added) — banner must REMAIN active",
     0, 10, 1,
     {"slot_09": "OCCUPIED", "slot_10": "RESERVED"}),

    # 5 — recovery to 60 %  (ratio=0.60 → alert clears)
    ("Recovery: 60 % occupied — banner should clear to NEUTRAL",
     4, 6, 0,
     {"slot_01": "FREE", "slot_02": "FREE", "slot_09": "FREE", "slot_10": "FREE"}),

    # 6 — second threshold crossing: 10/10 = 100 % (proves strip survives multiple cycles)
    ("Second threshold crossing: 100 % — banner should turn RED again",
     0, 10, 0,
     {"slot_01": "OCCUPIED", "slot_02": "OCCUPIED", "slot_09": "OCCUPIED"}),

    # 7 — final recovery  (ratio=0.50 → alert clears)
    ("Final recovery: 50 % — banner should clear to NEUTRAL",
     5, 5, 0,
     {"slot_01": "FREE", "slot_02": "FREE", "slot_03": "FREE",
      "slot_09": "FREE", "slot_10": "FREE"}),
]

_STEP_INTERVAL_MS = 2000  # 2 s per scenario so a human can observe each state


def main() -> None:
    app = QApplication(sys.argv)

    # Broker connection will fail silently (port 9 is discard / not listening).
    window = ParkingDashboard(SLOT_IDS, "127.0.0.1", 9)
    window.resize(940, 660)
    window.show()

    step = [0]

    def tick() -> None:
        idx = step[0]
        if idx >= len(_SCENARIOS):
            print("\n[TEST] All scenarios complete — exiting.")
            app.quit()
            return

        label, free, occupied, reserved, slot_states = _SCENARIOS[idx]
        print(f"\n[TEST] Step {idx}: {label}")

        window.signals.summary_updated.emit(free, occupied, reserved)

        total = free + occupied + reserved
        ratio = occupied / total if total > 0 else 0.0
        window.signals.alert_triggered.emit(ratio > 0.90)

        for slot_id, state in slot_states.items():
            window.signals.slot_updated.emit(slot_id, state)

        step[0] += 1

    timer = QTimer()
    timer.timeout.connect(tick)
    timer.start(_STEP_INTERVAL_MS)

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
