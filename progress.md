# Progress
## v0.8 - 2026-05-17

- Fixed reserved slots being overwritten by sensor telemetry during the reservation window.
- Root cause: the broker fans out sensor telemetry to both the parking controller and the UI simultaneously. The parking controller's internal state guard blocked the conflicting update correctly, but the UI was already displaying the raw sensor state before any guard could act.
- `ParkingLotState.update()` now returns early for any slot with an active reservation timer, preventing internal state corruption from sensor-driven FREE/OCCUPIED events.
- `MQTTConsumer.on_message()` now detects when a received telemetry message conflicts with an active reservation and immediately re-publishes the authoritative `RESERVED` state to the telemetry topic, correcting what the UI displays.
- Added `ParkingLotState.is_reservation_active(slot_id)` to expose timer liveness to the consumer without exposing internal timer state directly.
- Added two unit tests covering the blocked-update and post-expiry-allowed-update cases.

## v0.7 - 2026-05-03
- Renamed components
## v0.6 - 2026-05-03

- Built a complete PyQt5 desktop dashboard (`ui/`) for real-time parking lot visualisation.
- Added `ui/signals.py`: central `ParkingSignals(QObject)` with four typed signals (`slot_updated`, `summary_updated`, `alert_triggered`, `connected`) used for thread-safe communication between the Paho MQTT thread and the Qt main thread.
- Added `ui/widgets/slot_cell.py`: `SlotCell(QFrame)` widget — 90×70 px cell displaying slot ID and state, color-coded by state (FREE/OCCUPIED/RESERVED/REQUESTING), emits `reserve_requested` signal on left-click when FREE.
- Added `ui/widgets/slot_grid.py`: `SlotGrid(QWidget)` that lays out N SlotCells in a `ceil(sqrt(N))`-column grid, exposes `update_slot()` and forwards `reserve_requested` upward.
- Added `ui/widgets/summary_panel.py`: `SummaryPanel(QFrame)` showing live FREE / OCCUPIED / RESERVED counts in a horizontal bar.
- Added `ui/widgets/alert_banner.py`: `AlertBanner(QLabel)` red banner shown when occupancy exceeds 90%, hidden by default.
- Added `ui/dashboard.py`: `ParkingDashboard(QMainWindow)` wiring all widgets together, managing its own Paho MQTT client (subscribes to `parking/telemetry/+` and `parking/system/#`), and publishing RESERVE commands on slot click.
- Added `ui/main.py`: CLI entry point with `--slots`, `--broker`, `--port` arguments; generates zero-padded slot IDs matching the simulator's naming convention.
- Fixed platform plugin resolution: set `QT_QPA_PLATFORM_PLUGIN_PATH` before `QApplication` loads to point at the bundled PyQt5 cocoa plugin.

## v0.5 - 2026-04-18

- Added `tests/test_integration_basic.py`, a standalone end-to-end check that runs the real subscriber with SQLite logging enabled and 3 real slot simulators against the (run this on your host before running the test) Mosquitto broker on `localhost:1883`.
- The script lets the system run briefly, then verifies the `received` table contains rows for all 3 slots with valid `msg_id` format, non-duplicate deliveries, and `recv_ts >= sent_ts`.

## v0.4 - 2026-04-18

- Made `MeasurementLogger` opt-in in the subscriber: `subscriber.start()` now accepts `enable_logging=False` (default) and only creates the logger, opens a SQLite connection, and registers the `record` handler when explicitly enabled.
- `ExperimentController` passes `enable_logging=True` to preserve existing behavior.

## v0.3 - 2026-04-18

- Added configurable experiment controls for `base_seed`, per-slot jitter, and simulator mode (`random` or `forced`) so runs can be reproducible or intentionally high-throughput.
- Changed the experiment runner and shared config model to carry the new timing/behavior settings through to each slot simulator instance.
- Changed the slot simulator to rely on shared protocol constants/builders, use per-slot seeded RNG, and publish transition-driven state updates with jittered timing instead of tightly synchronized behavior.
- Fixed simulator lockstep risk by desynchronizing slots while still allowing full-run reproducibility from a single base seed.
