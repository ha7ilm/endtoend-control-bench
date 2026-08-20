#!/usr/bin/env python3
"""Export selected saved step responses to a compact PDF figure."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.rcParams["pdf.fonttype"] = 42
matplotlib.rcParams["ps.fonttype"] = 42


def _configure_matplotlib_backend_from_argv() -> str:
    """Pick an interactive backend when requested, otherwise use Agg."""
    argv = set(sys.argv[1:])
    if "--interactive" not in argv:
        matplotlib.use("Agg")
        return str(matplotlib.get_backend())

    for backend_name in ("QtAgg", "TkAgg"):
        try:
            matplotlib.use(backend_name)
            return backend_name
        except Exception:
            continue

    matplotlib.use("Agg")
    return str(matplotlib.get_backend())


_MPL_BACKEND = _configure_matplotlib_backend_from_argv()

import matplotlib.pyplot as plt
import matplotlib.transforms as mtransforms
import numpy as np

try:
    from controlserver.config import get_setup_signal_metadata
except (
    ModuleNotFoundError
):  # pragma: no cover - runtime convenience for direct script execution
    repo_root = Path(__file__).resolve().parents[1]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    from controlserver.config import get_setup_signal_metadata

# Match subplot sizing/fonts from dashes/figure_cumulative_minimums.py.
PDF_SUBPLOT_HEIGHT_IN = 1.3
PDF_WIDTH_IN = 3.45
PDF_TITLE_FONTSIZE = 6.9
PDF_AXIS_LABEL_FONTSIZE = 7.2
PDF_TICK_FONTSIZE = 6.6
PDF_BASE_HSPACE = 0.26
PDF_EXTRA_VSPACE_PX = 4.0
PDF_PIXEL_DPI_REF = 96.0
TITLE_BORDER_WIDTH_PX = 1
TITLE_DOWNWARD_SHIFT_PX = 5

_RUN_FILE_RE = re.compile(r"^run(\d+)\.npy$")


SignalTrace = np.ndarray | dict[str, np.ndarray]


@dataclass(frozen=True)
class RunRecord:
    setup_name: str
    experiment_id: str
    attempt_n: int
    run_index: int
    time_sec: np.ndarray
    ref: SignalTrace
    meas: SignalTrace
    control: np.ndarray
    disturbance: np.ndarray | None
    kpis: Mapping[str, Any]
    llm_said: Mapping[str, Any] | None
    file_path: Path
    legend_label: str | None = None


@dataclass(frozen=True)
class ExplicitRunSelector:
    setup_name: str
    experiment_id: str
    attempt_n: int
    run_index: int
    legend_suffix: str = ""
    legend_label_override: str | None = None

    def legend_label(self) -> str:
        if self.legend_label_override:
            return self.legend_label_override
        base = (
            f"{self.setup_name}/{self.experiment_id}/"
            f"attempt{self.attempt_n}/run{self.run_index}"
        )
        if self.legend_suffix:
            return f"{base}{self.legend_suffix}"
        return base


@dataclass(frozen=True)
class FigureExportSpec:
    output_name: str
    setup_name: str
    selectors: tuple[ExplicitRunSelector, ...]
    show_reference: bool
    show_control: bool
    show_disturbance: bool = False
    normalize_response: bool = False
    short_legend: bool = False
    use_rainbow_colors: bool = False
    show_response_legends: bool = True
    show_control_legend: bool = True
    meas_display_name_override: str | None = None
    control_display_name_override: str | None = None
    control_label_suffix: str = " u"
    figure_height_scale: float = 1.0
    subplot_adjust: Mapping[str, float] | None = None
    top_ylim_padding_fraction: float = 0.0
    response_legend_prefix: str = ""
    single_reference_signal: bool = False
    reference_signal_label: str = "Reference"
    reference_signal_color: str = "gray"
    response_legend_loc: str = "best"
    response_legend_bbox_anchor: tuple[float, float] | None = None
    response_legend_ncol: int = 1
    response_reference_on_bottom_row: bool = False
    xlim_sec: tuple[float, float] | None = None
    subplot_height_ratios: tuple[float, ...] | None = None


FIGURE_IDS = (
    "cruisecontrol_dt_codex",
    "cruisecontrol_hondajazz_wiggle",
    "motorspeed_dt_lim_maxonre30_proper",
)


def _hspace_with_extra_pixels(
    nrows: int,
    figure_height_in: float,
    top: float,
    bottom: float,
    base_hspace: float,
    extra_pixels: float,
    pixel_dpi: float,
) -> float:
    """Compute hspace so inter-row gap grows by a fixed pixel-equivalent delta."""
    if nrows <= 1:
        return base_hspace

    usable_height = figure_height_in * (top - bottom)
    base_gap = base_hspace * usable_height / (nrows + (nrows - 1) * base_hspace)
    target_gap = base_gap + (extra_pixels / pixel_dpi)
    denom = usable_height - target_gap * (nrows - 1)
    if denom <= 0:
        return base_hspace
    return (target_gap * nrows) / denom


def _coerce_1d_array(
    value: Any,
    *,
    key: str,
    file_path: Path,
    expected_len: int | None = None,
) -> np.ndarray:
    arr = np.asarray(value, dtype=float)
    if arr.ndim != 1:
        raise ValueError(f"{file_path}: '{key}' must be 1D")
    if arr.size == 0:
        raise ValueError(f"{file_path}: '{key}' must not be empty")
    if not np.isfinite(arr).all():
        raise ValueError(f"{file_path}: '{key}' contains non-finite values")
    if expected_len is not None and int(arr.shape[0]) != int(expected_len):
        raise ValueError(
            f"{file_path}: '{key}' length {arr.shape[0]} does not match {expected_len}"
        )
    return arr


def _coerce_signal_trace(
    value: Any,
    *,
    key: str,
    file_path: Path,
    expected_len: int,
) -> SignalTrace:
    if isinstance(value, Mapping):
        trace: dict[str, np.ndarray] = {}
        for channel_name, channel_value in value.items():
            if not isinstance(channel_name, str) or not channel_name.strip():
                raise ValueError(f"{file_path}: '{key}' has an invalid channel name")
            arr = _coerce_1d_array(
                channel_value,
                key=f"{key}.{channel_name}",
                file_path=file_path,
                expected_len=expected_len,
            )
            trace[channel_name] = arr
        if not trace:
            raise ValueError(f"{file_path}: '{key}' has no channels")
        return trace

    return _coerce_1d_array(
        value,
        key=key,
        file_path=file_path,
        expected_len=expected_len,
    )


def _run_index_from_name(file_name: str) -> int | None:
    match = _RUN_FILE_RE.fullmatch(file_name)
    if not match:
        return None
    return int(match.group(1))


def _resolve_sim_folder(folder: Path) -> Path:
    direct_sim = folder / "sim"
    if direct_sim.is_dir():
        return direct_sim
    if folder.is_dir():
        return folder
    raise FileNotFoundError(f"Folder not found: {folder}")


def _load_one_run(
    *,
    run_path: Path,
    setup_name: str,
    experiment_id: str,
    attempt_n: int,
    run_index: int,
    legend_label: str | None = None,
) -> RunRecord:
    payload_obj = np.load(run_path, allow_pickle=True)
    try:
        payload = payload_obj.item()
    except Exception as exc:  # pragma: no cover - defensive format guard
        raise ValueError(f"{run_path}: expected dict payload") from exc
    if not isinstance(payload, Mapping):
        raise ValueError(f"{run_path}: expected dict payload")

    setup_value = str(payload.get("setup", "")).strip()
    if setup_value and setup_value != setup_name:
        raise ValueError(
            f"{run_path}: setup '{setup_value}' does not match requested '{setup_name}'"
        )

    time_sec = _coerce_1d_array(
        payload.get("time_sec"), key="time_sec", file_path=run_path
    )
    expected_len = int(time_sec.shape[0])
    ref = _coerce_signal_trace(
        payload.get("ref"),
        key="ref",
        file_path=run_path,
        expected_len=expected_len,
    )
    meas = _coerce_signal_trace(
        payload.get("meas"),
        key="meas",
        file_path=run_path,
        expected_len=expected_len,
    )
    control = _coerce_1d_array(
        payload.get("control"),
        key="control",
        file_path=run_path,
        expected_len=expected_len,
    )
    disturbance_raw = payload.get("disturbance")
    disturbance = None
    if disturbance_raw is not None:
        disturbance = _coerce_1d_array(
            disturbance_raw,
            key="disturbance",
            file_path=run_path,
            expected_len=expected_len,
        )

    kpis_raw = payload.get("kpis")
    kpis = kpis_raw if isinstance(kpis_raw, Mapping) else {}
    llm_said_raw = payload.get("llm_said")
    llm_said = llm_said_raw if isinstance(llm_said_raw, Mapping) else None

    return RunRecord(
        setup_name=setup_name,
        experiment_id=experiment_id,
        attempt_n=attempt_n,
        run_index=run_index,
        time_sec=time_sec,
        ref=ref,
        meas=meas,
        control=control,
        disturbance=disturbance,
        kpis=kpis,
        llm_said=llm_said,
        file_path=run_path,
        legend_label=legend_label,
    )


def _load_selected_runs(
    *,
    sim_folder: Path,
    setup_name: str,
    experiment_id: str,
    attempt_n: int,
    run_indices: set[int] | None,
) -> tuple[list[RunRecord], list[str]]:
    attempt_dir = sim_folder / setup_name / experiment_id / f"attempt{attempt_n}"
    if not attempt_dir.is_dir():
        raise FileNotFoundError(f"Attempt folder not found: {attempt_dir}")

    selected_paths: list[tuple[int, Path]] = []
    for run_path in attempt_dir.glob("run*.npy"):
        run_idx = _run_index_from_name(run_path.name)
        if run_idx is None:
            continue
        if run_indices is not None and run_idx not in run_indices:
            continue
        selected_paths.append((run_idx, run_path))
    selected_paths.sort(key=lambda item: item[0])

    if not selected_paths:
        suffix = f" matching run indices {sorted(run_indices)}" if run_indices else ""
        raise FileNotFoundError(f"No run*.npy files found in {attempt_dir}{suffix}")

    found_indices = {idx for idx, _ in selected_paths}
    warnings: list[str] = []
    if run_indices is not None:
        missing = sorted(run_indices - found_indices)
        if missing:
            warnings.append(
                "Requested run indices were not found in the attempt folder: "
                + ", ".join(str(v) for v in missing)
            )

    runs: list[RunRecord] = []
    for run_idx, run_path in selected_paths:
        try:
            record = _load_one_run(
                run_path=run_path,
                setup_name=setup_name,
                experiment_id=experiment_id,
                attempt_n=attempt_n,
                run_index=run_idx,
            )
        except Exception as exc:
            warnings.append(f"Skipping {run_path}: {exc}")
            continue
        runs.append(record)

    if not runs:
        raise RuntimeError("No valid run files could be loaded after validation")
    return runs, warnings


def _trace_channels(trace: SignalTrace) -> list[str | None]:
    if isinstance(trace, dict):
        return list(trace.keys())
    return [None]


def _extract_channel(trace: SignalTrace, channel_name: str | None) -> np.ndarray:
    if isinstance(trace, dict):
        if channel_name is None:
            raise ValueError("Channel name is required for dict-valued traces")
        if channel_name not in trace:
            raise ValueError(f"Channel '{channel_name}' not present in trace")
        return trace[channel_name]

    if channel_name is not None:
        raise ValueError(f"Trace is scalar-valued; unexpected channel '{channel_name}'")
    return trace


def _legend_group_key(record: RunRecord) -> str:
    if record.legend_label:
        return record.legend_label
    return (
        f"{record.setup_name}/{record.experiment_id}/"
        f"attempt{record.attempt_n}/run{record.run_index}"
    )


def _format_signal_label(
    *,
    display_name: str,
    unit: str,
    channel_name: str | None,
    normalized: bool,
) -> str:
    raw_name = display_name if isinstance(display_name, str) else str(display_name)
    if "\n" in raw_name:
        # Preserve explicit line breaks from figure-specific label overrides.
        name = raw_name.strip(" \t") or "Signal"
    else:
        name = raw_name.strip() or "Signal"
    if channel_name:
        name = f"{name} ({channel_name})"
    if normalized:
        return f"{name} (normalized)"
    if unit.strip():
        if name.endswith("\n"):
            return f"{name}[{unit.strip()}]"
        return f"{name} [{unit.strip()}]"
    return name


def _title_text(prefix: str, channel_name: str | None) -> str:
    if channel_name is None:
        return prefix
    return f"{prefix} ({channel_name})"


def _style_axis_title(ax: plt.Axes, fig: plt.Figure, text: str) -> None:
    title_artist = ax.set_title(
        text,
        fontsize=PDF_TITLE_FONTSIZE,
        y=1.0,
        pad=2,
        bbox={
            "facecolor": "white",
            "edgecolor": "black",
            "linewidth": float(TITLE_BORDER_WIDTH_PX),
            "boxstyle": "square,pad=0.15",
        },
    )
    title_artist.set_transform(
        title_artist.get_transform()
        + mtransforms.ScaledTranslation(
            0.0,
            -TITLE_DOWNWARD_SHIFT_PX / fig.dpi,
            fig.dpi_scale_trans,
        )
    )


def _add_top_ylim_padding(ax: plt.Axes, fraction: float) -> None:
    if fraction <= 0.0:
        return
    ymin, ymax = ax.get_ylim()
    if not np.isfinite([ymin, ymax]).all():
        return
    if np.isclose(ymin, ymax):
        span = abs(ymax) if not np.isclose(ymax, 0.0) else 1.0
    else:
        span = abs(ymax - ymin)
    pad = span * fraction
    if ymax >= ymin:
        ax.set_ylim(ymin, ymax + pad)
    else:
        ax.set_ylim(ymin + pad, ymax)


def _rainbow_colors(n: int) -> list[tuple[float, float, float, float]]:
    if n <= 0:
        return []
    cmap = plt.get_cmap("turbo")
    if n == 1:
        return [cmap(0.5)]
    return [cmap(x) for x in np.linspace(0.0, 1.0, num=n)]


def _move_reference_legend_to_bottom_row(
    handles: list[Any],
    labels: list[str],
    *,
    reference_label: str,
    ncol: int,
) -> tuple[list[Any], list[str]]:
    if ncol <= 1 or not labels:
        return handles, labels
    try:
        ref_idx = labels.index(reference_label)
    except ValueError:
        return handles, labels

    nrows = int(np.ceil(len(labels) / ncol))
    if nrows <= 1:
        return handles, labels
    bottom_positions = [idx for idx in range(len(labels)) if idx % nrows == (nrows - 1)]
    if not bottom_positions:
        return handles, labels
    target_idx = bottom_positions[-1]
    if ref_idx == target_idx:
        return handles, labels

    moved_handle = handles.pop(ref_idx)
    moved_label = labels.pop(ref_idx)
    if ref_idx < target_idx:
        target_idx -= 1
    handles.insert(target_idx, moved_handle)
    labels.insert(target_idx, moved_label)
    return handles, labels


def build_pdf_figure(
    runs: Sequence[RunRecord],
    *,
    setup_name: str,
    show_reference: bool,
    show_control: bool,
    show_disturbance: bool,
    normalize_response: bool,
    short_legend: bool,
    use_rainbow_colors: bool,
    preserve_run_order: bool = False,
    show_response_legends: bool = True,
    show_control_legend: bool = True,
    meas_display_name_override: str | None = None,
    control_display_name_override: str | None = None,
    control_label_suffix: str = " u",
    response_legend_prefix: str = "",
    single_reference_signal: bool = False,
    reference_signal_label: str = "Reference",
    reference_signal_color: str = "gray",
    response_legend_loc: str = "best",
    response_legend_bbox_anchor: tuple[float, float] | None = None,
    response_legend_ncol: int = 1,
    response_reference_on_bottom_row: bool = False,
    subplot_height_ratios: Sequence[float] | None = None,
) -> plt.Figure:
    if not runs:
        raise ValueError("No runs were provided")

    sorted_runs = (
        list(runs)
        if preserve_run_order
        else sorted(runs, key=lambda rec: rec.run_index)
    )
    response_channels = _trace_channels(sorted_runs[0].meas)
    if _trace_channels(sorted_runs[0].ref) != response_channels:
        raise ValueError(
            "The selected run has mismatched channels between ref and meas"
        )
    for record in sorted_runs[1:]:
        if _trace_channels(record.meas) != response_channels:
            raise ValueError("Selected runs do not share the same measured channels")
        if _trace_channels(record.ref) != response_channels:
            raise ValueError("Selected runs do not share the same reference channels")

    metadata = get_setup_signal_metadata(setup_name)
    meas_meta = metadata.get("meas", {})
    control_meta = metadata.get("control", {})

    include_disturbance = show_disturbance and any(
        record.disturbance is not None for record in sorted_runs
    )
    nrows = len(response_channels) + int(show_control) + int(include_disturbance)
    if nrows <= 0:
        raise ValueError("No subplot rows to render")

    top = 0.975
    bottom = 0.11
    hspace = _hspace_with_extra_pixels(
        nrows=nrows,
        figure_height_in=PDF_SUBPLOT_HEIGHT_IN * nrows,
        top=top,
        bottom=bottom,
        base_hspace=PDF_BASE_HSPACE,
        extra_pixels=PDF_EXTRA_VSPACE_PX,
        pixel_dpi=PDF_PIXEL_DPI_REF,
    )

    subplot_kwargs: dict[str, Any] = {}
    if subplot_height_ratios is not None and len(subplot_height_ratios) == nrows:
        height_ratios: list[float] = []
        valid = True
        for ratio in subplot_height_ratios:
            try:
                ratio_float = float(ratio)
            except (TypeError, ValueError):
                valid = False
                break
            if not np.isfinite(ratio_float) or ratio_float <= 0.0:
                valid = False
                break
            height_ratios.append(ratio_float)
        if valid:
            subplot_kwargs["gridspec_kw"] = {"height_ratios": height_ratios}

    fig, axes_arr = plt.subplots(
        nrows=nrows,
        ncols=1,
        figsize=(PDF_WIDTH_IN, PDF_SUBPLOT_HEIGHT_IN * nrows),
        sharex=True,
        squeeze=False,
        **subplot_kwargs,
    )
    fig.subplots_adjust(left=0.16, right=0.98, top=top, bottom=bottom, hspace=hspace)
    axes = [axes_arr[row_i, 0] for row_i in range(nrows)]

    if use_rainbow_colors:
        colors = _rainbow_colors(len(sorted_runs))
    else:
        tab10 = plt.get_cmap("tab10")
        colors = [tab10(i % 10) for i in range(len(sorted_runs))]

    legend_lookup: dict[str, str] = {}
    if short_legend:
        for idx, record in enumerate(sorted_runs):
            legend_lookup[_legend_group_key(record)] = f"Iteration {idx + 1}"

    row_index = 0
    for channel_name in response_channels:
        ax = axes[row_index]
        _style_axis_title(ax, fig, _title_text("Step response", channel_name))
        reference_time: np.ndarray | None = None
        reference_trace: np.ndarray | None = None
        for run_idx, record in enumerate(sorted_runs):
            legend_group = _legend_group_key(record)
            legend_name = legend_lookup.get(legend_group, legend_group)
            response_legend_name = f"{response_legend_prefix}{legend_name}"
            color = colors[run_idx]

            ref_trace = _extract_channel(record.ref, channel_name)
            meas_trace = _extract_channel(record.meas, channel_name)
            ref_plot = ref_trace
            meas_plot = meas_trace
            if normalize_response:
                scale = float(np.nanmax(np.abs(ref_trace)))
                if np.isfinite(scale) and scale > 0.0:
                    ref_plot = ref_trace / scale
                    meas_plot = meas_trace / scale

            ax.plot(
                record.time_sec,
                meas_plot,
                color=color,
                linewidth=0.8,
                alpha=0.8,
                label=response_legend_name,
                zorder=2.0,
            )
            if show_reference:
                if single_reference_signal:
                    if run_idx == 0:
                        reference_time = record.time_sec
                        reference_trace = ref_plot
                else:
                    ax.plot(
                        record.time_sec,
                        ref_plot,
                        color=color,
                        linewidth=0.8,
                        alpha=0.65,
                        linestyle="--",
                        label=f"{legend_name} ref",
                        zorder=1.5,
                    )
        if (
            show_reference
            and single_reference_signal
            and reference_time is not None
            and reference_trace is not None
        ):
            ax.plot(
                reference_time,
                reference_trace,
                color=reference_signal_color,
                linewidth=0.8,
                alpha=0.8,
                linestyle="--",
                label=reference_signal_label,
                zorder=1.0,
            )

        ax.set_ylabel(
            _format_signal_label(
                display_name=(
                    meas_display_name_override
                    if meas_display_name_override is not None
                    else str(meas_meta.get("display_name", "Measured response"))
                ),
                unit=str(meas_meta.get("unit", "")),
                channel_name=channel_name,
                normalized=normalize_response,
            ),
            fontsize=PDF_AXIS_LABEL_FONTSIZE,
        )
        ax.minorticks_on()
        ax.grid(which="major", alpha=0.35, linewidth=0.35)
        ax.grid(which="minor", alpha=0.25, linewidth=0.3)
        ax.tick_params(axis="both", labelsize=PDF_TICK_FONTSIZE, length=2)
        ax.tick_params(axis="both", which="minor", length=0)
        if show_response_legends:
            legend_ncol = max(1, int(response_legend_ncol))
            legend_kwargs: dict[str, Any] = {
                "loc": response_legend_loc,
                "fontsize": 5.8,
                "frameon": True,
                "framealpha": 1.0,
                "borderpad": 0.2,
                "handlelength": 1.2,
                "handletextpad": 0.4,
                "ncol": legend_ncol,
            }
            if response_legend_bbox_anchor is not None:
                legend_kwargs["bbox_to_anchor"] = response_legend_bbox_anchor
            handles, labels = ax.get_legend_handles_labels()
            if response_reference_on_bottom_row:
                handles, labels = _move_reference_legend_to_bottom_row(
                    handles,
                    labels,
                    reference_label=reference_signal_label,
                    ncol=legend_ncol,
                )
            ax.legend(handles, labels, **legend_kwargs)
        row_index += 1

    if show_control:
        ax = axes[row_index]
        _style_axis_title(ax, fig, "Controller output / Actuator input")
        for run_idx, record in enumerate(sorted_runs):
            legend_group = _legend_group_key(record)
            legend_name = legend_lookup.get(legend_group, legend_group)
            color = colors[run_idx]
            ax.plot(
                record.time_sec,
                record.control,
                color=color,
                linewidth=0.8,
                alpha=0.8,
                label=f"{legend_name}{control_label_suffix}",
            )
        ax.set_ylabel(
            _format_signal_label(
                display_name=(
                    control_display_name_override
                    if control_display_name_override is not None
                    else str(control_meta.get("display_name", "Control signal"))
                ),
                unit=str(control_meta.get("unit", "")),
                channel_name=None,
                normalized=False,
            ),
            fontsize=PDF_AXIS_LABEL_FONTSIZE,
        )
        ax.minorticks_on()
        ax.grid(which="major", alpha=0.35, linewidth=0.35)
        ax.grid(which="minor", alpha=0.25, linewidth=0.3)
        ax.tick_params(axis="both", labelsize=PDF_TICK_FONTSIZE, length=2)
        ax.tick_params(axis="both", which="minor", length=0)
        if show_control_legend:
            ax.legend(
                loc="best",
                fontsize=5.8,
                frameon=True,
                framealpha=1.0,
                borderpad=0.2,
                handlelength=1.2,
                handletextpad=0.4,
            )
        row_index += 1

    if include_disturbance:
        ax = axes[row_index]
        _style_axis_title(ax, fig, "Disturbance")
        for run_idx, record in enumerate(sorted_runs):
            if record.disturbance is None:
                continue
            legend_group = _legend_group_key(record)
            legend_name = legend_lookup.get(legend_group, legend_group)
            color = colors[run_idx]
            ax.plot(
                record.time_sec,
                record.disturbance,
                color=color,
                linewidth=0.8,
                alpha=0.8,
                linestyle=":",
                label=f"{legend_name} d",
            )
        ax.set_ylabel("Disturbance", fontsize=PDF_AXIS_LABEL_FONTSIZE)
        ax.minorticks_on()
        ax.grid(which="major", alpha=0.35, linewidth=0.35)
        ax.grid(which="minor", alpha=0.25, linewidth=0.3)
        ax.tick_params(axis="both", labelsize=PDF_TICK_FONTSIZE, length=2)
        ax.tick_params(axis="both", which="minor", length=0)
        ax.legend(
            loc="best",
            fontsize=5.8,
            frameon=True,
            framealpha=1.0,
            borderpad=0.2,
            handlelength=1.2,
            handletextpad=0.4,
        )

    axes[-1].set_xlabel("Time [s]", fontsize=PDF_AXIS_LABEL_FONTSIZE, labelpad=2)
    return fig


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export three fixed paper figures as compact PDFs.",
    )
    parser.add_argument(
        "--folder",
        type=Path,
        default=Path("results/current_run"),
        help=(
            "Root results folder (expects '<folder>/sim/...') or direct sim folder path. "
            "Default: results/current_run"
        ),
    )
    parser.add_argument(
        "--figure",
        dest="figure_ids",
        action="append",
        choices=FIGURE_IDS,
        default=None,
        help=(
            "Only export a specific figure id. Repeat this option to export multiple ids. "
            f"Choices: {', '.join(FIGURE_IDS)}"
        ),
    )
    parser.add_argument(
        "--interactive",
        action="store_true",
        default=False,
        help=(
            "Open each selected figure in Matplotlib's interactive UI before saving "
            "(toolbar contains subplot and axis editors)."
        ),
    )
    parser.add_argument(
        "--layout-overrides",
        type=Path,
        default=None,
        help=(
            "Optional JSON file containing per-figure layout overrides to apply before "
            "rendering/saving."
        ),
    )
    parser.add_argument(
        "--write-layout-json",
        type=Path,
        default=None,
        help=(
            "Write captured figure layout state to this JSON file. If omitted and "
            "--interactive is used, defaults to "
            "<folder>/analysis_artifacts/figures/figure_specific_step_responses_layout.json."
        ),
    )
    return parser.parse_args()


def _figure_id_from_output_name(output_name: str) -> str:
    output_lower = output_name.lower()
    if output_lower.endswith(".pdf"):
        return output_name[:-4]
    return output_name


def _load_layout_overrides(path: Path | None) -> dict[str, Mapping[str, Any]]:
    if path is None:
        return {}
    if not path.is_file():
        raise FileNotFoundError(f"Layout overrides file not found: {path}")

    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError(f"{path}: expected a JSON object")

    figures_section = payload.get("figures", payload)
    if not isinstance(figures_section, Mapping):
        raise ValueError(f"{path}: expected 'figures' to be a JSON object")

    overrides: dict[str, Mapping[str, Any]] = {}
    for key, value in figures_section.items():
        if not isinstance(key, str) or not isinstance(value, Mapping):
            continue
        overrides[key] = value
    return overrides


def _apply_layout_overrides(figure: plt.Figure, overrides: Mapping[str, Any]) -> None:
    figsize_raw = overrides.get("figsize_inches")
    if isinstance(figsize_raw, Sequence) and len(figsize_raw) == 2:
        try:
            figure.set_size_inches(
                float(figsize_raw[0]), float(figsize_raw[1]), forward=True
            )
        except (TypeError, ValueError):
            pass

    subplotpars_raw = overrides.get("subplotpars")
    if isinstance(subplotpars_raw, Mapping):
        adjust_kwargs: dict[str, float] = {}
        for key in ("left", "right", "bottom", "top", "wspace", "hspace"):
            value = subplotpars_raw.get(key)
            if value is None:
                continue
            try:
                adjust_kwargs[key] = float(value)
            except (TypeError, ValueError):
                continue
        if adjust_kwargs:
            figure.subplots_adjust(**adjust_kwargs)

    axes_raw = overrides.get("axes")
    if not isinstance(axes_raw, Sequence):
        return

    for axis_override in axes_raw:
        if not isinstance(axis_override, Mapping):
            continue
        index_raw = axis_override.get("index")
        try:
            axis_index = int(index_raw)
        except (TypeError, ValueError):
            continue
        if axis_index < 0 or axis_index >= len(figure.axes):
            continue
        axis = figure.axes[axis_index]

        xlim_raw = axis_override.get("xlim")
        if isinstance(xlim_raw, Sequence) and len(xlim_raw) == 2:
            try:
                axis.set_xlim(float(xlim_raw[0]), float(xlim_raw[1]))
            except (TypeError, ValueError):
                pass

        ylim_raw = axis_override.get("ylim")
        if isinstance(ylim_raw, Sequence) and len(ylim_raw) == 2:
            try:
                axis.set_ylim(float(ylim_raw[0]), float(ylim_raw[1]))
            except (TypeError, ValueError):
                pass

        position_raw = axis_override.get("position")
        if isinstance(position_raw, Sequence) and len(position_raw) == 4:
            try:
                bounds = tuple(float(value) for value in position_raw)
                axis.set_position(bounds)
            except (TypeError, ValueError):
                pass

        title_raw = axis_override.get("title")
        if isinstance(title_raw, str):
            axis.set_title(title_raw)
        xlabel_raw = axis_override.get("xlabel")
        if isinstance(xlabel_raw, str):
            axis.set_xlabel(xlabel_raw)
        ylabel_raw = axis_override.get("ylabel")
        if isinstance(ylabel_raw, str):
            axis.set_ylabel(ylabel_raw)

        legend_loc = axis_override.get("legend_loc")
        if legend_loc is not None:
            legend = axis.get_legend()
            if legend is not None:
                try:
                    legend.set_loc(legend_loc)
                except Exception:
                    pass


def _capture_layout_state(figure: plt.Figure) -> dict[str, Any]:
    subplotpars = figure.subplotpars
    axes_state: list[dict[str, Any]] = []
    for axis_index, axis in enumerate(figure.axes):
        legend = axis.get_legend()
        legend_loc = None
        if legend is not None:
            legend_loc = getattr(legend, "_loc", None)
            if legend_loc is not None and not isinstance(legend_loc, (int, str)):
                legend_loc = str(legend_loc)
        axes_state.append(
            {
                "index": axis_index,
                "title": axis.get_title(),
                "xlabel": axis.get_xlabel(),
                "ylabel": axis.get_ylabel(),
                "xlim": [float(v) for v in axis.get_xlim()],
                "ylim": [float(v) for v in axis.get_ylim()],
                "position": [float(v) for v in axis.get_position().bounds],
                "legend_loc": legend_loc,
            }
        )

    return {
        "figsize_inches": [float(v) for v in figure.get_size_inches()],
        "subplotpars": {
            "left": float(subplotpars.left),
            "right": float(subplotpars.right),
            "bottom": float(subplotpars.bottom),
            "top": float(subplotpars.top),
            "wspace": float(subplotpars.wspace),
            "hspace": float(subplotpars.hspace),
        },
        "axes": axes_state,
    }


def _show_interactive_editor(figure: plt.Figure, *, output_name: str) -> None:
    manager = getattr(figure.canvas, "manager", None)
    if manager is not None and hasattr(manager, "set_window_title"):
        manager.set_window_title(output_name)
    print(
        "[interactive] Close the figure window after tuning with toolbar actions "
        "('Configure subplots' and 'Edit axis, curve and image parameters').",
        file=sys.stderr,
    )
    plt.show(block=True)


def _load_explicit_runs(
    *,
    sim_folder: Path,
    selectors: Sequence[ExplicitRunSelector],
) -> tuple[list[RunRecord], list[str]]:
    warnings: list[str] = []
    runs: list[RunRecord] = []
    for selector in selectors:
        run_path = (
            sim_folder
            / selector.setup_name
            / selector.experiment_id
            / f"attempt{selector.attempt_n}"
            / f"run{selector.run_index}.npy"
        )
        if not run_path.is_file():
            warnings.append(f"Missing run file: {run_path}")
            continue
        try:
            record = _load_one_run(
                run_path=run_path,
                setup_name=selector.setup_name,
                experiment_id=selector.experiment_id,
                attempt_n=selector.attempt_n,
                run_index=selector.run_index,
                legend_label=selector.legend_label(),
            )
        except Exception as exc:
            warnings.append(f"Skipping {run_path}: {exc}")
            continue
        runs.append(record)

    if not runs:
        raise RuntimeError("No valid run files could be loaded after validation")
    return runs, warnings


def _fixed_figure_specs() -> tuple[FigureExportSpec, ...]:
    return (
        FigureExportSpec(
            output_name="cruisecontrol_dt_codex.pdf",
            setup_name="cruisecontrol_dt",
            selectors=tuple(
                ExplicitRunSelector(
                    setup_name="cruisecontrol_dt",
                    experiment_id="customctlchoice_codex53xhigh",
                    attempt_n=0,
                    run_index=run_idx,
                    legend_label_override=f"Iteration {run_idx + 1}",
                )
                for run_idx in (0, 1, 2, 3, 4)
            ),
            show_reference=True,
            show_control=False,
            short_legend=False,
            use_rainbow_colors=True,
            meas_display_name_override="Speed",
            single_reference_signal=True,
            reference_signal_label="Reference",
            reference_signal_color="gray",
            response_legend_ncol=3,
            figure_height_scale=0.68,
            top_ylim_padding_fraction=0.10,
            subplot_adjust={
                "top": 0.91,
                "bottom": 0.34,
                "left": 0.11,
                "right": 0.995,
                "hspace": 0.26,
                "wspace": 0.2,
            },
        ),
        FigureExportSpec(
            output_name="cruisecontrol_hondajazz_wiggle.pdf",
            setup_name="cruisecontrol_dt_lim_hondajazz",
            selectors=(
                ExplicitRunSelector(
                    setup_name="cruisecontrol_dt_lim_hondajazz",
                    experiment_id="customctlchoice_opus46high",
                    attempt_n=0,
                    run_index=4,
                    legend_suffix="*",
                    legend_label_override="Opus 4.6",
                ),
                ExplicitRunSelector(
                    setup_name="cruisecontrol_dt_lim_hondajazz",
                    experiment_id="customctlchoice_codex53xhigh",
                    attempt_n=0,
                    run_index=6,
                    legend_suffix="*",
                    legend_label_override="Codex 5.3",
                ),
            ),
            show_reference=True,
            show_control=True,
            show_response_legends=True,
            show_control_legend=False,
            meas_display_name_override="Speed\n",
            control_display_name_override="Traction",
            control_label_suffix="",
            figure_height_scale=0.5,
            subplot_adjust={
                "top": 0.945,
                "bottom": 0.23,
                "left": 0.14,
                "right": 0.995,
                "hspace": 0.313,
                "wspace": 0.2,
            },
            top_ylim_padding_fraction=0.30,
            single_reference_signal=True,
            reference_signal_label="Reference",
            reference_signal_color="gray",
            response_legend_ncol=3,
        ),
        FigureExportSpec(
            output_name="motorspeed_dt_lim_maxonre30_proper.pdf",
            setup_name="motorspeed_dt_lim_maxonre30",
            selectors=(
                ExplicitRunSelector(
                    setup_name="motorspeed_dt_lim_maxonre30",
                    experiment_id="customctlchoice_codex53xhigh",
                    attempt_n=0,
                    run_index=2,
                    legend_label_override="Codex 5.3 #1",
                ),
                ExplicitRunSelector(
                    setup_name="motorspeed_dt_lim_maxonre30",
                    experiment_id="customctlchoice_codex53xhigh",
                    attempt_n=1,
                    run_index=2,
                    legend_label_override="Codex 5.3 #2",
                ),
                ExplicitRunSelector(
                    setup_name="motorspeed_dt_lim_maxonre30",
                    experiment_id="customctlchoice_codex53xhigh",
                    attempt_n=2,
                    run_index=1,
                    legend_label_override="Codex 5.3 #3",
                ),
                ExplicitRunSelector(
                    setup_name="motorspeed_dt_lim_maxonre30",
                    experiment_id="customctlchoice_opus46high",
                    attempt_n=0,
                    run_index=0,
                    legend_label_override="Opus 4.6 #1",
                ),
                ExplicitRunSelector(
                    setup_name="motorspeed_dt_lim_maxonre30",
                    experiment_id="customctlchoice_opus46high",
                    attempt_n=1,
                    run_index=0,
                    legend_label_override="Opus 4.6 #2",
                ),
                ExplicitRunSelector(
                    setup_name="motorspeed_dt_lim_maxonre30",
                    experiment_id="customctlchoice_opus46high",
                    attempt_n=2,
                    run_index=0,
                    legend_label_override="Opus 4.6 #3",
                ),
            ),
            show_reference=True,
            show_control=True,
            show_control_legend=False,
            meas_display_name_override="Speed",
            control_display_name_override="Armature \n voltage",
            single_reference_signal=True,
            reference_signal_label="Reference",
            reference_signal_color="gray",
            response_legend_loc="best",
            response_legend_ncol=2,
            response_reference_on_bottom_row=True,
            xlim_sec=(-0.05, 0.55),
            figure_height_scale=0.648,
            top_ylim_padding_fraction=0.10,
            subplot_height_ratios=(2.0, 1.0),
            subplot_adjust={
                "top": 0.955,
                "bottom": 0.185,
                "left": 0.135,
                "right": 0.995,
                "hspace": 0.218,
                "wspace": 0.175,
            },
        ),
    )


def main() -> None:
    args = parse_args()
    sim_folder = _resolve_sim_folder(args.folder)
    output_dir = args.folder / "analysis_artifacts" / "figures"
    output_dir.mkdir(parents=True, exist_ok=True)
    selected_specs = list(_fixed_figure_specs())
    if args.figure_ids:
        selected_ids = set(args.figure_ids)
        selected_specs = [
            spec
            for spec in selected_specs
            if _figure_id_from_output_name(spec.output_name) in selected_ids
        ]
    if not selected_specs:
        raise RuntimeError("No figures selected for export")

    layout_overrides = _load_layout_overrides(args.layout_overrides)
    active_backend = str(matplotlib.get_backend()).strip().lower()
    if args.interactive and active_backend == "agg":
        raise RuntimeError(
            "Interactive mode requested, but no interactive Matplotlib backend is available. "
            "Install/configure Tk or Qt, then rerun with --interactive."
        )

    captured_layouts: dict[str, dict[str, Any]] = {}
    for spec in selected_specs:
        runs, warnings = _load_explicit_runs(
            sim_folder=sim_folder, selectors=spec.selectors
        )
        for warning in warnings:
            print(f"[warning] {warning}", file=sys.stderr)

        figure = build_pdf_figure(
            runs=runs,
            setup_name=spec.setup_name,
            show_reference=spec.show_reference,
            show_control=spec.show_control,
            show_disturbance=spec.show_disturbance,
            normalize_response=spec.normalize_response,
            short_legend=spec.short_legend,
            use_rainbow_colors=spec.use_rainbow_colors,
            preserve_run_order=True,
            show_response_legends=spec.show_response_legends,
            show_control_legend=spec.show_control_legend,
            meas_display_name_override=spec.meas_display_name_override,
            control_display_name_override=spec.control_display_name_override,
            control_label_suffix=spec.control_label_suffix,
            response_legend_prefix=spec.response_legend_prefix,
            single_reference_signal=spec.single_reference_signal,
            reference_signal_label=spec.reference_signal_label,
            reference_signal_color=spec.reference_signal_color,
            response_legend_loc=spec.response_legend_loc,
            response_legend_bbox_anchor=spec.response_legend_bbox_anchor,
            response_legend_ncol=spec.response_legend_ncol,
            response_reference_on_bottom_row=spec.response_reference_on_bottom_row,
            subplot_height_ratios=spec.subplot_height_ratios,
        )
        if not np.isclose(spec.figure_height_scale, 1.0):
            fig_width, fig_height = figure.get_size_inches()
            figure.set_size_inches(
                fig_width,
                fig_height * spec.figure_height_scale,
                forward=True,
            )
        if spec.xlim_sec is not None:
            x_start, x_end = spec.xlim_sec
            for axis in figure.axes:
                axis.set_xlim(x_start, x_end)
        if spec.subplot_adjust is not None:
            figure.subplots_adjust(**dict(spec.subplot_adjust))
        if spec.top_ylim_padding_fraction > 0.0:
            for axis in figure.axes:
                _add_top_ylim_padding(axis, spec.top_ylim_padding_fraction)

        spec_key = spec.output_name
        spec_id = _figure_id_from_output_name(spec.output_name)
        layout_override = layout_overrides.get(spec_key) or layout_overrides.get(
            spec_id
        )
        if isinstance(layout_override, Mapping):
            _apply_layout_overrides(figure, layout_override)

        if args.interactive:
            _show_interactive_editor(figure, output_name=spec.output_name)

        output_path = output_dir / spec.output_name
        if output_path.suffix.lower() != ".pdf":
            output_path = output_path.with_suffix(".pdf")

        figure.canvas.draw()
        captured_layouts[spec_key] = _capture_layout_state(figure)
        figure.savefig(output_path, format="pdf", dpi=300)
        plt.close(figure)
        print(f"Wrote {output_path} ({len(runs)} run(s))")

    layout_output_path = args.write_layout_json
    if layout_output_path is None and args.interactive:
        layout_output_path = output_dir / "figure_specific_step_responses_layout.json"

    if layout_output_path is not None:
        layout_output_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema_version": 1,
            "generated_by": "dashes/figure_specific_step_responses.py",
            "backend": str(matplotlib.get_backend()),
            "figures": captured_layouts,
        }
        layout_output_path.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(f"Wrote layout JSON {layout_output_path}")


if __name__ == "__main__":
    main()
