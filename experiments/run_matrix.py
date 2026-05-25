"""Execute repeated SmartPark experiments from a JSON matrix."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any, Sequence

from experiments.experiment_controller import run_experiment
from shared.protocol import ExperimentConfig

DEFAULT_MATRIX_PATH = "experiments/matrix.json"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run repeated experiments from a matrix file.")
    parser.add_argument("--matrix", default=DEFAULT_MATRIX_PATH)
    parser.add_argument("--runs", nargs="*")
    parser.add_argument("--reps", type=int, default=3)
    parser.add_argument("--cooldown", type=float, default=5)
    return parser


def load_matrix(matrix_path: str) -> list[dict[str, Any]]:
    with Path(matrix_path).open("r", encoding="utf-8") as handle:
        matrix = json.load(handle)
    if not isinstance(matrix, list):
        raise ValueError("matrix file must contain a JSON array")
    return matrix


def select_rows(rows: list[dict[str, Any]], run_ids: Sequence[str] | None) -> list[dict[str, Any]]:
    if not run_ids:
        return rows

    selected = [row for row in rows if row.get("run_id") in run_ids]
    selected_ids = {row.get("run_id") for row in selected}
    missing = [run_id for run_id in run_ids if run_id not in selected_ids]
    if missing:
        missing_text = ", ".join(missing)
        raise ValueError(f"unknown run_id(s): {missing_text}")
    return selected


def build_config(row: dict[str, Any], rep: int) -> ExperimentConfig:
    base_run_id = row["run_id"]
    return ExperimentConfig(
        run_id=f"{base_run_id}_rep{rep}",
        qos=row["qos"],
        n_slots=row["n_slots"],
        transition_rate=row["transition_rate"],
        duration_s=row["duration_s"],
        network_condition=row["network_condition"],
        loss_pct=row["loss_pct"],
        delay_ms=row["delay_ms"],
        started_at=time.time_ns() // 1_000_000,
    )


def run_matrix(matrix_path: str, run_ids: Sequence[str] | None, reps: int, cooldown: float) -> None:
    if reps < 1:
        raise ValueError("--reps must be at least 1")
    if cooldown < 0:
        raise ValueError("--cooldown must be non-negative")

    rows = load_matrix(matrix_path)
    selected_rows = select_rows(rows, run_ids)
    total_runs = len(selected_rows) * reps
    completed_runs = 0

    for row in selected_rows:
        for rep in range(1, reps + 1):
            config = build_config(row, rep)
            run_experiment(config)
            completed_runs += 1
            print(
                f"[{config.run_id}] done — "
                f"{config.duration_s}s, {config.n_slots} slots, qos={config.qos}, {config.network_condition}"
            )
            if completed_runs < total_runs:
                time.sleep(cooldown)


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    run_matrix(args.matrix, args.runs, args.reps, args.cooldown)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
