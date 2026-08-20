#!/usr/bin/env python3
"""Dash app for visualizing saved simulation step responses.

Expected on-disk format per run:
results/current_run/sim/<setup>/<experiment_id>/attempt<attempt_N>/run<run_N>.npy
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import quote

import numpy as np
import plotly.graph_objects as go
from controlserver.config import get_setup_signal_metadata
from dash import Dash, Input, Output, State, ctx, dcc, html, no_update
from dashes.lib_query_runs import (
    build_controller_lookup,
    build_run_lookup,
    load_match_csv_rows,
    parse_sim_run_path,
    read_best_controller_name,
    resolve_last_design_before_tuning_run_paths,
)
from dashes.parse_kpis import compute_objective, format_objective
from flask import Response, abort, request
from plotly.colors import qualitative
from plotly.subplots import make_subplots

RUN_FILE_PATTERN = re.compile(r"run(\d+)\.npy$")
ATTEMPT_DIR_PATTERN = re.compile(r"attempt(\d+)$")
REQUIRED_KEYS = ("time_sec", "ref", "meas", "control", "kpis", "llm_said")
REQUIRED_LLM_SAID_KEYS = ("setup", "description", "why")
KPI_HOVER_KEYS = (
    "overshoot_pct",
    "rise_time_sec",
    "settling_time_sec",
    "steady_state_error_pct",
    "max_abs_rad",
    "settled_within_horizon",
    "simulation_horizon_sec",
)
TRACE_COLORS = (
    qualitative.Plotly
    + qualitative.D3
    + qualitative.G10
    + qualitative.Safe
    + qualitative.Set2
)
AXIS_COLORS = qualitative.Dark24 + qualitative.Bold + qualitative.Safe + qualitative.Set2
SCALAR_CHANNEL = "__scalar__"
PREFERRED_CHANNEL_ORDER = ("x_cart", "phi_angle")
DEFAULT_SIGNAL_SPECS = {
    "ref": {"display_name": "Reference", "unit": ""},
    "meas": {"display_name": "Measured Output", "unit": ""},
    "control": {"display_name": "Control Input", "unit": ""},
}
MATCHABLE_NPY_STATUSES = frozenset({"PASS", "WARN"})
BEST_HOVER_SUFFIX = " (🏆 best)"
DAGGER_HOVER_SUFFIX = " (⛳ design checkpoint)"
CONTROLLER_VIEW_ROUTE = "/view-controller"


@dataclass(frozen=True)
class RunRecord:
    setup_name: str
    experiment_id: str
    attempt_n: int
    run_index: int
    time_sec: np.ndarray
    ref: np.ndarray | dict[str, np.ndarray]
    meas: np.ndarray | dict[str, np.ndarray]
    control: np.ndarray
    kpis: dict[str, Any]
    llm_said: dict[str, str]
    file_path: Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="View saved step responses from runN.npy files with Dash."
    )
    parser.add_argument(
        "--folder",
        type=Path,
        default=Path("results/current_run/sim"),
        help="Folder that contains setup/experiment/attemptN/runN.npy files.",
    )
    parser.add_argument(
        "--host",
        type=str,
        default="127.0.0.1",
        help="Host interface for the Dash server.",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8201,
        help="Dash server port.",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable Dash debug mode.",
    )
    return parser.parse_args()


def _coerce_1d_float_array(
    value: Any,
    key: str,
    file_path: Path,
    warnings: list[str],
) -> np.ndarray | None:
    arr = np.asarray(value)
    if arr.ndim != 1:
        warnings.append(
            f"Skipped {file_path}: key '{key}' is not 1D (shape={arr.shape})."
        )
        return None

    try:
        return arr.astype(float)
    except (TypeError, ValueError):
        warnings.append(
            f"Skipped {file_path}: key '{key}' is not numeric (dtype={arr.dtype})."
        )
        return None


def _coerce_signal_trace(
    value: Any,
    key: str,
    file_path: Path,
    warnings: list[str],
) -> np.ndarray | dict[str, np.ndarray] | None:
    if isinstance(value, Mapping):
        if not value:
            warnings.append(f"Skipped {file_path}: key '{key}' map is empty.")
            return None

        channels: dict[str, np.ndarray] = {}
        expected_len: int | None = None
        for channel_name in sorted(value):
            if not isinstance(channel_name, str):
                warnings.append(
                    f"Skipped {file_path}: key '{key}' channel names must be strings."
                )
                return None
            stripped = channel_name.strip()
            if not stripped:
                warnings.append(
                    f"Skipped {file_path}: key '{key}' channel names must be non-empty."
                )
                return None

            arr = _coerce_1d_float_array(
                value[channel_name],
                f"{key}.{stripped}",
                file_path,
                warnings,
            )
            if arr is None:
                return None

            if expected_len is None:
                expected_len = len(arr)
            elif len(arr) != expected_len:
                warnings.append(
                    f"Skipped {file_path}: key '{key}' channel lengths do not match "
                    f"(expected={expected_len}, got={len(arr)} for '{stripped}')."
                )
                return None
            channels[stripped] = arr

        return channels

    return _coerce_1d_float_array(value, key, file_path, warnings)


def _trace_length(trace: np.ndarray | dict[str, np.ndarray]) -> int:
    if isinstance(trace, dict):
        first_key = next(iter(trace))
        return int(len(trace[first_key]))
    return int(len(trace))


def _trace_channels(
    ref: np.ndarray | dict[str, np.ndarray],
    meas: np.ndarray | dict[str, np.ndarray],
) -> list[str]:
    if isinstance(ref, dict) and isinstance(meas, dict):
        return sorted(set(ref) & set(meas))
    if isinstance(meas, dict):
        return sorted(meas)
    if isinstance(ref, dict):
        return sorted(ref)
    return [SCALAR_CHANNEL]


def _ordered_channels(channels: set[str]) -> list[str]:
    ordered: list[str] = []

    if SCALAR_CHANNEL in channels:
        ordered.append(SCALAR_CHANNEL)

    for preferred in PREFERRED_CHANNEL_ORDER:
        if preferred in channels and preferred not in ordered:
            ordered.append(preferred)

    ordered.extend(sorted(channel for channel in channels if channel not in ordered))
    return ordered


def _channel_suffix(channel: str) -> str:
    if channel == SCALAR_CHANNEL:
        return ""
    return f" [{channel}]"


def _extract_plot_trace(
    trace: np.ndarray | dict[str, np.ndarray],
    channel: str,
) -> np.ndarray:
    if isinstance(trace, dict):
        if channel not in trace:
            raise ValueError(
                f"Missing plot channel '{channel}' in dict-valued trace."
            )
        return trace[channel]
    if channel != SCALAR_CHANNEL:
        raise ValueError(
            f"Plot channel '{channel}' is unavailable for scalar-valued trace."
        )
    return trace


def _coerce_llm_said(
    value: Any,
    file_path: Path,
    warnings: list[str],
) -> dict[str, str] | None:
    if not isinstance(value, dict):
        warnings.append(f"Skipped {file_path}: key 'llm_said' is not a dict.")
        return None

    llm_said: dict[str, str] = {}
    for key in REQUIRED_LLM_SAID_KEYS:
        field_value = value.get(key)
        if not isinstance(field_value, str):
            warnings.append(
                f"Skipped {file_path}: llm_said['{key}'] must be a string."
            )
            return None
        stripped = field_value.strip()
        if not stripped:
            warnings.append(
                f"Skipped {file_path}: llm_said['{key}'] must be non-empty."
            )
            return None
        llm_said[key] = stripped
    return llm_said


def _load_one_run(
    file_path: Path,
    setup_name: str,
    experiment_id: str,
    attempt_n: int,
    run_index: int,
    warnings: list[str],
) -> RunRecord | None:
    try:
        loaded = np.load(file_path, allow_pickle=True)
    except Exception as exc:  # noqa: BLE001
        warnings.append(f"Skipped {file_path}: load failed ({exc}).")
        return None

    payload: Any = loaded
    if isinstance(loaded, np.ndarray) and loaded.shape == ():
        try:
            payload = loaded.item()
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"Skipped {file_path}: could not extract scalar payload ({exc}).")
            return None

    if not isinstance(payload, dict):
        warnings.append(f"Skipped {file_path}: payload is not a dict.")
        return None

    missing = [k for k in REQUIRED_KEYS if k not in payload]
    if missing:
        warnings.append(f"Skipped {file_path}: missing keys {missing}.")
        return None

    time_sec = _coerce_1d_float_array(payload["time_sec"], "time_sec", file_path, warnings)
    ref = _coerce_signal_trace(payload["ref"], "ref", file_path, warnings)
    meas = _coerce_signal_trace(payload["meas"], "meas", file_path, warnings)
    control = _coerce_1d_float_array(payload["control"], "control", file_path, warnings)
    if any(x is None for x in (time_sec, ref, meas, control)):
        return None

    if isinstance(ref, dict) and isinstance(meas, dict):
        if set(ref) != set(meas):
            warnings.append(
                f"Skipped {file_path}: ref/meas channels do not match "
                f"(ref={sorted(ref)}, meas={sorted(meas)})."
            )
            return None

    lengths = {
        len(time_sec),
        _trace_length(ref),
        _trace_length(meas),
        len(control),
    }
    if len(lengths) != 1:
        warnings.append(
            f"Skipped {file_path}: trace lengths do not match "
            f"(time={len(time_sec)}, ref={_trace_length(ref)}, "
            f"meas={_trace_length(meas)}, control={len(control)})."
        )
        return None

    kpis = payload["kpis"]
    if not isinstance(kpis, dict):
        warnings.append(f"Warning {file_path}: key 'kpis' is not a dict; using empty KPI set.")
        kpis = {}

    llm_said = _coerce_llm_said(payload["llm_said"], file_path=file_path, warnings=warnings)
    if llm_said is None:
        return None

    setup_from_payload = payload.get("setup")
    if isinstance(setup_from_payload, str) and setup_from_payload:
        setup_name = setup_from_payload
    if llm_said["setup"] != setup_name:
        warnings.append(
            f"Skipped {file_path}: llm_said.setup='{llm_said['setup']}' does not match "
            f"setup='{setup_name}'."
        )
        return None

    return RunRecord(
        setup_name=setup_name,
        experiment_id=experiment_id,
        attempt_n=attempt_n,
        run_index=run_index,
        time_sec=time_sec,
        ref=ref,
        meas=meas,
        control=control,
        kpis=kpis,
        llm_said=llm_said,
        file_path=file_path,
    )


def load_runs(folder: Path) -> tuple[list[RunRecord], list[str], list[str], list[int], list[str]]:
    warnings: list[str] = []
    records: list[RunRecord] = []

    if not folder.exists():
        return records, [], [], [], [f"Folder does not exist: {folder}"]
    if not folder.is_dir():
        return records, [], [], [], [f"Path is not a directory: {folder}"]

    setup_dirs = sorted(p for p in folder.iterdir() if p.is_dir())
    for setup_dir in setup_dirs:
        setup_name = setup_dir.name
        experiment_dirs = sorted(p for p in setup_dir.iterdir() if p.is_dir())
        for experiment_dir in experiment_dirs:
            experiment_id = experiment_dir.name
            attempt_dirs = sorted(p for p in experiment_dir.iterdir() if p.is_dir())
            for attempt_dir in attempt_dirs:
                attempt_match = ATTEMPT_DIR_PATTERN.fullmatch(attempt_dir.name)
                if attempt_match is None:
                    continue
                attempt_n = int(attempt_match.group(1))
                run_files = sorted(p for p in attempt_dir.iterdir() if p.is_file())
                for file_path in run_files:
                    run_match = RUN_FILE_PATTERN.fullmatch(file_path.name)
                    if run_match is None:
                        continue
                    run_index = int(run_match.group(1))
                    record = _load_one_run(
                        file_path=file_path,
                        setup_name=setup_name,
                        experiment_id=experiment_id,
                        attempt_n=attempt_n,
                        run_index=run_index,
                        warnings=warnings,
                    )
                    if record is not None:
                        records.append(record)

    records.sort(
        key=lambda rec: (
            rec.setup_name,
            rec.experiment_id,
            rec.attempt_n,
            rec.run_index,
        )
    )

    all_setups = sorted({rec.setup_name for rec in records})
    all_experiment_ids = sorted({rec.experiment_id for rec in records})
    all_attempts = sorted({rec.attempt_n for rec in records})

    if not records:
        warnings.append(
            "No valid runN.npy files found under setup/experiment/attemptN directories."
        )

    return records, all_setups, all_experiment_ids, all_attempts, warnings


def _kpi_text(kpis: Mapping[str, Any], key: str) -> str:
    if key not in kpis:
        return "n/a"

    value = kpis[key]
    if isinstance(value, (bool, np.bool_)):
        return str(bool(value))

    if isinstance(value, (int, float, np.integer, np.floating)):
        value_float = float(value)
        if np.isfinite(value_float):
            return f"{value_float:.6g}"
        return "n/a"

    return str(value)


def _kpis_for_channel(kpis: Mapping[str, Any], channel: str) -> Mapping[str, Any]:
    channel_bundles = kpis.get("channels")
    if not isinstance(channel_bundles, Mapping):
        return kpis

    if channel != SCALAR_CHANNEL:
        selected = channel_bundles.get(channel)
        if isinstance(selected, Mapping):
            return selected

    preferred = channel_bundles.get("x_cart")
    if isinstance(preferred, Mapping):
        return preferred

    for candidate in channel_bundles.values():
        if isinstance(candidate, Mapping):
            return candidate

    return {}


def _build_customdata(
    record: RunRecord,
    channel: str,
    is_best: bool = False,
    is_design_checkpoint: bool = False,
) -> np.ndarray:
    point_count = len(record.time_sec)
    kpi_values = _kpis_for_channel(record.kpis, channel)
    columns: list[np.ndarray] = [
        np.full(point_count, record.setup_name, dtype=object),
        np.full(point_count, record.experiment_id, dtype=object),
        np.full(point_count, f"attempt{record.attempt_n}", dtype=object),
        np.full(point_count, f"run{record.run_index}", dtype=object),
    ]
    for key in KPI_HOVER_KEYS:
        columns.append(np.full(point_count, _kpi_text(kpi_values, key), dtype=object))
    columns.append(
        np.full(
            point_count,
            _hover_marker_suffix(
                is_best=is_best,
                is_design_checkpoint=is_design_checkpoint,
            ),
            dtype=object,
        )
    )
    return np.column_stack(columns)


def _hover_template(signal_label: str) -> str:
    best_col_index = 4 + len(KPI_HOVER_KEYS)
    lines = [
        (
            "<b>%{customdata[0]}/%{customdata[1]}/%{customdata[2]}/%{customdata[3]}"
            f"%{{customdata[{best_col_index}]}}</b>"
        ),
        "time_sec=%{x:.6f}",
        f"{signal_label}=%{{y:.6g}}",
    ]
    for offset, key in enumerate(KPI_HOVER_KEYS, start=4):
        lines.append(f"{key}=%{{customdata[{offset}]}}")
    return "<br>".join(lines) + "<extra></extra>"


def _empty_figure(message: str) -> go.Figure:
    fig = go.Figure()
    fig.add_annotation(
        x=0.5,
        y=0.5,
        xref="paper",
        yref="paper",
        text=message,
        showarrow=False,
    )
    fig.update_xaxes(visible=False)
    fig.update_yaxes(visible=False)
    fig.update_layout(
        template="plotly_white",
        autosize=True,
        margin=dict(l=30, r=20, t=50, b=40),
    )
    return fig


def _format_signal_label(display_name: str, unit: str) -> str:
    if unit:
        return f"{display_name} ({unit})"
    return display_name


def _signal_label(setup_name: str, key: str) -> str:
    fallback = DEFAULT_SIGNAL_SPECS[key]
    try:
        spec = get_setup_signal_metadata(setup_name).get(key, fallback)
    except Exception:
        spec = fallback

    display_name = str(spec.get("display_name", fallback["display_name"]))
    unit = str(spec.get("unit", fallback["unit"]))
    return _format_signal_label(display_name, unit)


def _common_signal_label(records: list[RunRecord], key: str) -> str:
    labels = sorted({_signal_label(record.setup_name, key) for record in records})
    if len(labels) == 1:
        return labels[0]
    fallback = DEFAULT_SIGNAL_SPECS[key]
    return _format_signal_label(fallback["display_name"], fallback["unit"])


def _legend_group_key(record: RunRecord) -> str:
    return f"{record.setup_name}/{record.experiment_id}/attempt{record.attempt_n}/run{record.run_index}"


def _legend_group_from_run_path(run_path: str) -> str | None:
    parsed = parse_sim_run_path(run_path)
    if parsed is None:
        return None
    setup_name, experiment_id, attempt_n, run_index = parsed
    return f"{setup_name}/{experiment_id}/attempt{attempt_n}/run{run_index}"


def _append_run_markers(
    label: str,
    is_best: bool,
    is_design_checkpoint: bool,
) -> str:
    suffix = ""
    if is_best:
        suffix += "*"
    if is_design_checkpoint:
        suffix += "†"
    return f"{label}{suffix}"


def _hover_marker_suffix(
    is_best: bool,
    is_design_checkpoint: bool,
) -> str:
    suffix = ""
    if is_best:
        suffix += BEST_HOVER_SUFFIX
    if is_design_checkpoint:
        suffix += DAGGER_HOVER_SUFFIX
    return suffix


def _load_pass_warn_lookups(
    current_run_folder: Path,
) -> tuple[dict[str, tuple[str, str]], dict[str, tuple[str, str]], list[str]]:
    warnings: list[str] = []
    match_rows, row_issues = load_match_csv_rows(current_run_folder)
    if not match_rows:
        warnings.extend(f"best-run mapping unavailable: {issue}." for issue in row_issues)
        return {}, {}, warnings

    warnings.extend(f"best-run mapping warning: {issue}." for issue in row_issues)
    controller_to_run, controller_issues = build_controller_lookup(
        match_rows,
        allowed_statuses=set(MATCHABLE_NPY_STATUSES),
        duplicate_policy="last",
    )
    run_to_controller, run_issues = build_run_lookup(
        match_rows,
        allowed_statuses=set(MATCHABLE_NPY_STATUSES),
        duplicate_policy="last",
    )
    warnings.extend(f"best-run mapping warning: {issue}." for issue in controller_issues)
    warnings.extend(f"best-run mapping warning: {issue}." for issue in run_issues)
    return controller_to_run, run_to_controller, warnings


def _resolve_controller_targets(
    current_run_folder: Path,
    run_to_controller: Mapping[str, tuple[str, str]],
) -> tuple[dict[str, Path], dict[str, str], list[str]]:
    warnings: list[str] = []
    controller_paths_by_legend: dict[str, Path] = {}
    controller_names_by_legend: dict[str, str] = {}

    for run_path, (controller_path, _status) in run_to_controller.items():
        legend_group = _legend_group_from_run_path(run_path)
        if legend_group is None:
            warnings.append(
                f"Skipped mapped run with unexpected path format in npy_match.csv: {run_path}."
            )
            continue
        controller_paths_by_legend[legend_group] = current_run_folder.joinpath(
            Path(controller_path)
        )
        controller_names_by_legend[legend_group] = Path(controller_path).name

    return controller_paths_by_legend, controller_names_by_legend, warnings


def _resolve_best_legend_groups(
    current_run_folder: Path,
    controller_to_run: Mapping[str, tuple[str, str]] | None = None,
) -> tuple[set[str], list[str]]:
    warnings: list[str] = []
    if current_run_folder.name == "sim":
        current_run_folder = current_run_folder.parent
    if controller_to_run is None:
        controller_to_run, _run_to_controller, lookup_warnings = _load_pass_warn_lookups(
            current_run_folder
        )
        warnings.extend(lookup_warnings)

    wp_folder = current_run_folder / "wp"

    if not wp_folder.is_dir():
        warnings.append(f"best-run mapping unavailable: missing folder {wp_folder}.")
        return set(), warnings

    best_legend_groups: set[str] = set()
    for best_path in sorted(wp_folder.rglob("best.txt")):
        best_text, best_issue = read_best_controller_name(best_path.parent)
        if best_text is None:
            if best_issue is None:
                warnings.append(f"Skipped malformed best.txt at {best_path}.")
            else:
                warnings.append(f"Skipped {best_issue}.")
            continue

        controller_rel = best_path.parent.relative_to(current_run_folder).joinpath(
            best_text
        )
        controller_rel_posix = controller_rel.as_posix()
        mapped = controller_to_run.get(controller_rel_posix)
        if mapped is None:
            warnings.append(
                "Skipped best-controller mapping without PASS/WARN row: "
                f"{controller_rel_posix}."
            )
            continue
        mapped_run, _mapped_status = mapped

        legend_group = _legend_group_from_run_path(mapped_run)
        if legend_group is None:
            warnings.append(
                f"Skipped mapped run with unexpected path format in npy_match.csv: {mapped_run}."
            )
            continue

        best_legend_groups.add(legend_group)

    return best_legend_groups, warnings


def _run_path_for_record(record: RunRecord) -> str:
    return (
        f"sim/{record.setup_name}/{record.experiment_id}/"
        f"attempt{record.attempt_n}/run{record.run_index}.npy"
    )


def _resolve_dagger_legend_groups(records: list[RunRecord]) -> tuple[set[str], list[str]]:
    run_why_by_path = {
        _run_path_for_record(record): record.llm_said["why"]
        for record in records
    }
    dagger_run_paths, issues = resolve_last_design_before_tuning_run_paths(run_why_by_path)
    warnings = [f"design-checkpoint mapping warning: {issue}." for issue in issues]

    dagger_legend_groups: set[str] = set()
    for run_path in sorted(dagger_run_paths):
        legend_group = _legend_group_from_run_path(run_path)
        if legend_group is None:
            warnings.append(
                "design-checkpoint mapping warning: "
                f"skipped mapped run with unexpected path format: {run_path}."
            )
            continue
        dagger_legend_groups.add(legend_group)

    return dagger_legend_groups, warnings


def _normalize_hidden_groups(hidden_groups: Any) -> set[str]:
    if isinstance(hidden_groups, list):
        return {str(item) for item in hidden_groups if isinstance(item, str)}
    return set()


def _extract_visibility_value(values: Any, offset: int) -> Any:
    if isinstance(values, list):
        if 0 <= offset < len(values):
            return values[offset]
        return None
    return values


def _update_hidden_groups_from_restyle(
    hidden_groups: set[str],
    restyle_data: Any,
    figure: dict[str, Any] | None,
) -> set[str]:
    updated = set(hidden_groups)
    if not isinstance(restyle_data, list) or len(restyle_data) != 2:
        return updated
    if not isinstance(figure, dict):
        return updated
    data = figure.get("data")
    if not isinstance(data, list):
        return updated

    edits, trace_indexes = restyle_data
    if not isinstance(edits, dict):
        return updated
    if not isinstance(trace_indexes, list):
        return updated

    for offset, trace_index in enumerate(trace_indexes):
        if not isinstance(trace_index, int):
            continue
        if trace_index < 0 or trace_index >= len(data):
            continue

        trace = data[trace_index]
        if not isinstance(trace, dict):
            continue
        legend_group = trace.get("legendgroup")
        if not isinstance(legend_group, str) or not legend_group:
            continue

        visible_value = _extract_visibility_value(edits.get("visible"), offset)
        if visible_value in ("legendonly", False):
            updated.add(legend_group)
        elif visible_value in (True, None):
            updated.discard(legend_group)

    return updated


def _legend_groups_in_figure(figure: dict[str, Any] | None) -> set[str]:
    if not isinstance(figure, dict):
        return set()
    data = figure.get("data")
    if not isinstance(data, list):
        return set()
    groups: set[str] = set()
    for trace in data:
        if not isinstance(trace, dict):
            continue
        legend_group = trace.get("legendgroup")
        if isinstance(legend_group, str) and legend_group:
            groups.add(legend_group)
    return groups


def _llm_said_table(
    records: list[RunRecord],
    hidden_groups: set[str],
    best_legend_groups: set[str] | None = None,
    dagger_legend_groups: set[str] | None = None,
    controller_names_by_legend: Mapping[str, str] | None = None,
) -> Any:
    best_legend_groups = best_legend_groups or set()
    dagger_legend_groups = dagger_legend_groups or set()
    controller_names_by_legend = controller_names_by_legend or {}
    visible_records = [r for r in records if _legend_group_key(r) not in hidden_groups]
    if not visible_records:
        return html.Div(
            "No visible runs for llm_said metadata.",
            style={"padding": "10px 12px", "fontSize": "13px", "color": "#475569"},
        )

    def objective_text(rec: RunRecord) -> str:
        try:
            value = compute_objective(rec.setup_name, rec.kpis)
        except (TypeError, ValueError):
            return "n/a"
        return format_objective(value)

    visible_records.sort(
        key=lambda rec: (
            rec.setup_name,
            rec.experiment_id,
            rec.attempt_n,
            rec.run_index,
        )
    )
    header_cells = [
        html.Th("Legend", style={"textAlign": "left", "padding": "6px 8px"}),
        html.Th("Controller", style={"textAlign": "left", "padding": "6px 8px"}),
        html.Th("Setup", style={"textAlign": "left", "padding": "6px 8px"}),
        html.Th("Objective", style={"textAlign": "left", "padding": "6px 8px"}),
        html.Th("Description", style={"textAlign": "left", "padding": "6px 8px"}),
        html.Th("Why", style={"textAlign": "left", "padding": "6px 8px"}),
    ]
    body_rows = []
    for rec in visible_records:
        legend_group = _legend_group_key(rec)
        legend = _append_run_markers(
            label=legend_group,
            is_best=legend_group in best_legend_groups,
            is_design_checkpoint=legend_group in dagger_legend_groups,
        )
        controller_name = controller_names_by_legend.get(legend_group)
        if controller_name is None:
            controller_cell = html.Span("n/a", style={"color": "#64748b"})
        else:
            legend_query = quote(legend_group, safe="")
            controller_cell = html.A(
                controller_name,
                href=f"{CONTROLLER_VIEW_ROUTE}?legend={legend_query}",
                target="_blank",
                rel="noopener noreferrer",
            )
        body_rows.append(
            html.Tr(
                [
                    html.Td(legend, style={"padding": "6px 8px", "verticalAlign": "top"}),
                    html.Td(controller_cell, style={"padding": "6px 8px", "verticalAlign": "top"}),
                    html.Td(rec.llm_said["setup"], style={"padding": "6px 8px", "verticalAlign": "top"}),
                    html.Td(objective_text(rec), style={"padding": "6px 8px", "verticalAlign": "top"}),
                    html.Td(
                        rec.llm_said["description"],
                        style={"padding": "6px 8px", "verticalAlign": "top"},
                    ),
                    html.Td(rec.llm_said["why"], style={"padding": "6px 8px", "verticalAlign": "top"}),
                ]
            )
        )

    return html.Table(
        [html.Thead(html.Tr(header_cells)), html.Tbody(body_rows)],
        style={
            "width": "100%",
            "borderCollapse": "collapse",
            "fontSize": "13px",
        },
    )


def _style_lookup(
    records: list[RunRecord],
    use_rainbow_colors: bool = False,
    rainbow_group_order: list[str] | None = None,
) -> dict[str, tuple[str, float]]:
    style: dict[str, tuple[str, float]] = {}
    if not records:
        return style

    unique_groups = sorted({_legend_group_key(rec) for rec in records})
    if use_rainbow_colors and rainbow_group_order:
        available = set(unique_groups)
        ordered = [group for group in rainbow_group_order if group in available]
        ordered_set = set(ordered)
        ordered.extend(group for group in unique_groups if group not in ordered_set)
        unique_groups = ordered

    opacity = 1.0 if len(unique_groups) <= 1 else 0.7
    rainbow_anchor_rgb = np.array(
        [
            [255.0, 0.0, 0.0],    # red
            [255.0, 255.0, 0.0],  # yellow
            [0.0, 0.0, 255.0],    # blue
        ],
        dtype=float,
    )

    if use_rainbow_colors:
        if len(unique_groups) <= 1:
            colors = ["#ff0000"]
        else:
            palette: list[str] = []
            steps = np.linspace(0.0, float(len(rainbow_anchor_rgb) - 1), num=len(unique_groups))
            for step in steps:
                lo = int(np.floor(step))
                hi = min(lo + 1, len(rainbow_anchor_rgb) - 1)
                frac = step - lo
                rgb = (1.0 - frac) * rainbow_anchor_rgb[lo] + frac * rainbow_anchor_rgb[hi]
                r, g, b = [int(round(x)) for x in rgb]
                palette.append(f"#{r:02x}{g:02x}{b:02x}")
            colors = palette
    else:
        colors = [TRACE_COLORS[idx % len(TRACE_COLORS)] for idx in range(len(unique_groups))]

    for idx, legend_group in enumerate(unique_groups):
        style[legend_group] = (colors[idx], opacity)

    return style


def build_figure(
    all_runs: list[RunRecord],
    selected_setups: list[str],
    selected_experiment_ids: list[str],
    selected_attempts: list[int],
    show_reference: bool,
    show_control: bool,
    normalize_response: bool,
    use_rainbow_colors: bool = False,
    short_legend: bool = False,
    show_best_only: bool = False,
    show_design_checkpoint_only: bool = False,
    hidden_groups: set[str] | None = None,
    best_legend_groups: set[str] | None = None,
    dagger_legend_groups: set[str] | None = None,
) -> tuple[go.Figure, int, list[RunRecord]]:
    hidden_groups = hidden_groups or set()
    best_legend_groups = best_legend_groups or set()
    dagger_legend_groups = dagger_legend_groups or set()
    selected_setup_set = set(selected_setups)
    selected_experiment_set = set(selected_experiment_ids)
    selected_attempt_set = set(selected_attempts)

    filtered = [
        rec
        for rec in all_runs
        if rec.setup_name in selected_setup_set
        and rec.experiment_id in selected_experiment_set
        and rec.attempt_n in selected_attempt_set
    ]
    marker_filter_groups: set[str] = set()
    if show_best_only:
        marker_filter_groups.update(best_legend_groups)
    if show_design_checkpoint_only:
        marker_filter_groups.update(dagger_legend_groups)
    if marker_filter_groups:
        filtered = [
            rec for rec in filtered if _legend_group_key(rec) in marker_filter_groups
        ]
    filtered.sort(
        key=lambda rec: (
            rec.setup_name,
            rec.experiment_id,
            rec.attempt_n,
            rec.run_index,
        )
    )

    if not filtered:
        return _empty_figure("No runs to show for the current selection."), 0, []

    if show_control:
        fig = make_subplots(
            rows=2,
            cols=1,
            shared_xaxes=True,
            vertical_spacing=0.08,
            row_heights=[0.72, 0.28],
            subplot_titles=("Step Response", "Control Signal"),
        )
    else:
        fig = make_subplots(rows=1, cols=1)

    response_channels = _ordered_channels(
        {
            channel
            for rec in filtered
            for channel in _trace_channels(rec.ref, rec.meas)
        }
    )
    legend_order_for_iteration = sorted(
        filtered,
        key=lambda rec: (
            rec.run_index,
            rec.setup_name,
            rec.experiment_id,
            rec.attempt_n,
        ),
    )
    ordered_legend_groups: list[str] = []
    seen_legend_groups: set[str] = set()
    for rec in legend_order_for_iteration:
        legend_group = _legend_group_key(rec)
        if legend_group in seen_legend_groups:
            continue
        seen_legend_groups.add(legend_group)
        ordered_legend_groups.append(legend_group)

    legend_name_lookup: dict[str, str] = {}
    if short_legend:
        legend_name_lookup = {
            legend_group: f"Iteration {idx + 1}"
            for idx, legend_group in enumerate(ordered_legend_groups)
        }

    styles = _style_lookup(
        filtered,
        use_rainbow_colors=use_rainbow_colors,
        rainbow_group_order=ordered_legend_groups if use_rainbow_colors else None,
    )
    plot_records = (
        legend_order_for_iteration
        if (use_rainbow_colors or short_legend)
        else filtered
    )
    meas_label = _common_signal_label(filtered, "meas")
    ref_label = _common_signal_label(filtered, "ref")
    control_label = _common_signal_label(filtered, "control")
    meas_hover = {
        channel: _hover_template(meas_label + _channel_suffix(channel))
        for channel in response_channels
    }
    ref_hover = {
        channel: _hover_template(ref_label + _channel_suffix(channel))
        for channel in response_channels
    }
    control_hover = _hover_template(control_label)
    response_axis_for_channel: dict[str, str] = {}
    axis_layout_updates: dict[str, dict[str, Any]] = {}
    left_axis_count = 1
    right_axis_count = 0
    extra_left_rank = 1
    extra_right_rank = 0

    for channel_index, channel in enumerate(response_channels):
        axis_color = AXIS_COLORS[channel_index % len(AXIS_COLORS)]
        axis_title_base = meas_label + _channel_suffix(channel)
        axis_title = (
            f"{axis_title_base} (normalized)"
            if normalize_response
            else axis_title_base
        )
        if channel_index == 0:
            axis_name = "y"
            layout_axis_name = "yaxis"
            axis_layout_updates[layout_axis_name] = dict(
                title=dict(text=axis_title, font=dict(color=axis_color)),
                tickfont=dict(color=axis_color),
                linecolor=axis_color,
                showline=True,
                zeroline=False,
                showgrid=True,
            )
        else:
            axis_number = channel_index + (2 if show_control else 1)
            axis_name = f"y{axis_number}"
            layout_axis_name = f"yaxis{axis_number}"
            is_left = channel_index % 2 == 0
            side = "left" if is_left else "right"
            if is_left:
                position = min(0.2, 0.045 * extra_left_rank)
                extra_left_rank += 1
                left_axis_count += 1
            else:
                position = max(0.8, 1.0 - 0.045 * extra_right_rank)
                extra_right_rank += 1
                right_axis_count += 1

            axis_layout_updates[layout_axis_name] = dict(
                title=dict(text=axis_title, font=dict(color=axis_color)),
                tickfont=dict(color=axis_color),
                linecolor=axis_color,
                showline=True,
                zeroline=False,
                showgrid=False,
                overlaying="y",
                side=side,
                anchor="free",
                position=position,
            )

        response_axis_for_channel[channel] = axis_name

    for rec in plot_records:
        legend_group = _legend_group_key(rec)
        is_best = legend_group in best_legend_groups
        is_design_checkpoint = legend_group in dagger_legend_groups
        legend_name = _append_run_markers(
            label=legend_name_lookup.get(legend_group, legend_group),
            is_best=is_best,
            is_design_checkpoint=is_design_checkpoint,
        )
        is_hidden = legend_group in hidden_groups
        rec_channels = _ordered_channels(set(_trace_channels(rec.ref, rec.meas)))
        control_customdata = _build_customdata(
            rec,
            rec_channels[0],
            is_best=is_best,
            is_design_checkpoint=is_design_checkpoint,
        )

        for channel_index, channel in enumerate(rec_channels):
            color, opacity = styles[legend_group]
            ref_trace = _extract_plot_trace(rec.ref, channel)
            meas_trace = _extract_plot_trace(rec.meas, channel)
            axis_name = response_axis_for_channel[channel]
            customdata = _build_customdata(
                rec,
                channel,
                is_best=is_best,
                is_design_checkpoint=is_design_checkpoint,
            )

            scale = 1.0
            if normalize_response:
                ref_abs_max = float(np.nanmax(np.abs(ref_trace)))
                if np.isfinite(ref_abs_max) and ref_abs_max > 0:
                    scale = ref_abs_max

            meas_y = meas_trace / scale
            ref_y = ref_trace / scale

            fig.add_trace(
                go.Scatter(
                    x=rec.time_sec,
                    y=meas_y,
                    mode="lines",
                    name=legend_name,
                    legendgroup=legend_group,
                    showlegend=channel_index == 0,
                    line=dict(color=color, width=2.0),
                    opacity=opacity,
                    customdata=customdata,
                    hovertemplate=meas_hover[channel],
                    visible="legendonly" if is_hidden else True,
                ),
                row=1,
                col=1,
            )
            fig.data[-1].update(yaxis=axis_name)

            if show_reference:
                fig.add_trace(
                    go.Scatter(
                        x=rec.time_sec,
                        y=ref_y,
                        mode="lines",
                        name=f"{legend_name} ref",
                        legendgroup=legend_group,
                        showlegend=False,
                        line=dict(color=color, width=1.5, dash="dash"),
                        opacity=min(1.0, opacity + 0.15),
                        customdata=customdata,
                        hovertemplate=ref_hover[channel],
                        visible=False if is_hidden else True,
                    ),
                    row=1,
                    col=1,
                )
                fig.data[-1].update(yaxis=axis_name)

        if show_control:
            control_color, control_opacity = styles[legend_group]
            fig.add_trace(
                go.Scatter(
                    x=rec.time_sec,
                    y=rec.control,
                    mode="lines",
                    name=f"{legend_name} u",
                    legendgroup=legend_group,
                    showlegend=False,
                    line=dict(color=control_color, width=1.5),
                    opacity=min(1.0, control_opacity + 0.15),
                    customdata=control_customdata,
                    hovertemplate=control_hover,
                    visible=False if is_hidden else True,
                ),
                row=2,
                col=1,
            )

    margin_left = 60 + max(0, left_axis_count - 1) * 58
    margin_right = 40 + max(0, right_axis_count - 1) * 58
    fig.update_layout(
        template="plotly_white",
        hovermode="closest",
        autosize=True,
        margin=dict(l=margin_left, r=margin_right, t=55, b=45),
        **axis_layout_updates,
    )
    if show_control:
        fig.update_yaxes(title_text=control_label, row=2, col=1)
        fig.update_xaxes(title_text="Time (s)", row=2, col=1)
    else:
        fig.update_xaxes(title_text="Time (s)", row=1, col=1)

    visible_filtered = [rec for rec in filtered if _legend_group_key(rec) not in hidden_groups]
    return fig, len(visible_filtered), filtered


def create_app(
    all_runs: list[RunRecord],
    all_setups: list[str],
    all_experiment_ids: list[str],
    all_attempts: list[int],
    warnings: list[str],
    best_legend_groups: set[str] | None = None,
    dagger_legend_groups: set[str] | None = None,
    current_run_folder: Path | None = None,
    controller_paths_by_legend: Mapping[str, Path] | None = None,
    controller_names_by_legend: Mapping[str, str] | None = None,
) -> Dash:
    best_legend_groups = best_legend_groups or set()
    dagger_legend_groups = dagger_legend_groups or set()
    controller_paths_by_legend = dict(controller_paths_by_legend or {})
    controller_names_by_legend = dict(controller_names_by_legend or {})
    app = Dash(__name__)
    allowed_controller_root = (
        (current_run_folder / "wp").resolve() if current_run_folder is not None else None
    )

    @app.server.route(CONTROLLER_VIEW_ROUTE, methods=["GET"])
    def view_controller_source() -> Response:
        legend_group = str(request.args.get("legend", "")).strip()
        if not legend_group:
            abort(400, "Missing legend query parameter.")

        controller_path = controller_paths_by_legend.get(legend_group)
        if controller_path is None:
            abort(404, f"No controller mapping found for {legend_group}.")

        resolved_path = controller_path.resolve()
        if allowed_controller_root is not None:
            try:
                resolved_path.relative_to(allowed_controller_root)
            except ValueError:
                abort(403, "Controller path is outside allowed root.")

        if not resolved_path.exists() or not resolved_path.is_file():
            abort(404, f"Controller file not found: {resolved_path}")

        try:
            source = resolved_path.read_text(encoding="utf-8")
        except Exception as exc:  # noqa: BLE001
            abort(500, f"Could not read controller file: {exc}")

        return Response(source, mimetype="text/plain; charset=utf-8")

    initial_options = ["show_reference", "best_only"]
    initial_hidden_groups: set[str] = set()
    initial_figure, initial_count, initial_filtered = build_figure(
        all_runs=all_runs,
        selected_setups=[],
        selected_experiment_ids=all_experiment_ids,
        selected_attempts=[],
        show_reference=True,
        show_control=False,
        normalize_response=False,
        use_rainbow_colors=False,
        short_legend=False,
        show_best_only=True,
        show_design_checkpoint_only=False,
        hidden_groups=initial_hidden_groups,
        best_legend_groups=best_legend_groups,
        dagger_legend_groups=dagger_legend_groups,
    )
    initial_table = _llm_said_table(
        initial_filtered,
        initial_hidden_groups,
        best_legend_groups=best_legend_groups,
        dagger_legend_groups=dagger_legend_groups,
        controller_names_by_legend=controller_names_by_legend,
    )

    option_labels = {
        "show_reference": "Show/hide dashed reference traces for each run.",
        "show_control": "Show/hide the control-signal subplot.",
        "normalize_response": "Normalize response traces by each run's max |reference|.",
        "rainbow_colors": (
            "Apply rainbow colors across selected runs from lower run index to higher run index."
        ),
        "short_legend": (
            "Use short legend labels as Iteration 1, Iteration 2, ... instead of full run paths."
        ),
        "best_only": "Show only best-marked runs (🏆/*).",
        "design_checkpoint_only": (
            "Show only last design run before first tuning run per attempt (⛳/†)."
        ),
    }
    checklist_options = [
        {
            "label": html.Abbr(
                "REF",
                title=option_labels["show_reference"],
                style={"textDecoration": "none", "cursor": "help", "fontWeight": "600"},
            ),
            "value": "show_reference",
        },
        {
            "label": html.Abbr(
                "U",
                title=option_labels["show_control"],
                style={"textDecoration": "none", "cursor": "help", "fontWeight": "600"},
            ),
            "value": "show_control",
        },
        {
            "label": html.Abbr(
                "NORM",
                title=option_labels["normalize_response"],
                style={"textDecoration": "none", "cursor": "help", "fontWeight": "600"},
            ),
            "value": "normalize_response",
        },
        {
            "label": html.Abbr(
                "🌈",
                title=option_labels["rainbow_colors"],
                style={"textDecoration": "none", "cursor": "help", "fontWeight": "600"},
            ),
            "value": "rainbow_colors",
        },
        {
            "label": html.Abbr(
                "🈹",
                title=option_labels["short_legend"],
                style={"textDecoration": "none", "cursor": "help", "fontWeight": "600"},
            ),
            "value": "short_legend",
        },
        {
            "label": html.Abbr(
                "🏆",
                title=option_labels["best_only"],
                style={"textDecoration": "none", "cursor": "help", "fontWeight": "600"},
            ),
            "value": "best_only",
        },
        {
            "label": html.Abbr(
                "⛳",
                title=option_labels["design_checkpoint_only"],
                style={"textDecoration": "none", "cursor": "help", "fontWeight": "600"},
            ),
            "value": "design_checkpoint_only",
        },
    ]

    app.layout = html.Div(
        [
            html.Div(
                [
                    html.Div(
                        [
                            html.Div(
                                "Setups",
                                style={"fontSize": "12px", "fontWeight": "600", "marginBottom": "4px"},
                            ),
                            dcc.Dropdown(
                                id="setup-selector",
                                options=[{"label": name, "value": name} for name in all_setups],
                                value=[],
                                multi=True,
                                clearable=True,
                                placeholder="Select setups...",
                            ),
                        ],
                        style={"flex": "1 1 220px", "minWidth": "200px"},
                    ),
                    html.Div(
                        [
                            html.Div(
                                "Experiment IDs",
                                style={"fontSize": "12px", "fontWeight": "600", "marginBottom": "4px"},
                            ),
                            dcc.Dropdown(
                                id="experiment-selector",
                                options=[{"label": name, "value": name} for name in all_experiment_ids],
                                value=all_experiment_ids,
                                multi=True,
                                clearable=True,
                                placeholder="Select experiment IDs...",
                            ),
                        ],
                        style={"flex": "1 1 280px", "minWidth": "220px"},
                    ),
                    html.Div(
                        [
                            html.Div(
                                "Attempts",
                                style={"fontSize": "12px", "fontWeight": "600", "marginBottom": "4px"},
                            ),
                            dcc.Dropdown(
                                id="attempt-selector",
                                options=[
                                    {"label": f"attempt{attempt}", "value": attempt}
                                    for attempt in all_attempts
                                ],
                                value=[],
                                multi=True,
                                clearable=True,
                                placeholder="Select attempts...",
                            ),
                        ],
                        style={"flex": "1 1 220px", "minWidth": "200px"},
                    ),
                    html.Div(
                        [
                            html.Div(
                                "Display",
                                style={"fontSize": "12px", "fontWeight": "600", "marginBottom": "4px"},
                            ),
                            dcc.Checklist(
                                id="display-options",
                                options=checklist_options,
                                value=initial_options,
                                inline=True,
                                inputStyle={"marginRight": "6px", "marginLeft": "12px"},
                                labelStyle={
                                    "display": "inline-flex",
                                    "alignItems": "center",
                                    "gap": "4px",
                                    "cursor": "pointer",
                                },
                                style={"display": "flex", "alignItems": "center", "gap": "2px"},
                            ),
                        ],
                        style={"flex": "0 1 auto"},
                    ),
                ],
                style={
                    "display": "flex",
                    "alignItems": "flex-end",
                    "gap": "16px",
                    "padding": "12px 16px",
                    "backgroundColor": "#f7f9fc",
                    "borderBottom": "1px solid #dbe2ee",
                    "flexWrap": "wrap",
                },
            ),
            html.Div(
                id="status-line",
                children=(
                    f"Loaded {len(all_runs)} runs across {len(all_setups)} setups, "
                    f"{len(all_experiment_ids)} experiment IDs, and {len(all_attempts)} attempts. "
                    f"Showing {initial_count} runs."
                ),
                style={"padding": "10px 16px", "fontSize": "13px", "color": "#334155"},
            ),
            dcc.Graph(
                id="step-response-graph",
                figure=initial_figure,
                style={"height": "78vh", "padding": "0 8px 8px 8px"},
                config={"displaylogo": False, "responsive": True},
                responsive=True,
            ),
            dcc.Store(id="legend-hidden-groups", data=[]),
            html.Div(
                [
                    html.Div(
                        "Visible runs metadata (llm_said)",
                        style={
                            "fontSize": "13px",
                            "fontWeight": "600",
                            "color": "#1e293b",
                            "marginBottom": "4px",
                        },
                    ),
                    html.Div(
                        "* marks best.txt-selected controller via PASS/WARN npy_match mapping. "
                        "† marks last design run before first tuning run per attempt.",
                        style={"fontSize": "12px", "color": "#475569", "marginBottom": "8px"},
                    ),
                    html.Div(id="llm-said-table", children=initial_table),
                ],
                style={
                    "margin": "4px 16px 14px 16px",
                    "padding": "10px 12px",
                    "backgroundColor": "#f8fafc",
                    "border": "1px solid #dbe2ee",
                    "borderRadius": "6px",
                },
            ),
        ]
    )

    @app.callback(
        Output("step-response-graph", "figure"),
        Output("status-line", "children"),
        Output("llm-said-table", "children"),
        Output("legend-hidden-groups", "data"),
        Input("setup-selector", "value"),
        Input("experiment-selector", "value"),
        Input("attempt-selector", "value"),
        Input("display-options", "value"),
        Input("step-response-graph", "restyleData"),
        State("step-response-graph", "figure"),
        State("legend-hidden-groups", "data"),
    )
    def update_figure(
        selected_setups: list[str] | None,
        selected_experiment_ids: list[str] | None,
        selected_attempts: list[int] | None,
        display_options: list[str] | None,
        restyle_data: Any,
        current_figure: dict[str, Any] | None,
        hidden_groups_data: Any,
    ):
        selected_setups = selected_setups or []
        selected_setups = [name for name in selected_setups if name in all_setups]

        selected_experiment_ids = selected_experiment_ids or []
        selected_experiment_ids = [
            name for name in selected_experiment_ids if name in all_experiment_ids
        ]

        selected_attempts = selected_attempts or []
        selected_attempts = [
            int(attempt) for attempt in selected_attempts if int(attempt) in all_attempts
        ]

        display_options = display_options or []
        show_reference = "show_reference" in display_options
        show_control = "show_control" in display_options
        normalize_response = "normalize_response" in display_options
        use_rainbow_colors = "rainbow_colors" in display_options
        short_legend = "short_legend" in display_options
        show_best_only = "best_only" in display_options
        show_design_checkpoint_only = "design_checkpoint_only" in display_options
        hidden_groups = _normalize_hidden_groups(hidden_groups_data)
        hidden_groups = _update_hidden_groups_from_restyle(
            hidden_groups=hidden_groups,
            restyle_data=restyle_data,
            figure=current_figure,
        )

        triggered_by_restyle = (
            ctx.triggered_id == "step-response-graph" and restyle_data is not None
        )
        if triggered_by_restyle:
            groups_in_figure = _legend_groups_in_figure(current_figure)
            filtered_runs = [
                rec for rec in all_runs if _legend_group_key(rec) in groups_in_figure
            ]
            shown_count = sum(
                1
                for rec in filtered_runs
                if _legend_group_key(rec) not in hidden_groups
            )
            table = _llm_said_table(
                filtered_runs,
                hidden_groups,
                best_legend_groups=best_legend_groups,
                dagger_legend_groups=dagger_legend_groups,
                controller_names_by_legend=controller_names_by_legend,
            )
            status = (
                f"Loaded {len(all_runs)} runs across {len(all_setups)} setups, "
                f"{len(all_experiment_ids)} experiment IDs, and {len(all_attempts)} attempts. "
                f"Showing {shown_count} visible runs for "
                f"{len(selected_setups)} selected setups, "
                f"{len(selected_experiment_ids)} selected experiment IDs, and "
                f"{len(selected_attempts)} selected attempts."
            )
            return no_update, status, table, sorted(hidden_groups)

        figure, shown_count, filtered_runs = build_figure(
            all_runs=all_runs,
            selected_setups=selected_setups,
            selected_experiment_ids=selected_experiment_ids,
            selected_attempts=selected_attempts,
            show_reference=show_reference,
            show_control=show_control,
            normalize_response=normalize_response,
            use_rainbow_colors=use_rainbow_colors,
            short_legend=short_legend,
            show_best_only=show_best_only,
            show_design_checkpoint_only=show_design_checkpoint_only,
            hidden_groups=hidden_groups,
            best_legend_groups=best_legend_groups,
            dagger_legend_groups=dagger_legend_groups,
        )
        table = _llm_said_table(
            filtered_runs,
            hidden_groups,
            best_legend_groups=best_legend_groups,
            dagger_legend_groups=dagger_legend_groups,
            controller_names_by_legend=controller_names_by_legend,
        )

        status = (
            f"Loaded {len(all_runs)} runs across {len(all_setups)} setups, "
            f"{len(all_experiment_ids)} experiment IDs, and {len(all_attempts)} attempts. "
            f"Showing {shown_count} visible runs for "
            f"{len(selected_setups)} selected setups, "
            f"{len(selected_experiment_ids)} selected experiment IDs, and "
            f"{len(selected_attempts)} selected attempts."
        )
        return figure, status, table, sorted(hidden_groups)

    return app


def main() -> None:
    args = parse_args()
    folder = args.folder.expanduser()
    current_run_folder = folder.parent
    runs, setups, experiment_ids, attempts, warnings = load_runs(folder)

    controller_to_run, run_to_controller, lookup_warnings = _load_pass_warn_lookups(
        current_run_folder
    )
    controller_paths_by_legend, controller_names_by_legend, controller_warnings = (
        _resolve_controller_targets(current_run_folder, run_to_controller)
    )
    best_legend_groups, best_warnings = _resolve_best_legend_groups(
        current_run_folder,
        controller_to_run,
    )
    dagger_legend_groups, dagger_warnings = _resolve_dagger_legend_groups(runs)
    warnings.extend(lookup_warnings)
    warnings.extend(controller_warnings)
    warnings.extend(best_warnings)
    warnings.extend(dagger_warnings)
    for warning in warnings:
        print(f"WARNING: {warning}", file=sys.stderr)

    app = create_app(
        all_runs=runs,
        all_setups=setups,
        all_experiment_ids=experiment_ids,
        all_attempts=attempts,
        warnings=warnings,
        best_legend_groups=best_legend_groups,
        dagger_legend_groups=dagger_legend_groups,
        current_run_folder=current_run_folder,
        controller_paths_by_legend=controller_paths_by_legend,
        controller_names_by_legend=controller_names_by_legend,
    )
    print(
        "Starting view_sim_step_responses.py "
        f"on http://{args.host}:{args.port} with folder={folder}"
    )
    app.run(host=args.host, port=args.port, debug=args.debug)


if __name__ == "__main__":
    main()
