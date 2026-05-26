#!/bin/bash
cd /mnt/c/Users/ramad/smartpark-mqtt
venv_wsl/bin/python -c "import paho.mqtt, pandas; print('deps ok')"
tc qdisc show dev lo
echo "tc ok"
