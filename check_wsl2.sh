#!/bin/bash
which mosquitto && mosquitto --version | head -1 || echo "mosquitto not installed"
sudo tc qdisc add dev lo root netem loss 1% 2>&1 && sudo tc qdisc del dev lo root netem 2>&1 && echo "tc sudo ok" || echo "tc needs different perms"
