"""Shared helpers for querying run/controller mappings and phase markers."""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

MATCH_CSV_FILENAME = "npy_match.csv"
REQUIRED_MATCH_COLUMNS = ("status", "run_path", "controller_path")
BEST_CONTROLLER_PATTERN = re.compile(r"controller_(\d+)\.py$")
SIM_RUN_RELATIVE_PATTERN = re.compile(
    r"^sim/([^/]+)/([^/]+)/attempt(\d+)/run(\d+)\.npy$"
)
DESIGN_WHY_PREFIX = "design to meet specifications:"
TUNING_WHY_PREFIX = "tuning:"


@dataclass(frozen=True)
class MatchCsvRow:
    status: str
    run_path: str
    controller_path: str
    row_number: int


def load_match_csv_rows(results_folder: Path) -> tuple[list[MatchCsvRow], list[str]]:
    """Load and validate npy_match.csv rows from a results folder."""
    csv_path = results_folder / MATCH_CSV_FILENAME
    if not csv_path.exists():
        return [], [f"missing file {csv_path}"]

    rows: list[MatchCsvRow] = []
    issues: list[str] = []
    try:
        with csv_path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            fieldnames = set(reader.fieldnames or [])
            missing_columns = [
                name for name in REQUIRED_MATCH_COLUMNS if name not in fieldnames
            ]
            if missing_columns:
                return [], [
                    f"{csv_path} is missing required columns {missing_columns}"
                ]

            for row_number, row in enumerate(reader, start=2):
                status = str(row.get("status", "")).strip().upper()
                run_path = str(row.get("run_path", "")).strip()
                controller_path = str(row.get("controller_path", "")).strip()

                if not status or not run_path or not controller_path:
                    issues.append(
                        "skipped malformed row "
                        f"{row_number} in {csv_path}: "
                        f"status='{status}', run_path='{run_path}', "
                        f"controller_path='{controller_path}'"
                    )
                    continue

                rows.append(
                    MatchCsvRow(
                        status=status,
                        run_path=run_path,
                        controller_path=controller_path,
                        row_number=row_number,
                    )
                )
    except Exception as exc:  # noqa: BLE001
        return [], [f"failed to parse {csv_path} ({exc})"]

    return rows, issues


def build_controller_lookup(
    rows: list[MatchCsvRow],
    allowed_statuses: set[str] | None = None,
    duplicate_policy: str = "last",
) -> tuple[dict[str, tuple[str, str]], list[str]]:
    """Build controller_path -> (run_path, status) lookup."""
    if duplicate_policy not in {"last", "first", "error"}:
        raise ValueError(f"Unsupported duplicate_policy: {duplicate_policy!r}")

    normalized_statuses: set[str] | None = None
    if allowed_statuses is not None:
        normalized_statuses = {status.upper() for status in allowed_statuses}

    mapping: dict[str, tuple[str, str]] = {}
    issues: list[str] = []
    for row in rows:
        if normalized_statuses is not None and row.status not in normalized_statuses:
            continue

        existing = mapping.get(row.controller_path)
        next_value = (row.run_path, row.status)
        if existing is None:
            mapping[row.controller_path] = next_value
            continue

        if existing == next_value:
            issues.append(
                "duplicate mapping with identical value for "
                f"{row.controller_path} at row {row.row_number}"
            )
            continue

        if duplicate_policy == "last":
            issues.append(
                "duplicate controller mapping for "
                f"{row.controller_path}; overriding {existing} with {next_value} "
                f"(row {row.row_number})"
            )
            mapping[row.controller_path] = next_value
        elif duplicate_policy == "first":
            issues.append(
                "duplicate controller mapping for "
                f"{row.controller_path}; keeping first value {existing} "
                f"and skipping row {row.row_number}"
            )
        else:  # duplicate_policy == "error"
            issues.append(
                "duplicate controller mapping for "
                f"{row.controller_path}; conflict between {existing} and "
                f"{next_value} (row {row.row_number})"
            )

    return mapping, issues


