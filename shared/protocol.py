"""shared.protocol — single source of truth for the SmartPark-MQTT system.

All publishers, subscribers, and analysis scripts import constants and helpers
from here. Neither team member should hard-code topic strings, DB paths, or
message formats anywhere else.
"""

from dataclasses import dataclass
import json

# ---------------------------------------------------------------------------
# A. Broker connection
# ---------------------------------------------------------------------------

BROKER_HOST = "127.0.0.1"
BROKER_PORT = 1883

# ---------------------------------------------------------------------------
# B. Topic templates — call .format(slot_id=...) to use
# ---------------------------------------------------------------------------

TELEMETRY_TOPIC = "parking/telemetry/{slot_id}"
COMMAND_TOPIC = "parking/commands/{slot_id}"
SUMMARY_TOPIC = "parking/system/summary"
ALERT_TOPIC = "parking/system/alert"
TELEMETRY_WILDCARD = "parking/telemetry/+"
COMMAND_TOPIC_PREFIX        = "parking/commands/"
COMMAND_SUBSCRIBE_WILDCARD  = "parking/commands/#"
RESERVATION_TIMEOUT_S       = 300

# ---------------------------------------------------------------------------
# C. Valid states and occupancy alert threshold
# ---------------------------------------------------------------------------

STATES = {"FREE", "OCCUPIED", "RESERVED"}

ALERT_THRESHOLD = 0.9  # fraction of slots occupied before an alert is raised

# ---------------------------------------------------------------------------
# D. Message builders
# ---------------------------------------------------------------------------


def build_status_message(slot_id: str, state: str, msg_counter: int, qos: int) -> dict:
    """Build the status message payload dict.

    The caller is responsible for setting sent_ts immediately before publishing::

        msg = build_status_message("slot_03", "OCCUPIED", 142, 1)
        msg["sent_ts"] = time.time_ns() // 1_000_000
        client.publish(topic, json.dumps(msg), qos=qos)

    Returns a dict with keys: slot_id, state, msg_id, sent_ts (placeholder 0), qos.
    """
    return {
        "slot_id": slot_id,
        "state": state,
        "msg_id": make_msg_id(slot_id, msg_counter),
        "sent_ts": 0,  # placeholder — publisher fills this right before publish()
        "qos": qos,
    }


def build_summary_message(free: int, occupied: int, reserved: int) -> dict:
    """Build the system summary payload.

    Returns a dict with keys: free, occupied, reserved, total.
    """
    return {
        "free": free,
        "occupied": occupied,
        "reserved": reserved,
        "total": free + occupied + reserved,
    }


def build_command_message(slot_id: str, action: str) -> dict:
    """Build a reservation command payload.

    action should be 'RESERVE'.
    Returns a dict with keys: slot_id, action.
    """
    return {
        "slot_id": slot_id,
        "action": action,
    }


# ---------------------------------------------------------------------------
# E. Message parser
# ---------------------------------------------------------------------------


def parse_message(payload_bytes: bytes) -> dict:
    """Parse raw MQTT payload bytes into a dict.

    Raises ValueError on bad JSON.
    """
    try:
        return json.loads(payload_bytes)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ValueError(f"Failed to parse MQTT payload: {exc}") from exc


# ---------------------------------------------------------------------------
# F. msg_id helpers
# ---------------------------------------------------------------------------


def make_msg_id(slot_id: str, counter: int) -> str:
    """Return a formatted message ID.

    Format: ``slot_03-0142``
    """
    return f"{slot_id}-{counter:04d}"


def parse_msg_id(msg_id: str) -> tuple[str, int]:
    """Split a msg_id back into (slot_id, counter).

    Raises ValueError if the format is wrong.
    """
    parts = msg_id.rsplit("-", 1)
    if len(parts) != 2:
        raise ValueError(f"Invalid msg_id format (expected '<slot_id>-<NNNN>'): {msg_id!r}")
    slot_id, counter_str = parts
    if not counter_str.isdigit():
        raise ValueError(f"Invalid msg_id counter (expected digits): {msg_id!r}")
    return slot_id, int(counter_str)


# ---------------------------------------------------------------------------
# G. SQLite schema
# ---------------------------------------------------------------------------

SQLITE_DB_PATH = "data/experiment.db"


# ---------------------------------------------------------------------------
# I. FSM config
# ---------------------------------------------------------------------------

# Minimum hold times in seconds before a slot can transition out of a state (?)
MIN_HOLD_TIMES = {
    "FREE": 5,
    "OCCUPIED": 10,
    "RESERVED": 300,  # reservation timeout — auto-expires to FREE
}

# Valid FSM transitions: current_state -> set of reachable states
FSM_TRANSITIONS = {
    "FREE": {"OCCUPIED", "RESERVED"},
    "OCCUPIED": {"FREE"},
    "RESERVED": {"FREE", "OCCUPIED"},
}

# In headless/experiment mode, only these transitions are active
HEADLESS_TRANSITIONS = {
    "FREE": {"OCCUPIED"},
    "OCCUPIED": {"FREE"},
}


@dataclass
class Event:
    slot_id: str
    state: str
    msg_id: str
    sent_ts: int
    recv_ts: int
    qos: int
    raw_topic: str


@dataclass
class ExperimentConfig:
    run_id: str
    qos: int
    n_slots: int
    transition_rate: float
    duration_s: int
    network_condition: str
    loss_pct: float
    delay_ms: int
    started_at: int
    db_path: str = SQLITE_DB_PATH
    base_seed: int | None = None
    jitter_factor: float = 0.2
    mode: str = "random"


def slot_ids_for_run(config: ExperimentConfig) -> list[str]:
    return [f"slot_{i:02d}" for i in range(1, config.n_slots + 1)]
