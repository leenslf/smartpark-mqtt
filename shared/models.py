from dataclasses import dataclass

from shared.protocol import SQLITE_DB_PATH


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
    # Seed for per-slot RNG. Slot i uses base_seed + i so runs are reproducible.
    # None disables seeding (non-deterministic, legacy behaviour).
    base_seed: int | None = None
    # Fraction of transition_interval applied as ±jitter each tick.
    # 0.2 means each sleep is drawn from [0.8x, 1.2x] of the nominal interval.
    jitter_factor: float = 0.2
    # FSM transition mode for all slots in this run.
    # "random": 50 % chance to transition each tick (realistic behaviour).
    # "forced": transition every tick that clears min_hold_time (max throughput).
    mode: str = "random"
