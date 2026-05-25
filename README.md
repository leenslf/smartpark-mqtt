# SmartPark-MQTT

Simulation-based IoT smart parking system using MQTT. Parking slots publish
state transitions to a Mosquitto broker; a parking controller persists everything to
SQLite; an analysis suite computes QoS performance metrics across experiments.

Built for BBM 460.

---

## Setup

**1. Install Mosquitto** (once, outside the project):

```bash
# macOS
brew install mosquitto

# Ubuntu / Debian
sudo apt install mosquitto mosquitto-clients
```

**2. Set up the Python environment:**

```bash
source setup_env.sh
```

This creates `.venv/`, activates it, and installs all dependencies. Safe to
run multiple times.

**3. Start the broker:**

```bash
mosquitto -c config/mosquitto.conf
```

---

## Project Structure

| Directory | Contents |
|-----------|----------|
| `sensors/` | MQTT publishers — one `SensorNode` per parking slot |
| `parking_controller/` | MQTT parking controller — persists telemetry to SQLite |
| `experiments/` | Experiment controller — orchestrates multi-slot runs across QoS levels |
| `analysis/` | Metrics pipeline — latency, delivery rate, duplicate rate; saves plots |
| `ui/` | Tkinter real-time dashboard — live slot grid and occupancy alerts |
| `shared/` | **Contract file** (`protocol.py`) — all constants, message builders, and schemas |
| `config/` | Mosquitto broker configuration |
| `data/` | Runtime output: SQLite DB, publisher CSVs, and figures (git-ignored) |
| `tests/` | Unit tests for `shared/protocol.py` |

---

## Running Tests

```bash
# With pytest
python -m pytest tests/

# With the standard library test runner
python -m unittest discover tests/
```


``` bash
# to start an experiment with both simulated sensors and parking controller
python -m experiments.experiment_controller --qos 1 --n-slots 10 --duration 60
# launch UI with 10 slotd
python3 -m ui.main --slots 10 --broker localhost --port 1883

# to have more control over the sensors and cotnroller
python -m sensors.launch_sensors --slots 10 --interval 20 --jitter 0.3
python -m parking_controller.parking_controller
```