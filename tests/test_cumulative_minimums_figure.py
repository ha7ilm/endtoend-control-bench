"""Tests for dashes/figure_cumulative_minimums.py."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from dashes.figure_cumulative_minimums import (
    RunEvaluation,
    build_cumulative_minimum_figure,
    build_hover_text,
    collect_attempt_series,
    cumulative_feasible_minimum,
)
from dashes.parse_kpis import explain_constraints


def _write_run(path: Path, kpis: dict) -> None:
    payload = {"kpis": kpis}
    np.save(path, payload)


def test_cumulative_minimum_skips_infeasible_improvements():
    points = [
        RunEvaluation(iteration=1, objective=10.0, feasible=True, constraints=[]),
        RunEvaluation(iteration=2, objective=1.0, feasible=False, constraints=[]),
        RunEvaluation(iteration=3, objective=8.0, feasible=True, constraints=[]),
        RunEvaluation(iteration=4, objective=7.5, feasible=True, constraints=[]),
    ]
    assert cumulative_feasible_minimum(points) == [10.0, 10.0, 8.0, 7.5]


def test_collect_attempt_series_maps_run_index_to_one_based_iteration(tmp_path: Path):
    attempt_dir = (
        tmp_path
        / "sim"
        / "motorspeed_dt"
        / "customctlchoice_codex53xhigh"
        / "attempt0"
    )
    attempt_dir.mkdir(parents=True)

    _write_run(
        attempt_dir / "run0.npy",
        {
            "overshoot_pct": 3.0,
            "settling_time_sec": 1.2,
            "steady_state_error_pct": 0.2,
        },
    )
    _write_run(
        attempt_dir / "run2.npy",
        {
            "overshoot_pct": 2.0,
            "settling_time_sec": 1.0,
            "steady_state_error_pct": 0.2,
        },
    )

    series = collect_attempt_series(folder=tmp_path, prompt="customctlchoice")
    evaluations = series["motorspeed_dt"]["codex53xhigh"]["attempt0"]
    assert [ev.iteration for ev in evaluations] == [1, 3]


def test_hover_text_includes_objective_constraints_and_feasibility():
    kpis = {
        "overshoot_pct": 7.0,
        "settling_time_sec": 1.5,
        "steady_state_error_pct": 0.3,
    }
    point = RunEvaluation(
        iteration=2,
        objective=11.5,
        feasible=False,
        constraints=explain_constraints("motorspeed_dt", kpis),
    )
    hover = build_hover_text(
        setup_name="motorspeed_dt",
        model_label="Codex 5.3",
        attempt_name="attempt0",
        point=point,
        cumulative_value=12.0,
    )

    assert "Objective: 11.5" in hover
    assert "KPIs feasible: False" in hover
    assert "settling_time_sec < 2" in hover
    assert "overshoot_pct < 5" in hover
    assert "PASS" in hover
    assert "FAIL" in hover


def test_build_figure_uses_model_colors_alpha_and_blank_empty_panel():
    series = {
        "motorspeed_dt": {
            "codex53xhigh": {
                "attempt0": [
                    RunEvaluation(
                        iteration=1,
                        objective=9.0,
                        feasible=True,
                        constraints=[],
                    )
                ]
            },
            "opus46high": {
                "attempt0": [
                    RunEvaluation(
                        iteration=1,
                        objective=10.0,
                        feasible=True,
                        constraints=[],
                    )
                ]
            },
        }
    }
    models = {
        "codex53xhigh": {"short_name": "Codex 5.3", "color": "red"},
        "opus46high": {"short_name": "Opus 4.6", "color": "blue"},
    }
    setups = {
        "motorspeed_dt.md": {"short_name": "Motor speed CTMS"},
    }
    fig = build_cumulative_minimum_figure(series=series, models=models, setups=setups)

    colors = {trace.line.color for trace in fig.data}
    assert "red" in colors
    assert "blue" in colors
    assert all(trace.opacity == 0.5 for trace in fig.data)
    assert all(trace.mode == "lines" for trace in fig.data)
    assert fig.layout.yaxis.type == "log"
    assert fig.layout.yaxis.title.text == "Cum. feas. min. objective."
    assert not any(
        isinstance(ann.text, str) and "empty subplot" in ann.text
        for ann in fig.layout.annotations
    )
    assert any(
        isinstance(ann.text, str) and "Motor speed CTMS" in ann.text
        for ann in fig.layout.annotations
    )


def test_main_writes_html_output(tmp_path: Path):
    from dashes.figure_cumulative_minimums import main

    attempt_dir = (
        tmp_path
        / "sim"
        / "motorspeed_dt"
        / "customctlchoice_codex53xhigh"
        / "attempt0"
    )
    attempt_dir.mkdir(parents=True)
    _write_run(
        attempt_dir / "run0.npy",
        {
            "overshoot_pct": 2.5,
            "settling_time_sec": 1.1,
            "steady_state_error_pct": 0.2,
        },
    )

    main(["--folder", str(tmp_path), "--prompt", "customctlchoice"])

    out_path = tmp_path / "analysis_artifacts" / "figures" / "cumulative_minimums.html"
    assert out_path.exists()
    html = out_path.read_text()
    assert "<h1>Cumulative Feasible Minimum Objective</h1>" in html
    assert "Figure. Cumulative feasible minimum objective versus tuning iteration" in html
    assert "hover text reports objective" not in html

    col1_pdf = tmp_path / "analysis_artifacts" / "figures" / "cumulative_minimums_col1.pdf"
    col2_pdf = tmp_path / "analysis_artifacts" / "figures" / "cumulative_minimums_col2.pdf"
    assert col1_pdf.exists()
    assert col2_pdf.exists()
