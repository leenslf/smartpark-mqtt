#!/usr/bin/env bash
# setup_env.sh — one-command virtual environment setup for SmartPark-MQTT
# Usage: source setup_env.sh
# Idempotent: safe to run multiple times.

set -e

VENV_DIR=".venv"

if [ ! -d "$VENV_DIR" ]; then
    echo "[setup] Creating virtual environment at $VENV_DIR ..."
    python3 -m venv "$VENV_DIR"
else
    echo "[setup] Virtual environment already exists at $VENV_DIR — skipping creation."
fi

# Activate (works when sourced; no-op if already active)
# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

echo "[setup] Installing dependencies from requirements.txt ..."
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt

echo ""
echo "[setup] Done. Virtual environment is active."
echo "        Deactivate with: deactivate"
