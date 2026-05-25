## [x 18-04-2026] Randomization
The current simulator can drift into a lockstep pattern because all slots
in a run are started from the controller with the same transition interval, the
same initial state, and nearly the same start time. That means many slots can
publish and become eligible for a state change at roughly the same moments.

Benefits of randomizing the interval and slot selection:
- More realistic parking behavior. Real parking slots do not all change state
  on a common cadence.
- Less burstiness. Staggered publishes reduce synchronized spikes at the broker,
  subscriber, event bus, and SQLite writers.
- Better experiment quality. QoS and loss measurements become less biased by
  artificial herd behavior caused by the simulator rather than the protocol.
- Better stress coverage. Randomized timing exercises more interleavings in the
  subscriber, measurement logger, and publisher logger paths.

How this can be done:
- Add per-slot jitter around the base transition interval, for example sampling
  each wait from a bounded range around the configured interval.
- Decouple "publish frequency" from "state transition frequency". Right now the
  controller maps transition_rate directly to transition_interval, which is
  really the loop period.
- Introduce a transition decision model that does not let every slot evaluate
  on the same cadence. Options include:
  - each slot draws its own next transition deadline independently
  - a central scheduler selects a subset of eligible slots each cycle
  - each slot keeps a transition probability derived from elapsed time instead
    of flipping on a fixed polling interval
- Randomize initial conditions when desired, such as initial state or the
  initial offset before the first publish/transition check.

Components that likely need refactoring:
- simulators/slot_simulator.py
  This is the main change. The loop currently waits on one fixed
  transition_interval and then always checks/publishes. It would need separate
  notions of publish cadence, transition timing, and possibly initial jitter.
- experiments/experiment_controller.py
  The controller currently computes one shared interval from transition_rate and
  passes it to every SlotSimulator. If per-slot jitter or a centralized slot
  scheduler is added, the controller will need to pass richer timing config.
- shared/protocol.py
  ExperimentConfig may need new fields, such as publish_rate, transition_jitter,
  initial_offset_jitter, or scheduler mode, so the experiment definition can
  express the new behavior explicitly.
- experiments/matrix.json and experiments/run_matrix.py
  If new timing parameters are introduced, the matrix format and loader will
  need to carry them into ExperimentConfig.
- tests/test_slot_simulator.py and tests/test_experiment_controller.py
  Existing tests assume a fixed loop period and deterministic startup shape.
  They would need to validate jitter bounds, scheduling rules, and non-lockstep
  startup behavior instead.

## [x 18-04-2026] Adding shared protocol to slot_simulator
## [x] Integration tests

## [x] Rename slotsimulator and subscriber

## [] MQTT topic coverage gaps

Three protocol topics are defined in `shared/protocol.py` but not fully handled end-to-end:

### [x] `parking/commands/{slot_id}`
- The UI publishes a RESERVE command to this topic when a FREE slot is clicked.
- Nothing subscribes to it. A command handler is needed that:
  - Subscribes to `parking/commands/#`
  - On `{"command": "RESERVE", "slot_id": ...}`, transitions that slot to RESERVED and publishes a telemetry update so the UI reflects the change
- Without this, clicking a slot leaves it stuck in REQUESTING until the simulator overwrites it.

### [] `parking/system/summary`
- The UI subscribes to this topic and uses it to update the summary panel (FREE / OCCUPIED / RESERVED counts) and trigger the 90% alert banner.
- Nothing publishes it. The parking controller backend (`parking_controller/parking_state.py`, `parking_controller/alerts.py`) tracks counts internally but never emits a summary message.
- A summary publisher is needed — either inside the parking controller or as a separate aggregator — that emits to this topic whenever slot counts change.

### [] `parking/system/alert`
- Defined in the protocol but not subscribed to or published anywhere in the current codebase.
- The UI uses `signals.alert_triggered` driven by the summary ratio, so the alert banner works without this topic — but a dedicated alert topic would allow external systems to react to lot-full conditions.
- Decide: publish here from the parking controller's `AlertService`, or remove the constant if it will stay unused.

## [] Dashboard
### [x] Reserve via UI
  - [] perhaps look into timeout?
### [] Summary widget
### [] Alert eidget