def build_run_lookup(
    rows: list[MatchCsvRow],
    allowed_statuses: set[str] | None = None,
    duplicate_policy: str = "last",
) -> tuple[dict[str, tuple[str, str]], list[str]]:
    """Build run_path -> (controller_path, status) lookup."""
    if duplicate_policy not in {"last", "first", "error"}:
        raise ValueError(f"Unsupported duplicate_policy: {duplicate_policy!r}")

    normalized_statuses: set[str] | None = None
    if allowed_statuses is not None:
        normalized_statuses = {status.upper() for status in allowed_statuses}

    mapping: dict[str, tuple[str, str]] = {}
    issues: list[str] = []
    for row in rows:
        if normalized_statuses is not None and row.status not in normalized_statuses:
            continue

        existing = mapping.get(row.run_path)
        next_value = (row.controller_path, row.status)
        if existing is None:
            mapping[row.run_path] = next_value
            continue

        if existing == next_value:
            issues.append(
                "duplicate mapping with identical value for "
                f"{row.run_path} at row {row.row_number}"
            )
            continue

        if duplicate_policy == "last":
            issues.append(
                "duplicate run mapping for "
                f"{row.run_path}; overriding {existing} with {next_value} "
                f"(row {row.row_number})"
            )
            mapping[row.run_path] = next_value
        elif duplicate_policy == "first":
            issues.append(
                "duplicate run mapping for "
                f"{row.run_path}; keeping first value {existing} "
                f"and skipping row {row.row_number}"
            )
        else:  # duplicate_policy == "error"
            issues.append(
                "duplicate run mapping for "
                f"{row.run_path}; conflict between {existing} and "
                f"{next_value} (row {row.row_number})"
            )

    return mapping, issues


def read_best_controller_name(rlwp_dir: Path) -> tuple[str | None, str | None]:
    """Read best.txt under a rlwp directory and return controller_N.py."""
    best_path = rlwp_dir / "best.txt"
    if not best_path.exists():
        return None, f"missing file {best_path}"

    try:
        text = best_path.read_text(encoding="utf-8").strip()
    except Exception as exc:  # noqa: BLE001
        return None, f"failed to read {best_path} ({exc})"

    if BEST_CONTROLLER_PATTERN.fullmatch(text) is None:
        return None, f"malformed best.txt at {best_path}: expected controller_N.py"
    return text, None


def parse_sim_run_path(run_path: str) -> tuple[str, str, int, int] | None:
    """Parse sim/<setup>/<experiment>/attemptN/runM.npy relative run path."""
    match = SIM_RUN_RELATIVE_PATTERN.fullmatch(run_path)
    if match is None:
        return None
    setup_name, experiment_id, attempt_n, run_index = match.groups()
    return setup_name, experiment_id, int(attempt_n), int(run_index)


def classify_why_phase(why_text: str) -> str | None:
    """Classify an llm_said why string as design/tuning phase."""
    normalized = why_text.strip().lower()
    if normalized.startswith(DESIGN_WHY_PREFIX):
        return "design"
    if normalized.startswith(TUNING_WHY_PREFIX):
        return "tuning"
    return None


def resolve_last_design_before_tuning_run_paths(
    run_why_by_path: Mapping[str, str],
) -> tuple[set[str], list[str]]:
    """Return run paths for the last design run before first tuning per attempt."""
    grouped_by_attempt: dict[tuple[str, str, int], list[tuple[int, str, str]]] = {}
    issues: list[str] = []

    for run_path, why_text in sorted(run_why_by_path.items()):
        parsed = parse_sim_run_path(run_path)
        if parsed is None:
            issues.append(f"skipped run with unexpected sim path format: {run_path}")
            continue
        setup_name, experiment_id, attempt_n, run_index = parsed

        if not isinstance(why_text, str):
            issues.append(
                f"skipped run with non-string why value: {run_path} ({type(why_text).__name__})"
            )
            continue
        phase = classify_why_phase(why_text)
        if phase is None:
            issues.append(
                f"skipped run with unrecognized why prefix: {run_path} "
                f"({why_text.strip()!r})"
            )
            continue

        attempt_key = (setup_name, experiment_id, attempt_n)
        grouped_by_attempt.setdefault(attempt_key, []).append((run_index, run_path, phase))

    selected: set[str] = set()
    for attempt_key in sorted(grouped_by_attempt):
        run_rows = sorted(grouped_by_attempt[attempt_key], key=lambda row: row[0])
        first_tuning_index: int | None = None
        for run_index, _run_path, phase in run_rows:
            if phase == "tuning":
                first_tuning_index = run_index
                break
        if first_tuning_index is None:
            continue

        design_before_tuning = [
            (run_index, run_path)
            for run_index, run_path, phase in run_rows
            if phase == "design" and run_index < first_tuning_index
        ]
        if not design_before_tuning:
            setup_name, experiment_id, attempt_n = attempt_key
            issues.append(
                "no design run found before first tuning for "
                f"{setup_name}/{experiment_id}/attempt{attempt_n}"
            )
            continue

        design_before_tuning.sort(key=lambda row: row[0])
        _run_index, chosen_run_path = design_before_tuning[-1]
        selected.add(chosen_run_path)

    return selected, issues
