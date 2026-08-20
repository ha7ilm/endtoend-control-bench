#!/usr/bin/env python3
"""Generate cumulative-feasible-minimum objective figure across setups.

Usage:
    python dashes/figure_cumulative_minimums.py \
        [--prompt customctlchoice] \
        [--folder results/current_run]
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import plotly.graph_objects as go
from plotly.colors import qualitative
from plotly.subplots import make_subplots

try:
    # Import path when executed as module from project root.
    from dashes.parse_kpis import (
        compute_objective,
        explain_constraints,
        format_objective,
        meets_design_spec,
    )
except ModuleNotFoundError:  # pragma: no cover - runtime convenience for direct script execution
    # Import path when executed as: python dashes/figure_cumulative_minimums.py
    from parse_kpis import (  # type: ignore
        compute_objective,
        explain_constraints,
        format_objective,
        meets_design_spec,
    )


def _configure_matplotlib_backend() -> str:
    """Pick an interactive backend when --interactive is in argv, otherwise Agg."""
    mpl_config_dir = Path(os.environ.get("MPLCONFIGDIR", "/tmp/matplotlib"))
    mpl_config_dir.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("MPLCONFIGDIR", str(mpl_config_dir))

    import matplotlib

    matplotlib.rcParams["pdf.fonttype"] = 42
    matplotlib.rcParams["ps.fonttype"] = 42

    if "--interactive" not in set(sys.argv[1:]):
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


_MPL_BACKEND = _configure_matplotlib_backend()

RUN_FILE_PATTERN = re.compile(r"run(\d+)\.npy$")
ATTEMPT_DIR_PATTERN = re.compile(r"attempt(\d+)$")

# Fixed 5x2 panel layout requested by analysis consumers.
SUBPLOT_GRID: tuple[tuple[str | None, str | None], ...] = (
    ("ballandbeam_dt", "ballandbeam_dt_nl_act_mg996r"),
    ("cruisecontrol_dt", "cruisecontrol_dt_lim_hondajazz"),
    ("invertedpendulum_dt", "invertedpendulum_dt_nl_lim_quanserip02"),
    ("motorspeed_dt", "motorspeed_dt_lim_maxonre30"),
    ("aircraftpitch_dt", None),
)

FALLBACK_MODEL_COLORS = (
    qualitative.Plotly
    + qualitative.D3
    + qualitative.G10
    + qualitative.Set2
    + qualitative.Safe
)

FIGURE_H1 = "Cumulative Feasible Minimum Objective"
FIGURE_CAPTION = (
    "Figure. Cumulative feasible minimum objective versus tuning iteration, shown per "
    "attempt for each setup variant. Curves report the running best objective among "
    "feasible controllers only. Infeasible iterations do not improve the running minimum."
)

PDF_SUBPLOT_HEIGHT_IN = 1.3
PDF_WIDTH_IN = 3.45
PDF_TITLE_FONTSIZE = 6.9
PDF_AXIS_LABEL_FONTSIZE = 7.2
PDF_TICK_FONTSIZE = 5.9
PDF_BASE_HSPACE = 0.26
PDF_EXTRA_VSPACE_PX = 4.0
PDF_PIXEL_DPI_REF = 96.0
TITLE_BORDER_WIDTH_PX = 1
TITLE_DOWNWARD_SHIFT_PX = 5
PDF_EDGE_LABEL_FONTSIZE = 5.9
PDF_EDGE_LABEL_X_AXES = 1.01

PDF_SPECIAL_EDGE_LABEL_SETUPS = {
    "invertedpendulum_dt_nl_lim_quanserip02",
    "ballandbeam_dt_nl_act_mg996r",
    "cruisecontrol_dt_lim_hondajazz",
    "invertedpendulum_dt",
}

PDF_HIDE_YTICK_LABELS_SETUPS = {
    "cruisecontrol_dt_lim_hondajazz",
    "invertedpendulum_dt_nl_lim_quanserip02",
    "ballandbeam_dt_nl_act_mg996r",
}

PDF_HIDE_YTICK_MARKS_SETUPS = {
    "cruisecontrol_dt_lim_hondajazz",
    "invertedpendulum_dt_nl_lim_quanserip02",
    "ballandbeam_dt_nl_act_mg996r",
}


@dataclass(frozen=True)
class RunEvaluation:
    iteration: int
    objective: float
    feasible: bool
    constraints: list[tuple[str, float, float, bool]]


def _load_json(path: Path) -> Any:
    with open(path) as f:
        return json.load(f)


def _attempt_sort_key(attempt_name: str) -> tuple[int, int, str]:
    m = ATTEMPT_DIR_PATTERN.match(attempt_name)
    if m:
        return (0, int(m.group(1)), attempt_name)
    return (1, 0, attempt_name)


def _run_sort_key(run_path: Path) -> tuple[int, int, str]:
    m = RUN_FILE_PATTERN.match(run_path.name)
    if m:
        return (0, int(m.group(1)), run_path.name)
    return (1, 0, run_path.name)


def _model_label(model_id: str, models: dict[str, dict]) -> str:
    entry = models.get(model_id)
    if isinstance(entry, dict):
        short_name = entry.get("short_name")
        if isinstance(short_name, str) and short_name.strip():
            return short_name.strip()
    return model_id


def _setup_label(setup_name: str, setups: dict[str, dict]) -> str:
    key = f"{setup_name}.md"
    entry = setups.get(key)
    if isinstance(entry, dict):
        short_name = entry.get("short_name")
        if isinstance(short_name, str) and short_name.strip():
            return short_name.strip()
    return setup_name


def resolve_model_colors(model_ids: set[str], models: dict[str, dict]) -> dict[str, str]:
    """Resolve model colors from map_models.json, using deterministic fallbacks."""
    used: set[str] = set()
    resolved: dict[str, str] = {}
    fallback_index = 0

    for model_id in sorted(model_ids):
        entry = models.get(model_id)
        if isinstance(entry, dict):
            color = entry.get("color")
            if isinstance(color, str) and color.strip():
                normalized = color.strip()
                resolved[model_id] = normalized
                used.add(normalized)
                continue

        while fallback_index < len(FALLBACK_MODEL_COLORS):
            candidate = FALLBACK_MODEL_COLORS[fallback_index]
            fallback_index += 1
            if candidate not in used:
                resolved[model_id] = candidate
                used.add(candidate)
                break
        else:
            # In practice we will not exhaust, but keep behavior deterministic.
            resolved[model_id] = FALLBACK_MODEL_COLORS[(fallback_index - 1) % len(FALLBACK_MODEL_COLORS)]

    return resolved


def _load_kpis(run_path: Path) -> dict[str, Any] | None:
    try:
        payload = np.load(run_path, allow_pickle=True).item()
    except Exception as exc:  # pragma: no cover - defensive branch
        print(f"WARNING: failed to load {run_path}: {exc}", file=sys.stderr)
        return None

    if not isinstance(payload, dict):
        print(f"WARNING: skipped {run_path}: payload is not a dict", file=sys.stderr)
        return None

    kpis = payload.get("kpis")
    if not isinstance(kpis, dict):
        print(f"WARNING: skipped {run_path}: missing dict-valued 'kpis'", file=sys.stderr)
        return None
    return kpis


def collect_attempt_series(
    folder: Path,
    prompt: str,
) -> dict[str, dict[str, dict[str, list[RunEvaluation]]]]:
    """Collect per-run objective and feasibility details by setup/model/attempt."""
    sim_dir = folder / "sim"
    target_setups = {
        setup_name
        for row in SUBPLOT_GRID
        for setup_name in row
        if setup_name is not None
    }
    collected: dict[str, dict[str, dict[str, list[RunEvaluation]]]] = {}

    for setup_name in sorted(target_setups):
        setup_dir = sim_dir / setup_name
        if not setup_dir.exists():
            continue

        for case_dir in sorted(p for p in setup_dir.iterdir() if p.is_dir()):
            case_name = case_dir.name
            prefix = prompt + "_"
            if not case_name.startswith(prefix):
                continue
            model_id = case_name[len(prefix):]

            attempt_dirs = sorted(
                (p for p in case_dir.iterdir() if p.is_dir()),
                key=lambda p: _attempt_sort_key(p.name),
            )
            for attempt_dir in attempt_dirs:
                run_files = sorted(
                    (p for p in attempt_dir.iterdir() if p.is_file()),
                    key=_run_sort_key,
                )

                evaluations: list[RunEvaluation] = []
                for run_path in run_files:
                    run_match = RUN_FILE_PATTERN.match(run_path.name)
                    if run_match is None:
                        continue
                    run_index = int(run_match.group(1))
                    iteration = run_index + 1

                    kpis = _load_kpis(run_path)
                    if kpis is None:
                        continue

                    try:
                        objective = compute_objective(setup_name, kpis)
                        feasible = meets_design_spec(setup_name, kpis)
                        constraints = explain_constraints(setup_name, kpis)
                    except (TypeError, ValueError) as exc:
                        print(f"WARNING: skipped {run_path}: {exc}", file=sys.stderr)
                        continue

                    evaluations.append(
                        RunEvaluation(
                            iteration=iteration,
                            objective=objective,
                            feasible=feasible,
                            constraints=constraints,
                        )
                    )

                if not evaluations:
                    continue

                collected.setdefault(setup_name, {}).setdefault(model_id, {})[attempt_dir.name] = evaluations

    return collected


def cumulative_feasible_minimum(points: list[RunEvaluation]) -> list[float | None]:
    """Compute running min objective where only feasible runs can improve the best."""
    running_best = float("inf")
    result: list[float | None] = []
    for point in sorted(points, key=lambda p: p.iteration):
        if point.feasible and math.isfinite(point.objective) and point.objective < running_best:
            running_best = point.objective
        if math.isfinite(running_best):
            result.append(running_best)
        else:
            result.append(None)
    return result


def _format_metric(value: float) -> str:
    if math.isnan(value):
        return "NaN"
    if math.isinf(value):
        return "inf"
    return f"{value:.6g}"


def build_hover_text(
    setup_name: str,
    model_label: str,
    attempt_name: str,
    point: RunEvaluation,
    cumulative_value: float | None,
) -> str:
    """Build rich hover text containing objective, constraints, and feasibility."""
    objective_text = format_objective(point.objective)
    cumulative_text = "n/a" if cumulative_value is None else format_objective(cumulative_value)

    lines = [
        f"<b>{setup_name} / {model_label} / {attempt_name}</b>",
        f"Iteration: {point.iteration}",
        f"Objective: {objective_text}",
        f"Cumulative feasible minimum: {cumulative_text}",
        f"KPIs feasible: {point.feasible}",
        "Constraints:",
    ]
    for desc, actual, _limit, passed in point.constraints:
        lines.append(
            f"{desc}; actual={_format_metric(actual)}; {'PASS' if passed else 'FAIL'}"
        )
    return "<br>".join(lines)


def _cumulative_value_for_log(value: float | None) -> float | None:
    if value is None:
        return None
    if not math.isfinite(value):
        return None
    if value <= 0:
        return None
    return value


def _build_model_colors(
    series: dict[str, dict[str, dict[str, list[RunEvaluation]]]],
    models: dict[str, dict],
) -> dict[str, str]:
    model_ids = {
        model_id
        for setup_models in series.values()
        for model_id in setup_models
    }
    return resolve_model_colors(model_ids, models)


def _iter_attempt_curves(
    setup_name: str,
    setup_series: dict[str, dict[str, list[RunEvaluation]]],
    models: dict[str, dict],
    model_colors: dict[str, str],
):
    for model_id in sorted(setup_series):
        model_label = _model_label(model_id, models)
        color = model_colors[model_id]
        attempts = setup_series[model_id]
        for attempt_name in sorted(attempts, key=_attempt_sort_key):
            points = sorted(attempts[attempt_name], key=lambda p: p.iteration)
            cumulative_values = cumulative_feasible_minimum(points)
            x_values = [point.iteration for point in points]
            y_values = [_cumulative_value_for_log(v) for v in cumulative_values]
            if not any(v is not None for v in y_values):
                continue
            hovertext = [
                build_hover_text(
                    setup_name=setup_name,
                    model_label=model_label,
                    attempt_name=attempt_name,
                    point=point,
                    cumulative_value=cumulative_value,
                )
                for point, cumulative_value in zip(points, cumulative_values)
            ]
            yield {
                "model_id": model_id,
                "model_label": model_label,
                "attempt_name": attempt_name,
                "color": color,
                "x_values": x_values,
                "y_values": y_values,
                "hovertext": hovertext,
            }


def _all_setup_names_sorted() -> list[str]:
    """All setup names from SUBPLOT_GRID in alphabetical order (matching tables.py row order)."""
    names: list[str] = []
    for row in SUBPLOT_GRID:
        for setup_name in row:
            if setup_name is not None:
                names.append(setup_name)
    return sorted(names)


def _column_setup_names(column_index: int) -> list[str]:
    names: list[str] = []
    for row in SUBPLOT_GRID:
        setup_name = row[column_index]
        if setup_name is not None:
            names.append(setup_name)
    return names


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


def _style_plotly_subplot_title_annotations(fig: go.Figure) -> None:
    """Style subplot title annotations with a tooltip-like box."""
    for ann in fig.layout.annotations or []:
        # Subplot titles from make_subplots are paper-referenced annotations.
        if (
            getattr(ann, "xref", None) == "paper"
            and getattr(ann, "yref", None) == "paper"
            and isinstance(getattr(ann, "text", None), str)
            and ann.text.strip()
        ):
            ann.bgcolor = "white"
            ann.bordercolor = "black"
            ann.borderwidth = TITLE_BORDER_WIDTH_PX
            ann.borderpad = 2
            ann.yshift = -TITLE_DOWNWARD_SHIFT_PX


def _format_scientific_multiline(value: float) -> str:
    """Format a positive value as 'a·10^N' on two lines using mathtext."""
    if not math.isfinite(value) or value <= 0:
        return ""
    exponent = int(math.floor(math.log10(value)))
    mantissa = value / (10 ** exponent)
    mantissa = round(mantissa, 1)
    if mantissa >= 10.0:
        mantissa = 1.0
        exponent += 1
    return f"${mantissa:g}\\cdot$\n$\\;\\;10^{{{exponent}}}$"


def build_cumulative_minimum_figure(
    series: dict[str, dict[str, dict[str, list[RunEvaluation]]]],
    models: dict[str, dict],
    setups: dict[str, dict],
) -> go.Figure:
    """Build the 5x2 cumulative minimum figure."""
    subplot_titles = [
        (f"<b>{_setup_label(setup_name, setups)}</b>" if setup_name is not None else "")
        for row in SUBPLOT_GRID
        for setup_name in row
    ]
    fig = make_subplots(
        rows=len(SUBPLOT_GRID),
        cols=2,
        subplot_titles=subplot_titles,
        vertical_spacing=0.08,
    )

    model_colors = _build_model_colors(series, models)

    for row_index, (left_setup, right_setup) in enumerate(SUBPLOT_GRID, start=1):
        for col_index, setup_name in enumerate((left_setup, right_setup), start=1):
            fig.update_xaxes(title_text="Iteration", row=row_index, col=col_index)

            if setup_name is None:
                fig.update_xaxes(visible=False, row=row_index, col=col_index)
                fig.update_yaxes(visible=False, row=row_index, col=col_index)
                continue

            fig.update_yaxes(
                type="log",
                title_text="Cum. feas. min. objective.",
                row=row_index,
                col=col_index,
            )

            traces_before = len(fig.data)
            setup_series = series.get(setup_name, {})
            for curve in _iter_attempt_curves(setup_name, setup_series, models, model_colors):
                fig.add_trace(
                    go.Scatter(
                        x=curve["x_values"],
                        y=curve["y_values"],
                        mode="lines",
                        name=f"{curve['model_label']} {curve['attempt_name']}",
                        legendgroup=f"{setup_name}/{curve['model_id']}/{curve['attempt_name']}",
                        line=dict(color=curve["color"], width=1.5),
                        opacity=0.5,
                        hovertext=curve["hovertext"],
                        hovertemplate="%{hovertext}<extra></extra>",
                        showlegend=False,
                        connectgaps=False,
                    ),
                    row=row_index,
                    col=col_index,
                )

            if len(fig.data) == traces_before:
                fig.add_annotation(
                    x=0.5,
                    y=0.5,
                    xref="x domain",
                    yref="y domain",
                    text="No data",
                    showarrow=False,
                    font=dict(color="#666"),
                    row=row_index,
                    col=col_index,
                )

    fig.update_layout(
        template="plotly_white",
        height=1700,
        width=1300,
        hovermode="closest",
        showlegend=False,
        margin=dict(l=80, r=40, t=60, b=60),
    )
    _style_plotly_subplot_title_annotations(fig)
    return fig


def write_column_pdf(
    series: dict[str, dict[str, dict[str, list[RunEvaluation]]]],
    models: dict[str, dict],
    setups: dict[str, dict],
    setup_names: list[str],
    out_path: Path,
    margin_scale: float = 0.8,
    bottom_margin_scale: float | None = None,
    figure_height_in: float | None = None,
    interactive: bool = False,
    subplot_adjust: dict[str, float] | None = None,
    top_ylim_padding: dict[str, float] | None = None,
) -> None:
    """Write a compact one-column PDF with equal per-subplot heights."""
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D
    from matplotlib.ticker import LogFormatterSciNotation, LogLocator, NullFormatter
    from matplotlib.transforms import ScaledTranslation, blended_transform_factory

    model_colors = _build_model_colors(series, models)
    nrows = len(setup_names)
    if nrows == 0:
        raise ValueError("setup_names must not be empty")
    if margin_scale <= 0.0 or margin_scale > 1.0:
        raise ValueError("margin_scale must be in (0, 1]")
    if bottom_margin_scale is None:
        bottom_margin_scale = margin_scale
    if bottom_margin_scale <= 0.0 or bottom_margin_scale > 1.0:
        raise ValueError("bottom_margin_scale must be in (0, 1]")

    fig_height = figure_height_in if figure_height_in is not None else PDF_SUBPLOT_HEIGHT_IN * nrows
    top = 1.0 - (1.0 - 0.975) * margin_scale
    bottom = 0.07 * bottom_margin_scale
    hspace = _hspace_with_extra_pixels(
        nrows=nrows,
        figure_height_in=fig_height,
        top=top,
        bottom=bottom,
        base_hspace=PDF_BASE_HSPACE,
        extra_pixels=PDF_EXTRA_VSPACE_PX,
        pixel_dpi=PDF_PIXEL_DPI_REF,
    )

    fig, axes = plt.subplots(
        nrows=nrows,
        ncols=1,
        figsize=(PDF_WIDTH_IN, fig_height),
        squeeze=False,
    )
    axes_1d = [axes[row_idx][0] for row_idx in range(nrows)]

    # Build one legend entry per model that appears in this column.
    column_model_ids: set[str] = set()
    for setup_name in setup_names:
        setup_series = series.get(setup_name, {})
        column_model_ids.update(setup_series.keys())
    legend_handles: list[Line2D] = []
    for model_id in sorted(column_model_ids):
        color = model_colors.get(model_id, "#444")
        label = _model_label(model_id, models)
        legend_handles.append(
            Line2D([0], [0], color=color, linewidth=1.2, alpha=0.8, label=label)
        )

    for row_idx, (ax, setup_name) in enumerate(zip(axes_1d, setup_names)):
        ax.set_yscale("log")
        title_transform = ax.transAxes + ScaledTranslation(
            0.0,
            -TITLE_DOWNWARD_SHIFT_PX / fig.dpi,
            fig.dpi_scale_trans,
        )
        title_artist = ax.text(
            0.5,
            1.0,
            _setup_label(setup_name, setups),
            transform=title_transform,
            ha="center",
            va="bottom",
            fontsize=PDF_TITLE_FONTSIZE,
            fontweight="bold",
            clip_on=False,
            bbox={
                "facecolor": "white",
                "edgecolor": "black",
                "linewidth": float(TITLE_BORDER_WIDTH_PX),
                "boxstyle": "square,pad=0.18",
            },
        )
        title_artist.set_wrap(True)

        setup_series = series.get(setup_name, {})
        plotted = False
        for curve in _iter_attempt_curves(setup_name, setup_series, models, model_colors):
            y_values = [
                float("nan") if value is None else value
                for value in curve["y_values"]
            ]
            if all(math.isnan(v) for v in y_values):
                continue
            ax.plot(
                curve["x_values"],
                y_values,
                color=curve["color"],
                alpha=0.5,
                linewidth=0.8,
            )
            plotted = True

        if not plotted:
            ax.text(
                0.5,
                0.5,
                "No data",
                transform=ax.transAxes,
                ha="center",
                va="center",
                fontsize=6.5,
                color="#666",
            )

        ax.yaxis.set_major_locator(LogLocator(base=10.0, subs=(1.0,), numticks=10))
        if setup_name in PDF_HIDE_YTICK_LABELS_SETUPS:
            ax.yaxis.set_major_formatter(NullFormatter())
        else:
            ax.yaxis.set_major_formatter(LogFormatterSciNotation(base=10.0, labelOnlyBase=True))
        ax.yaxis.set_minor_locator(
            LogLocator(base=10.0, subs=(2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0), numticks=100)
        )
        ax.yaxis.set_minor_formatter(NullFormatter())
        ax.grid(True, which="major", alpha=0.25, linewidth=0.35)
        ax.grid(True, which="minor", alpha=0.18, linewidth=0.3)
        ax.tick_params(axis="both", labelsize=PDF_TICK_FONTSIZE, length=2)
        ax.yaxis.tick_right()
        ax.yaxis.set_label_position("right")
        if setup_name in PDF_HIDE_YTICK_MARKS_SETUPS:
            ax.tick_params(axis="y", which="major", length=0, right=False, labelleft=False, left=False)
        else:
            ax.tick_params(axis="y", which="major", labelright=True, right=True, labelleft=False, left=False)
        ax.tick_params(axis="y", which="minor", length=0, right=False, left=False)

        if top_ylim_padding and setup_name in top_ylim_padding:
            frac = top_ylim_padding[setup_name]
            y_low, y_high = ax.get_ylim()
            if y_low > 0 and y_high > 0 and frac > 0:
                log_low = math.log10(y_low)
                log_high = math.log10(y_high)
                ax.set_ylim(y_low, 10 ** (log_high + (log_high - log_low) * frac))

        if setup_name in PDF_SPECIAL_EDGE_LABEL_SETUPS:
            y_low, y_high = ax.get_ylim()
            transform = blended_transform_factory(ax.transAxes, ax.transData)
            ax.text(
                PDF_EDGE_LABEL_X_AXES,
                y_low,
                _format_scientific_multiline(y_low),
                transform=transform,
                ha="left",
                va="center",
                fontsize=PDF_EDGE_LABEL_FONTSIZE,
                clip_on=False,
            )
            ax.text(
                PDF_EDGE_LABEL_X_AXES,
                y_high,
                _format_scientific_multiline(y_high),
                transform=transform,
                ha="left",
                va="center",
                fontsize=PDF_EDGE_LABEL_FONTSIZE,
                clip_on=False,
            )
        if row_idx == nrows - 1:
            ax.set_xlabel("Iteration", fontsize=PDF_AXIS_LABEL_FONTSIZE, labelpad=2)
        else:
            ax.set_xlabel("")

        if row_idx == 0 and legend_handles:
            ax.legend(
                handles=legend_handles,
                loc="best",
                frameon=True,
                fontsize=5.8,
                ncol=1,
                borderpad=0.2,
                handlelength=1.2,
                handletextpad=0.4,
                labelspacing=0.2,
            )

    fig.text(
        0.985,
        0.5,
        "Cumulative feasible minimum objective value",
        ha="center",
        va="center",
        rotation=270,
        fontsize=PDF_AXIS_LABEL_FONTSIZE,
    )
    if subplot_adjust is not None:
        fig.subplots_adjust(**subplot_adjust)
    else:
        fig.subplots_adjust(left=0.0, right=0.88, top=top, bottom=bottom, hspace=hspace)
    if interactive:
        manager = getattr(fig.canvas, "manager", None)
        if manager is not None and hasattr(manager, "set_window_title"):
            manager.set_window_title(str(out_path.name))
        print(
            "[interactive] Close the figure window after tuning with toolbar actions.",
            file=sys.stderr,
        )
        plt.show(block=True)
    fig.savefig(out_path, format="pdf", dpi=300)
    plt.close(fig)


def render_html_document(fig: go.Figure) -> str:
    """Render HTML document with heading and caption around a Plotly figure."""
    figure_html = fig.to_html(
        full_html=False,
        include_plotlyjs=True,
        config={"displaylogo": False, "responsive": True},
    )
    return f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>{FIGURE_H1}</title>
  <style>
    body {{ font-family: sans-serif; margin: 1.5rem; }}
    h1 {{ margin: 0 0 0.75rem 0; font-size: 1.7rem; }}
    .caption {{ margin-top: 0.9rem; max-width: 1200px; line-height: 1.4; color: #333; }}
  </style>
</head>
<body>
  <h1>{FIGURE_H1}</h1>
  {figure_html}
  <p class="caption">{FIGURE_CAPTION}</p>
</body>
</html>
"""


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate cumulative minimum objective figure for tuning runs.",
    )
    parser.add_argument(
        "--prompt",
        default="customctlchoice",
        help="Prompt filter used in case folder names (default: customctlchoice).",
    )
    parser.add_argument(
        "--folder",
        default="results/current_run",
        help="Base results folder containing sim/ and analysis_artifacts/ (default: results/current_run).",
    )
    parser.add_argument(
        "--interactive",
        action="store_true",
        default=False,
        help="Open the one-column PDF in an interactive Matplotlib window before saving.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    folder = Path(args.folder)
    prompt = args.prompt

    if args.interactive and _MPL_BACKEND.lower() == "agg":
        print(
            "ERROR: --interactive requested but no interactive Matplotlib backend is available.",
            file=sys.stderr,
        )
        sys.exit(1)

    sim_dir = folder / "sim"
    if not sim_dir.exists():
        print(f"ERROR: {sim_dir} does not exist.", file=sys.stderr)
        sys.exit(1)

    project_root = Path(__file__).resolve().parent.parent
    models = _load_json(project_root / "promptcomp" / "prompt_agent_commands" / "map_models.json")
    setups = _load_json(project_root / "promptcomp" / "prompt_setup_descriptions" / "map_setups.json")

    series = collect_attempt_series(folder=folder, prompt=prompt)
    fig = build_cumulative_minimum_figure(series=series, models=models, setups=setups)

    out_dir = folder / "analysis_artifacts" / "figures"
    out_dir.mkdir(parents=True, exist_ok=True)
    html_path = out_dir / "cumulative_minimums.html"
    html_path.write_text(render_html_document(fig))

    col1_pdf_path = out_dir / "cumulative_minimums_col1.pdf"
    write_column_pdf(
        series=series,
        models=models,
        setups=setups,
        setup_names=_column_setup_names(0),
        out_path=col1_pdf_path,
        margin_scale=0.5,
        bottom_margin_scale=0.6,
    )
    col2_pdf_path = out_dir / "cumulative_minimums_col2.pdf"
    write_column_pdf(
        series=series,
        models=models,
        setups=setups,
        setup_names=_column_setup_names(1),
        out_path=col2_pdf_path,
        margin_scale=0.8,
    )
    onecol_pdf_path = out_dir / "cumulative_minimums_onecol.pdf"
    write_column_pdf(
        series=series,
        models=models,
        setups=setups,
        setup_names=_all_setup_names_sorted(),
        out_path=onecol_pdf_path,
        figure_height_in=15.0 / 2.54,
        interactive=args.interactive,
        subplot_adjust={
            "top": 0.987,
            "bottom": 0.044,
            "left": 0.005,
            "right": 0.89,
            "hspace": 0.819,
            "wspace": 0.2,
        },
        top_ylim_padding={
            "invertedpendulum_dt": 0.2,
            "invertedpendulum_dt_nl_lim_quanserip02": 0.1,
            "cruisecontrol_dt": 0.1,
            "ballandbeam_dt_nl_act_mg996r": 0.1,
            "ballandbeam_dt": 0.1,
        },
    )

    print(f"Wrote {html_path}")
    print(f"Wrote {col1_pdf_path}")
    print(f"Wrote {col2_pdf_path}")
    print(f"Wrote {onecol_pdf_path}")


if __name__ == "__main__":
    main()
