import sqlite3

from shared.protocol import ExperimentConfig


class DatabaseInit:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.conn = None

    def initialize(self) -> None:
        self.conn = sqlite3.connect(self.db_path)
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS runs (
                run_id TEXT PRIMARY KEY,
                qos INTEGER,
                n_slots INTEGER,
                transition_rate REAL,
                duration_s INTEGER,
                network_condition TEXT,
                loss_pct REAL,
                delay_ms INTEGER,
                started_at INTEGER
            )
            """
        )
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sent (
                msg_id TEXT PRIMARY KEY,
                run_id TEXT,
                slot_id TEXT,
                sent_ts INTEGER
            )
            """
        )
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS received (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT,
                msg_id TEXT,
                slot_id TEXT,
                sent_ts INTEGER,
                recv_ts INTEGER,
                is_duplicate INTEGER
            )
            """
        )
        self.conn.commit()

    def insert_run(self, config: ExperimentConfig) -> None:
        if self.conn is None:
            self.initialize()
        self.conn.execute(
            """
            INSERT INTO runs (
                run_id,
                qos,
                n_slots,
                transition_rate,
                duration_s,
                network_condition,
                loss_pct,
                delay_ms,
                started_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                config.run_id,
                config.qos,
                config.n_slots,
                config.transition_rate,
                config.duration_s,
                config.network_condition,
                config.loss_pct,
                config.delay_ms,
                config.started_at,
            ),
        )
        self.conn.commit()

    def close(self) -> None:
        if self.conn is not None:
            self.conn.close()
            self.conn = None
