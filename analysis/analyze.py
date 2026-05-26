"""Analyze SmartPark MQTT experiment runs stored in SQLite."""

from __future__ import annotations

import argparse
import json
import sqlite3
from dataclasses import asdict, dataclass
from typing import Any, Sequence

from shared.protocol import SQLITE_DB_PATH, parse_msg_id


@dataclass
class RunMetrics:
    run_id: str
    qos: int
    n_slots: int
    transition_rate: float
    duration_s: int
    network_condition: str
    loss_pct: float
    delay_ms: int
    started_at: int
    sent_count: int
    received_count: int
    unique_received_count: int
    duplicate_count: int
    delivery_rate: float
    duplicate_rate: float
    avg_latency_ms: float | None
    p95_latency_ms: float | None
    out_of_order_count: int
    out_of_order_rate: float


def fetch_run_metrics(db_path: str = SQLITE_DB_PATH, run_id: str | None = None) -> list[RunMetrics]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        runs = conn.execute(
            """
            SELECT
                run_id,
                qos,
                n_slots,
                transition_rate,
                duration_s,
                network_condition,
                loss_pct,
                delay_ms,
                started_at
            FROM runs
            WHERE (? IS NULL OR run_id = ?)
            ORDER BY started_at, run_id
            """,
            (run_id, run_id),
        ).fetchall()
        return [build_run_metrics(conn, row) for row in runs]
    finally:
        conn.close()


def build_run_metrics(conn: sqlite3.Connection, run_row: sqlite3.Row) -> RunMetrics:
    run_id = run_row["run_id"]
    sent_count = conn.execute("SELECT COUNT(*) FROM sent WHERE run_id = ?", (run_id,)).fetchone()[0]
    received_rows = conn.execute(
        """
        SELECT
            id,
            msg_id,
            slot_id,
            sent_ts,
            recv_ts,
            is_duplicate
        FROM received
        WHERE run_id = ?
        ORDER BY recv_ts, id
        """,
        (run_id,),
    ).fetchall()

    first_receipts: dict[str, sqlite3.Row] = {}
    duplicate_count = 0
    for row in received_rows:
        if row["is_duplicate"]:
            duplicate_count += 1
        first_receipts.setdefault(row["msg_id"], row)

    latencies = [
        row["recv_ts"] - row["sent_ts"]
        for row in first_receipts.values()
        if row["recv_ts"] is not None and row["sent_ts"] is not None
    ]
    unique_received_count = len(first_receipts)
    received_count = len(received_rows)
    out_of_order_count = count_out_of_order(first_receipts.values())

    return RunMetrics(
        run_id=run_id,
        qos=run_row["qos"],
        n_slots=run_row["n_slots"],
        transition_rate=run_row["transition_rate"],
        duration_s=run_row["duration_s"],
        network_condition=run_row["network_condition"],
        loss_pct=run_row["loss_pct"],
        delay_ms=run_row["delay_ms"],
        started_at=run_row["started_at"],
        sent_count=sent_count,
        received_count=received_count,
        unique_received_count=unique_received_count,
        duplicate_count=duplicate_count,
        delivery_rate=safe_rate(unique_received_count, sent_count),
        duplicate_rate=safe_rate(duplicate_count, received_count),
        avg_latency_ms=(sum(latencies) / len(latencies)) if latencies else None,
        p95_latency_ms=percentile(latencies, 0.95),
        out_of_order_count=out_of_order_count,
        out_of_order_rate=safe_rate(out_of_order_count, unique_received_count),
    )


def count_out_of_order(receipts: Sequence[sqlite3.Row]) -> int:
    highest_counter_by_slot: dict[str, int] = {}
    out_of_order_count = 0

    for row in receipts:
        _, counter = parse_msg_id(row["msg_id"])
        slot_id = row["slot_id"]
        previous = highest_counter_by_slot.get(slot_id)
        if previous is not None and counter < previous:
            out_of_order_count += 1
        highest_counter_by_slot[slot_id] = max(counter, previous or counter)

    return out_of_order_count


def safe_rate(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return numerator / denominator


def percentile(values: Sequence[int], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return float(ordered[0])

    position = fraction * (len(ordered) - 1)
    lower_index = int(position)
    upper_index = min(lower_index + 1, len(ordered) - 1)
    lower = ordered[lower_index]
    upper = ordered[upper_index]
    weight = position - lower_index
    return lower + (upper - lower) * weight


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Analyze SmartPark MQTT experiment runs.")
    parser.add_argument("--db-path", default=SQLITE_DB_PATH)
    parser.add_argument("--run-id")
    parser.add_argument("--json", action="store_true", dest="as_json")
    return parser


def format_table(metrics: Sequence[RunMetrics]) -> str:
    if not metrics:
        return "No runs found."

    headers = [
        "run_id",
        "qos",
        "sent",
        "unique_recv",
        "dupes",
        "delivery",
        "dup_rate",
        "avg_lat_ms",
        "p95_lat_ms",
        "ooo",
        "net",
    ]
    rows = [
        [
            metric.run_id,
            str(metric.qos),
            str(metric.sent_count),
            str(metric.unique_received_count),
            str(metric.duplicate_count),
            f"{metric.delivery_rate:.3f}",
            f"{metric.duplicate_rate:.3f}",
            format_metric(metric.avg_latency_ms),
            format_metric(metric.p95_latency_ms),
            str(metric.out_of_order_count),
            metric.network_condition,
        ]
        for metric in metrics
    ]
    widths = [max(len(header), *(len(row[index]) for row in rows)) for index, header in enumerate(headers)]
    lines = [
        " ".join(header.ljust(widths[index]) for index, header in enumerate(headers)),
        " ".join("-" * width for width in widths),
    ]
    lines.extend(
        " ".join(cell.ljust(widths[index]) for index, cell in enumerate(row))
        for row in rows
    )
    return "\n".join(lines)


def format_metric(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:.1f}"


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    metrics = fetch_run_metrics(args.db_path, args.run_id)
    if args.as_json:
        payload: list[dict[str, Any]] = [asdict(metric) for metric in metrics]
        print(json.dumps(payload, indent=2))
    else:
        print(format_table(metrics))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
