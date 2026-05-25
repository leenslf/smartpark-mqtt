# Reservation Flow

Documents the end-to-end path when a user reserves a parking slot through the dashboard.

---

## Actors

| Actor | File | Role |
|---|---|---|
| `SlotCell` | `ui/widgets/slot_cell.py` | Button widget per slot; emits reserve signal on click |
| `SlotGrid` | `ui/widgets/slot_grid.py` | Grid of cells; forwards the signal upward |
| `ParkingDashboard` | `ui/dashboard.py` | Handles the signal; publishes MQTT command |
| MQTT Broker | — | Routes messages between dashboard and controller |
| `MQTTConsumer` | `parking_controller/consumer.py` | Receives command; drives state transition |
| `ParkingLotState` | `parking_controller/parking_state.py` | Authoritative server-side slot state + expiry timer |
| `EventBus` | `parking_controller/bus.py` | Fans events out to all subscribers |
| `AlertService` | `parking_controller/alerts.py` | Re-evaluates occupancy threshold after each event |
| `MeasurementLogger` | `parking_controller/measurement.py` | Persists events to SQLite (when logging is enabled) |

---

## Step-by-step

### 1. User clicks a FREE slot

**`SlotCell._on_clicked`** — `ui/widgets/slot_cell.py:35`

The cell only acts when its current state is `FREE`. Any other state silently ignores the click.

```python
def _on_clicked(self):
    if self._state == "FREE":
        self.reserve_requested.emit(self._slot_id)
```

Emits: `SlotCell.reserve_requested(slot_id: str)`

---

### 2. Signal bubbles up through SlotGrid

**`SlotGrid.__init__`** — `ui/widgets/slot_grid.py:19`

`SlotGrid` passes the signal straight through — it does not transform it.

```python
cell.reserve_requested.connect(self.reserve_requested)
```

Emits: `SlotGrid.reserve_requested(slot_id: str)`

---

### 3. Dashboard publishes the MQTT command + optimistic UI update

**`ParkingDashboard._on_reserve_requested`** — `ui/dashboard.py:79`

Two things happen in the same call:

1. Publishes a `RESERVE` command to the broker (QoS 1).
2. Immediately sets the local cell to `REQUESTING` (blue) without waiting for the controller to confirm — optimistic update so the user sees instant feedback.

```python
def _on_reserve_requested(self, slot_id: str):
    topic   = COMMAND_TOPIC.format(slot_id=slot_id)   # parking/commands/{slot_id}
    payload = json.dumps({"command": "RESERVE", "slot_id": slot_id})
    self._client.publish(topic, payload, qos=1)
    self._grid.update_slot(slot_id, "REQUESTING")
```

MQTT topic published: `parking/commands/{slot_id}`

---

### 4. Broker delivers command to the controller

`MQTTConsumer` subscribes to `parking/commands/#` (QoS 1). When the message arrives, `on_message` detects the `parking/commands/` prefix and routes to `handle_command`.

```python
if msg.topic.startswith(COMMAND_TOPIC_PREFIX):
    self.handle_command(msg)
    return
```

---

### 5. Controller validates and transitions state

**`MQTTConsumer.handle_command`** — `parking_controller/consumer.py:66`

Checks the command is `RESERVE`, then delegates to `ParkingLotState`.

**`ParkingLotState.transition_to_reserved`** — `parking_controller/parking_state.py:17`

```python
def transition_to_reserved(self, slot_id, on_expiry_callback) -> bool:
    if self._states.get(slot_id) != "FREE":
        return False                        # slot already taken — reject silently
    self._states[slot_id] = "RESERVED"
    timer = threading.Timer(RESERVATION_TIMEOUT_S, on_expiry_callback)  # 300 s
    timer.daemon = True
    timer.start()
    self._timers[slot_id] = timer
    return True
```

- Returns `False` → slot was not FREE; `handle_command` stops here. The dashboard cell stays on `REQUESTING` indefinitely (no explicit rejection message is sent back).
- Returns `True` → state is now `RESERVED` and a 300-second expiry timer is running.

---

### 6. Controller emits a RESERVED event and publishes telemetry

**`MQTTConsumer.handle_command`** — `parking_controller/consumer.py:83`

On success, a synthetic `Event` is constructed and pushed onto the `EventBus`, then the same data is published as a telemetry message so the dashboard (and any other subscriber) learns about the new state.

```python
event = Event(slot_id=slot_id, state="RESERVED", ...)
self.on_event(event)                                          # → EventBus
self._client.publish(
    TELEMETRY_TOPIC.format(slot_id=slot_id), out, qos=1      # parking/telemetry/{slot_id}
)
```

