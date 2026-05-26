"""Launch parking_controller only — no automatic sensor nodes."""

import signal
import sys
import time

import parking_controller.parking_controller as ctrl
from shared.protocol import ExperimentConfig

N_SLOTS = 10

config = ExperimentConfig(
    run_id="manual-run",
    qos=1,
    n_slots=N_SLOTS,
    transition_rate=1.0,
    duration_s=0,
    network_condition="normal",
    loss_pct=0.0,
    delay_ms=0,
    started_at=int(time.time() * 1000),
)

print("[stack] Starting parking controller...")
ctrl.start(config, enable_logging=False)
print("[stack] Ready — click slots in the UI to reserve them. Ctrl+C to stop.")

def _shutdown(sig, frame):
    print("\n[stack] Shutting down...")
    ctrl.stop()
    sys.exit(0)

signal.signal(signal.SIGINT, _shutdown)
signal.signal(signal.SIGTERM, _shutdown)

while True:
    time.sleep(1)
