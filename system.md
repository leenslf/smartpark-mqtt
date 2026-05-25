# SmartPark-MQTT — Developer Architecture Reference

## What It Is

Research-grade MQTT parking lot system with two modes:
- **Live** — PyQt5 dashboard + stateful parking controller; operators reserve slots interactively
- **Experiment** — headless harness with simulated sensors, `tc netem` impairments, and SQLite logging for QoS/latency analysis

Stack: Python 3, Paho-MQTT, PyQt5, SQLite (stdlib). Requires a running Mosquitto broker.

---

## Architecture

```
┌─────────────────────────────────────────────┐
│         MQTT Broker (Mosquitto)             │
│         localhost:1883                      │
└──────┬──────────────┬──────────┬────────────┘
       │              │          │
  telemetry       commands    summary
       │              │          │
┌──────▼──────┐  ┌────▼──────────▼──────────────┐
│ SensorNodes │  │   Parking Controller Process  │
│ (1 thread   │  │                               │
│  per slot)  │  │  MQTTConsumer                 │
│             │  │    → EventBus (queue+thread)  │
│ FREE ↔ OCC  │  │      → ParkingLotState        │
│  only       │  │      → AlertService (dead)    │
└─────────────┘  │      → SummaryPublisher       │
                 │      → MeasurementLogger      │
                 └───────────────────────────────┘
                              │ parking/system/summary
                 ┌────────────▼───────────────────┐
                 │  UI Process (PyQt5)            │
                 │  ParkingDashboard              │
                 │    ├── AlertBanner             │
                 │    ├── SummaryPanel            │
                 │    └── SlotGrid → SlotCell ×N  │
                 └────────────────────────────────┘
```

The controller and UI are **separate processes** — they share only the broker and `shared/protocol.py`.

---

## MQTT Topics

| Topic | QoS | Publisher | Subscriber | Payload |
|---|---|---|---|---|
| `parking/telemetry/{slot_id}` | 0 (sensor) / 1 (ctrl) | SensorNode, MQTTConsumer | MQTTConsumer, Dashboard | `{slot_id, state, msg_id, sent_ts, qos}` |
| `parking/commands/{slot_id}` | 1 | Dashboard | MQTTConsumer | `{command: "RESERVE", slot_id}` |
| `parking/system/summary` | 0 | SummaryPublisher | Dashboard | `{free, occupied, reserved, total}` |
| `parking/system/alert` | — | **nobody** | **nobody** | defined, unused |

---

## Startup

```bash
# Broker
mosquitto -c config/mosquitto.conf

# Environment
source setup_env.sh

# Live mode (controller + UI are separate)
python -m parking_controller.parking_controller   # start controller first
python -m ui.main --slots 10 --broker localhost --port 1883

# Single experiment
python -m experiments.experiment_controller --qos 1 --n-slots 10 --duration 60

# Batch matrix
python -m experiments.run_matrix [--matrix path] [--runs E1 E2] [--reps 3]
```

---

## Components

### `shared/protocol.py` — System Contract
Single source of truth for topic strings, payload builders, FSM rules, dataclasses. **Nothing else should hardcode topic strings.**

Key constants: `TELEMETRY_TOPIC`, `COMMAND_TOPIC`, `SUMMARY_TOPIC`, `RESERVATION_TIMEOUT_S = 300`, `ALERT_THRESHOLD = 0.9`, `FSM_TRANSITIONS` (FREE/OCC/RESERVED), `HEADLESS_TRANSITIONS` (FREE/OCC only for sensors).

> `shared/models.py` duplicates `Event` and `ExperimentConfig` with extra fields. **`protocol.py` is canonical** — `models.py` is vestigial.

---

### `sensors/sensor_node.py` — SensorNode
One instance per slot. Runs FREE↔OCCUPIED FSM on a daemon thread (`slot-{slot_id}`). Publishes only on state transitions (no heartbeat). `sent_ts` is stamped immediately before `client.publish()`.

- Paho `loop_start()` → MQTT network thread
- `_run_loop()` → FSM thread; sleeps with jitter, checks hold time, maybe transitions
- `PublisherLogger` enqueues each publish to the `sent` SQLite table (async, non-blocking)

---

### `parking_controller/parking_controller.py` — Controller Facade
Module-level singletons; `start(config, enable_logging)` wires the pipeline:

1. `ParkingLotState` → `AlertService` → `EventBus`
2. `MQTTConsumer` (capture publish method) → `SummaryPublisher`
3. Optionally `MeasurementLogger`
4. Bus subscriptions **in order**: `state.update` → `alerts.check` → `summary.on_event` → `measurement.record`
5. Start bus thread → `consumer.connect()`

Order matters: state is updated before alerts/summary see each event.

---

### `parking_controller/consumer.py` — MQTTConsumer
Controller's MQTT gateway. Subscribes to `parking/telemetry/+` (QoS 0) and `parking/commands/#` (QoS 1).

- Telemetry → stamps `recv_ts`, checks active reservation, pushes `Event` to EventBus
  - If reservation active → re-publishes synthetic RESERVED correction (overrides UI)
- Commands → validates `RESERVE`, calls `ParkingLotState.transition_to_reserved()`
  - On success → synthetic RESERVED event to bus + telemetry publish
  - On failure → **silent** (no rejection sent; UI stays blue indefinitely)

> **Feedback loop**: consumer publishes to `parking/telemetry/{slot_id}` which it also subscribes to. The broker delivers its own corrections back, creating a second bus event. Currently idempotent but is an architectural smell.

---