---

### 7. EventBus fans the event to all subscribers

**`EventBus._drain`** — `parking_controller/bus.py:36`

Runs on a dedicated background thread. Calls every registered handler in order:

| Handler | Effect |
|---|---|
| `ParkingLotState.update` | Keeps server-side state map consistent with the event |
| `AlertService.check` | Re-evaluates whether occupied ratio exceeds 90 % threshold |
| `MeasurementLogger.record` | Writes the event row to SQLite (only when logging is enabled) |

---

### 8. Dashboard receives telemetry and confirms the slot

**`ParkingDashboard._on_message`** — `ui/dashboard.py:67`

The dashboard is subscribed to `parking/telemetry/+`. It receives the telemetry published in step 6 and emits a Qt signal that updates the cell.

```python
if topic.startswith("parking/telemetry/"):
    self.signals.slot_updated.emit(payload["slot_id"], payload["state"])
```

`SlotGrid.update_slot` → `SlotCell.update_state("RESERVED")` → cell renders orange.

---

### 9. Reservation expires after 300 seconds

**`MQTTConsumer._on_reservation_expired`** — `parking_controller/consumer.py:103`

The timer started in step 5 fires. The method constructs a `FREE` event and runs the same publish path as step 6 — `EventBus` + telemetry topic — which causes the dashboard cell to revert to green.

---

## Sequence diagram

```
User          SlotCell      SlotGrid     Dashboard       Broker      MQTTConsumer   ParkingLotState   EventBus
 |               |              |             |              |              |                |             |
 |---click------>|              |             |              |              |                |             |
 |               |--reserve_--->|             |              |              |                |             |
 |               |  requested   |--reserve_-->|              |              |                |             |
 |               |              |  requested  |              |              |                |             |
 |               |              |             |--RESERVE---->|              |                |             |
 |               |              |             |  (QoS 1)     |              |                |             |
 |               |              |             |              |--command---->|                |             |
 |               |              |             |              |              |                |             |
 |               |              |             |<-REQUESTING  |              |--transition--->|             |
 |               |              |             |  (local)     |              |  _to_reserved  |             |
 |               |              |             |              |              |<----true-------|             |
 |               |              |             |              |              |                |             |
 |               |              |             |              |              |---event------->|             |
 |               |              |             |              |              |  (RESERVED)    |---update--->|
 |               |              |             |              |              |                |   check     |
 |               |              |             |              |--telemetry-->|                |   record    |
 |               |              |             |<-telemetry---|              |                |             |
 |               |              |             |  RESERVED    |              |                |             |
 |               |              |             |              |              |                |             |
 |               |<--RESERVED---|             |              |              |                |             |
 |               |   (orange)   |             |              |              |                |             |
 |               |              |             |              |              |                |             |
 :               :    [300 s later]           :              :              :                :             :
 |               |              |             |              |              |--expired------->|             |
 |               |              |             |              |--telemetry-->|                |             |
 |               |              |             |<-telemetry---|              |                |             |
 |               |              |             |  FREE        |              |                |             |
 |               |<----FREE-----|             |              |              |                |             |
 |               |   (green)    |             |              |              |                |             |
```

---

## Process model

The UI and controller are **separate processes**. `ui/main.py` only starts `ParkingDashboard`, which creates its own raw paho `mqtt.Client`. It never imports or starts `MQTTConsumer`. The controller must be started independently (via `parking_controller.parking_controller.start()`). Both sides talk exclusively through the broker. If the controller is not running, commands publish successfully but nothing responds — the cell stays on `REQUESTING` indefinitely.

---

## Key design notes

- **Optimistic UI update**: the dashboard sets the cell to `REQUESTING` immediately on publish, before any controller acknowledgement. If the controller rejects the command (slot not FREE), there is no rejection message sent back — the cell will stay blue until a subsequent telemetry message arrives that corrects it.
- **QoS 1 for commands**: the command topic uses QoS 1 (at-least-once delivery) so the command is not silently dropped under poor network conditions.
- **Single reservation path**: `transition_to_reserved` only accepts `FREE → RESERVED`. `OCCUPIED` or already-`RESERVED` slots are rejected without any broker-level response.
- **Expiry is server-driven**: the 300-second timer lives in `MQTTConsumer` / `ParkingLotState` on the controller side. The dashboard has no knowledge of the timeout; it simply receives the resulting `FREE` telemetry when it fires.
