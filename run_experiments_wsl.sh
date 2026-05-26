#!/bin/bash
set -e
cd /mnt/c/Users/ramad/smartpark-mqtt

PYTHON=venv_wsl/bin/python

# Find mosquitto: prefer WSL-installed, fall back to Windows binary
if which mosquitto &>/dev/null; then
    echo "=== Starting Mosquitto broker (WSL) ==="
    mosquitto -c config/mosquitto.conf -d
else
    WINMOSQUITTO="/mnt/c/Program Files/mosquitto/mosquitto.exe"
    WINCONF=$(wslpath -w "$(pwd)/config/mosquitto.conf")
    echo "=== Starting Mosquitto broker (Windows fallback) ==="
    "$WINMOSQUITTO" -c "$WINCONF" &
    MOSQUITTO_WIN_PID=$!
fi

sleep 1

echo "=== Running experiment matrix (E1-E12, 1 rep each) ==="
PYTHONPATH=. $PYTHON -m experiments.run_matrix --reps 1 --cooldown 10

echo "=== Done. Results in data/experiment.db ==="

# Clean up broker
pkill mosquitto 2>/dev/null || kill "${MOSQUITTO_WIN_PID:-}" 2>/dev/null || true