### `parking_controller/parking_state.py` — ParkingLotState
Authoritative server-side slot state (`_states: dict[str, str]`).

- `update()` is a no-op if a reservation timer is alive for that slot (reservation guard)
- `transition_to_reserved()` arms a `threading.Timer(300, _on_reservation_expired)`

> **No lock on `_states`/`_timers`**. Accessed from EventBus thread, Paho network thread, and Timer callbacks. GIL protects individual dict ops but not composite read-check-write sequences.

---

### `parking_controller/bus.py` — EventBus
In-process pub/sub. Single drain thread dequeues `Event` objects and calls handlers sequentially. `None` is the shutdown poison pill.

---

### `parking_controller/alerts.py` — AlertService
Evaluates occupancy ratio after each event. **In live mode, no handlers are ever registered** — `register_handler()` is only called in tests. The check runs but fires into an empty list. Dead code path.

---

### `parking_controller/summary_publisher.py` — SummaryPublisher
Publishes `parking/system/summary` on **every** event (including correction re-publishes). At 50 slots × 5 Hz = up to 250 summary publishes/sec, each recomputing counts via a full dict scan.

---

### `parking_controller/measurement.py` — MeasurementLogger
Async SQLite writer for received events. Dedup via in-memory `_seen_ids` set. Queue-based drain thread; connection opened with `check_same_thread=False`.

Writes to: `received(run_id, msg_id, slot_id, sent_ts, recv_ts, is_duplicate)`.

---

### `ui/dashboard.py` — ParkingDashboard
Separate Paho connection from the controller. Thread bridge via `ParkingSignals` (QObject with pyqtSignals) — Paho thread emits, Qt event loop delivers to main thread.

```python
class ParkingSignals(QObject):
    slot_updated    = pyqtSignal(str, str)       # slot_id, state
    summary_updated = pyqtSignal(int, int, int)  # free, occupied, reserved
    alert_triggered = pyqtSignal(bool)
    connected       = pyqtSignal()
```

Alert threshold (`ratio > 0.90`) is recomputed **in the dashboard** from summary messages — independent of `AlertService`.

Reservation: optimistic REQUESTING (blue) on click → controller confirms → RESERVED (orange). No timeout; no rejection path — cell stays blue if controller is down.

---

### `ui/widgets/slot_cell.py` — SlotCell

| State | Color | Symbol |
|---|---|---|
| FREE | `#43A047` green | ● |
| OCCUPIED | `#E53935` red | ■ |
| RESERVED | `#FB8C00` orange | ◆ |
| REQUESTING | `#1E88E5` blue | ◌ |

REQUESTING is UI-only; the controller has no knowledge of it.

---

### `experiments/experiment_controller.py`
Orchestrates a timed run: DB init → netem apply → controller start → sensor nodes start → `stop_event.wait(duration)` → ordered teardown. Requires `CAP_NET_ADMIN` for `tc` calls. Slot `i` uses seed `base_seed + i` for reproducibility.

### `experiments/run_matrix.py`
Iterates `matrix.json` (12 experiments: E1–E12 varying QoS 0/1/2, slots 10/50, rate 1/5 Hz, clean/5% loss) with N repetitions and cooldown between runs.

### `analysis/analyze.py`
**Entirely commented out.** Was designed to compute delivery rate, duplicate rate, avg/P95 latency, out-of-order count from SQLite. Experiment data accumulates but cannot currently be queried.

---

## State Ownership

| State | Owner | Thread(s) that write |
|---|---|---|
| Slot state (authoritative) | `ParkingLotState._states` | EventBus drain, Paho network |
| Slot state (display) | `SlotCell._state` | Qt main thread |
| Reservation timers | `ParkingLotState._timers` | Paho network, Timer callbacks |
| Seen msg IDs (dedup) | `MeasurementLogger._seen_ids` | EventBus drain |

Display state and authoritative state can briefly diverge during reservation correction. The correction re-publish mitigates but doesn't fully close the window.

---

## Known Issues

| # | Issue | Risk |
|---|---|---|
| 1 | No lock on `ParkingLotState` | Data race under high load with concurrent reservations |
| 2 | `AlertService` handlers never registered | Dead code; ALERT_TOPIC defined but unused |
| 3 | No reservation rejection message | UI stuck blue if controller rejects or is down |
| 4 | `shared/models.py` duplicates `protocol.py` | Confusion about canonical types |
| 5 | Consumer receives its own correction publishes | Extra bus events; idempotent now but fragile |
| 6 | `analysis/analyze.py` fully commented out | Experiment data silently accumulates with no analysis path |
| 7 | `SummaryPublisher` fires on every event | Up to 250 publish/sec at 50-slot 5 Hz; no change-gating |
| 8 | Clean sessions only | Telemetry lost on brief disconnect even at QoS 1/2 |
| 9 | No combined launcher | Must start Mosquitto → controller → UI manually in separate terminals |

---

## Quick Fixes (Priority Order)

1. **Lock `ParkingLotState`** — add `threading.Lock` around `_states`/`_timers` accesses
2. **Wire or remove `AlertService`** — register a handler that publishes to `ALERT_TOPIC`, or delete it
3. **Send rejection response** — re-publish FREE (or dedicated response) when `transition_to_reserved()` fails
4. **Delete `shared/models.py`** — consolidate into `protocol.py`
5. **Restore `analysis/analyze.py`** — experiment infrastructure is incomplete without it
6. **Rate-gate `SummaryPublisher`** — skip publish if counts unchanged from last publish
7. **Add a launcher** — Makefile or `run.py` that starts broker → controller → UI in order
