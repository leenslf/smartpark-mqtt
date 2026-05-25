# Shared Module Guide

`shared/protocol.py` is the common contract for the SmartPark-MQTT system. It centralizes broker settings, topic names, payload builders and parsers, message ID helpers, and a few experiment constants so publishers, subscribers, and analysis code all speak the same protocol without duplicating strings or formats.

## protocol.py inventory

| Name | Kind | Description |
| --- | --- | --- |
| `BROKER_HOST` | constant | MQTT broker hostname used by local clients. |
| `BROKER_PORT` | constant | MQTT broker port. |
| `TELEMETRY_TOPIC` | constant | Topic template for per-slot telemetry; call `.format(slot_id=...)`. |
| `COMMAND_TOPIC` | constant | Topic template for per-slot command messages; call `.format(slot_id=...)`. |
| `SUMMARY_TOPIC` | constant | Topic for system-wide summary messages. |
| `ALERT_TOPIC` | constant | Topic for system-wide alert messages. |
| `TELEMETRY_WILDCARD` | constant | Wildcard subscription topic for all telemetry messages. |
| `STATES` | constant | Valid parking slot states: `FREE`, `OCCUPIED`, `RESERVED`. |
| `ALERT_THRESHOLD` | constant | Occupancy ratio above which an alert should be raised. |
| `build_status_message` | helper | Builds a telemetry payload with `slot_id`, `state`, `msg_id`, placeholder `sent_ts`, and `qos`. |
| `build_summary_message` | helper | Builds a summary payload with `free`, `occupied`, `reserved`, and `total`. |
| `build_command_message` | helper | Builds a command payload for a slot action such as `RESERVE`. |
| `parse_message` | helper | Decodes MQTT payload bytes from JSON into a Python dict. |
| `make_msg_id` | helper | Formats a message ID like `slot_03-0142`. |
| `parse_msg_id` | helper | Splits a message ID back into `(slot_id, counter)`. |
| `SQLITE_DB_PATH` | constant | Default SQLite path used by experiment code. |
| `MESSAGES_TABLE_SCHEMA` | constant | Legacy SQL string for the old single `messages` table. |
| `MESSAGES_INSERT` | constant | Legacy insert SQL for the old single `messages` table. |
| `PUBLISHER_CSV_COLUMNS` | constant | Legacy CSV column list for publisher-side logs. |
| `publisher_log_path` | helper | Legacy helper that returns the publisher CSV path for one experiment. |
| `MIN_HOLD_TIMES` | constant | Minimum time a slot should stay in each state before another transition. |
| `FSM_TRANSITIONS` | constant | Allowed state transitions in the full finite state machine. |
| `HEADLESS_TRANSITIONS` | constant | Reduced transition set used in headless experiment mode. |


### `Event`

Represents one telemetry message after the parking controller has parsed and timestamped it.

| Field | Meaning | Set by |
| --- | --- | --- |
| `slot_id: str` | Parking slot identifier. | Publisher |
| `state: str` | Slot state carried in the telemetry payload. | Publisher |
| `msg_id: str` | Unique message identifier. | Publisher |
| `sent_ts: int` | Publish timestamp in milliseconds. | Publisher |
| `recv_ts: int` | Receive timestamp in milliseconds. | ParkingController at receive time |
| `qos: int` | MQTT QoS used for the publish. | Publisher |
| `raw_topic: str` | Exact MQTT topic the message arrived on. | ParkingController at receive time |

### `ExperimentConfig`

Represents one experiment run configuration shared across publisher, subscriber, and database setup.

| Field | Meaning | Set by |
| --- | --- | --- |
| `run_id: str` | Unique run identifier. | Publisher / experiment runner |
| `qos: int` | MQTT QoS for the run. | Publisher / experiment runner |
| `n_slots: int` | Number of simulated parking slots. | Publisher / experiment runner |
| `transition_rate: float` | Transition rate used by the simulator. | Publisher / experiment runner |
| `duration_s: int` | Experiment duration in seconds. | Publisher / experiment runner |
| `network_condition: str` | Named network profile for the run. | Publisher / experiment runner |
| `loss_pct: float` | Packet loss percentage for the run. | Publisher / experiment runner |
| `delay_ms: int` | Artificial network delay in milliseconds. | Publisher / experiment runner |
| `started_at: int` | Run start timestamp. | Publisher / experiment runner |
| `db_path: str` | SQLite database path; defaults to `data/experiment.db`. | Publisher / experiment runner |

`ExperimentConfig` is not enriched by the parking controller at receive time; it is created before the run starts and then stored as run metadata.
