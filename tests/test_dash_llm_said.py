import csv
from pathlib import Path
from urllib.parse import quote

import numpy as np

from dashes.view_sim_step_responses import (
    CONTROLLER_VIEW_ROUTE,
    KPI_HOVER_KEYS,
    _load_pass_warn_lookups,
    _legend_group_key,
    _llm_said_table,
    _resolve_controller_targets,
    _resolve_best_legend_groups,
    _resolve_dagger_legend_groups,
    build_figure,
    create_app,
    load_runs,
)


def _write_run(path: Path, include_llm_said: bool, why: str = "MotorSpeed.tex final tuned trial.") -> None:
    payload = {
        "setup": "motorspeed_dt",
        "time_sec": np.array([0.0, 0.01]),
        "ref": np.array([1.0, 1.0]),
        "meas": np.array([0.0, 0.5]),
        "control": np.array([0.1, 0.2]),
        "kpis": {
            "settling_time_sec": 1.0,
            "overshoot_pct": 1.0,
            "steady_state_error_pct": 0.2,
        },
    }
    if include_llm_said:
        payload["llm_said"] = {
            "setup": "motorspeed_dt",
            "description": "PID(100,200,10) controller",
            "why": why,
        }
    np.save(path, payload, allow_pickle=True)


def _write_invertedpendulum_run(path: Path) -> None:
    payload = {
        "setup": "invertedpendulum_dt",
        "time_sec": np.array([0.0, 0.01, 0.02]),
        "ref": {
            "x_cart": np.array([0.2, 0.2, 0.2]),
            "phi_angle": np.array([0.0, 0.0, 0.0]),
        },
        "meas": {
            "x_cart": np.array([0.0, 0.04, 0.09]),
            "phi_angle": np.array([0.0, 0.01, 0.005]),
        },
        "control": np.array([1.0, 0.5, 0.2]),
        "kpis": {
            "channels": {
                "x_cart": {
                    "overshoot_pct": 5.0,
                    "rise_time_sec": 0.2,
                    "settling_time_sec": 0.8,
                    "steady_state_error_pct": 1.0,
                    "settled_within_horizon": True,
                    "simulation_horizon_sec": 5.0,
                },
                "phi_angle": {
                    "overshoot_pct": 4.0,
                    "rise_time_sec": 0.1,
                    "settling_time_sec": 0.3,
                    "steady_state_error_pct": 0.5,
                    "max_abs_rad": 0.01,
                    "settled_within_horizon": True,
                    "simulation_horizon_sec": 5.0,
                },
            }
        },
        "llm_said": {
            "setup": "invertedpendulum_dt",
            "description": "Digital LQR",
            "why": "Dict-valued ref/meas trace smoke test for Dash loader.",
        },
    }
    np.save(path, payload, allow_pickle=True)


def _write_three_channel_run(path: Path) -> None:
    payload = {
        "setup": "invertedpendulum_dt",
        "time_sec": np.array([0.0, 0.01, 0.02]),
        "ref": {
            "x_cart": np.array([0.2, 0.2, 0.2]),
            "phi_angle": np.array([0.0, 0.0, 0.0]),
            "z": np.array([1.0, 1.0, 1.0]),
        },
        "meas": {
            "x_cart": np.array([0.0, 0.04, 0.09]),
            "phi_angle": np.array([0.0, 0.01, 0.005]),
            "z": np.array([1.0, 0.8, 0.6]),
        },
        "control": np.array([1.0, 0.5, 0.2]),
        "kpis": {
            "channels": {
                "x_cart": {
                    "overshoot_pct": 5.0,
                    "rise_time_sec": 0.2,
                    "settling_time_sec": 0.8,
                    "steady_state_error_pct": 1.0,
                    "settled_within_horizon": True,
                    "simulation_horizon_sec": 5.0,
                },
                "phi_angle": {
                    "overshoot_pct": 4.0,
                    "rise_time_sec": 0.1,
                    "settling_time_sec": 0.3,
                    "steady_state_error_pct": 0.5,
                    "max_abs_rad": 0.01,
                    "settled_within_horizon": True,
                    "simulation_horizon_sec": 5.0,
                },
            }
        },
        "llm_said": {
            "setup": "invertedpendulum_dt",
            "description": "Digital LQR",
            "why": "Three-channel plotting smoke test.",
        },
    }
    np.save(path, payload, allow_pickle=True)


def _collect_component_ids(component) -> set[str]:
    ids: set[str] = set()
    stack = [component]
    while stack:
        node = stack.pop()
        if node is None:
            continue
        node_id = getattr(node, "id", None)
        if isinstance(node_id, str):
            ids.add(node_id)

        children = getattr(node, "children", None)
        if isinstance(children, (list, tuple)):
            stack.extend(children)
        elif children is not None:
            stack.append(children)
    return ids


def _find_component_by_id(component, target_id: str):
    stack = [component]
    while stack:
        node = stack.pop()
        if node is None:
            continue
        if getattr(node, "id", None) == target_id:
            return node
        children = getattr(node, "children", None)
        if isinstance(children, (list, tuple)):
            stack.extend(children)
        elif children is not None:
            stack.append(children)
    return None


def _write_npy_match_csv(
    current_run_root: Path,
    rows: list[tuple[str, str, str]],
) -> None:
    csv_path = current_run_root / "npy_match.csv"
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["status", "run_path", "controller_path"],
        )
        writer.writeheader()
        for status, run_path, controller_path in rows:
            writer.writerow(
                {
                    "status": status,
                    "run_path": run_path,
                    "controller_path": controller_path,
                }
            )


def _write_best_txt(
    current_run_root: Path,
    setup_name: str,
    experiment_id: str,
    attempt_n: int,
    controller_name: str,
) -> None:
    best_path = (
        current_run_root
        / "wp"
        / setup_name
        / experiment_id
        / f"attempt{attempt_n}"
        / "lwp"
        / "rlwp"
        / "best.txt"
    )
    best_path.parent.mkdir(parents=True, exist_ok=True)
    best_path.write_text(controller_name + "\n", encoding="utf-8")


def _write_controller_file(
    current_run_root: Path,
    setup_name: str,
    experiment_id: str,
    attempt_n: int,
    controller_name: str,
    source: str,
) -> None:
    controller_path = (
        current_run_root
        / "wp"
        / setup_name
        / experiment_id
        / f"attempt{attempt_n}"
        / "lwp"
        / "rlwp"
        / controller_name
    )
    controller_path.parent.mkdir(parents=True, exist_ok=True)
    controller_path.write_text(source, encoding="utf-8")


def _build_best_mapping_fixture(tmp_path: Path) -> Path:
    current_run_root = tmp_path / "current_run"
    sim_folder = current_run_root / "sim"

    attempt0 = sim_folder / "motorspeed_dt" / "exp_a" / "attempt0"
    attempt0.mkdir(parents=True)
    _write_run(
        attempt0 / "run0.npy",
        include_llm_said=True,
        why="Design to meet specifications: baseline candidate.",
    )
    _write_run(
        attempt0 / "run1.npy",
        include_llm_said=True,
        why="Tuning: first tuning pass.",
    )

    attempt1 = sim_folder / "motorspeed_dt" / "exp_a" / "attempt1"
    attempt1.mkdir(parents=True)
    _write_run(
        attempt1 / "run0.npy",
        include_llm_said=True,
        why="Design to meet specifications: no tuning stage here.",
    )

    _write_best_txt(
        current_run_root,
        setup_name="motorspeed_dt",
        experiment_id="exp_a",
        attempt_n=0,
        controller_name="controller_2.py",
    )
    _write_best_txt(
        current_run_root,
        setup_name="motorspeed_dt",
        experiment_id="exp_a",
        attempt_n=1,
        controller_name="controller_1.py",
    )
    _write_controller_file(
        current_run_root,
        setup_name="motorspeed_dt",
        experiment_id="exp_a",
        attempt_n=0,
        controller_name="controller_1.py",
        source="def controller_update(*args, **kwargs):\n    return 0.0\n",
    )
    _write_controller_file(
        current_run_root,
        setup_name="motorspeed_dt",
        experiment_id="exp_a",
        attempt_n=0,
        controller_name="controller_2.py",
        source="def controller_update(*args, **kwargs):\n    return 0.1\n",
    )
    _write_controller_file(
        current_run_root,
        setup_name="motorspeed_dt",
        experiment_id="exp_a",
        attempt_n=1,
        controller_name="controller_1.py",
        source="def controller_update(*args, **kwargs):\n    return -0.2\n",
    )
    _write_npy_match_csv(
        current_run_root,
        rows=[
            (
                "PASS",
                "sim/motorspeed_dt/exp_a/attempt0/run0.npy",
                "wp/motorspeed_dt/exp_a/attempt0/lwp/rlwp/controller_1.py",
            ),
            (
                "WARN",
                "sim/motorspeed_dt/exp_a/attempt0/run1.npy",
                "wp/motorspeed_dt/exp_a/attempt0/lwp/rlwp/controller_2.py",
            ),
            (
                "FAIL",
                "sim/motorspeed_dt/exp_a/attempt1/run0.npy",
                "wp/motorspeed_dt/exp_a/attempt1/lwp/rlwp/controller_1.py",
            ),
        ],
    )
    return sim_folder


def test_load_runs_requires_llm_said(tmp_path):
    base = tmp_path / "motorspeed_dt" / "exp_a" / "attempt0"
    base.mkdir(parents=True)
    _write_run(base / "run0.npy", include_llm_said=True)
    _write_run(base / "run1.npy", include_llm_said=False)

    runs, setups, experiment_ids, attempts, warnings = load_runs(tmp_path)

    assert len(runs) == 1
    assert setups == ["motorspeed_dt"]
    assert experiment_ids == ["exp_a"]
    assert attempts == [0]
    assert any("missing keys ['llm_said']" in msg for msg in warnings)


def test_llm_said_table_only_includes_visible_legend_entries(tmp_path):
    base = tmp_path / "motorspeed_dt" / "exp_a" / "attempt0"
    base.mkdir(parents=True)
    _write_run(base / "run0.npy", include_llm_said=True)
    _write_run(base / "run1.npy", include_llm_said=True)
    runs, *_ = load_runs(tmp_path)
    assert len(runs) == 2

    hidden = {_legend_group_key(runs[1])}
    _, shown_count, filtered = build_figure(
        all_runs=runs,
        selected_setups=["motorspeed_dt"],
        selected_experiment_ids=["exp_a"],
        selected_attempts=[0],
        show_reference=True,
        show_control=False,
        normalize_response=False,
        hidden_groups=hidden,
    )
    table = _llm_said_table(filtered, hidden)

    assert shown_count == 1
    header_row, body = table.children
    assert header_row is not None
    assert len(body.children) == 1


def test_each_run_has_distinct_color(tmp_path):
    base = tmp_path / "motorspeed_dt" / "exp_a" / "attempt0"
    base.mkdir(parents=True)
    _write_run(base / "run0.npy", include_llm_said=True)
    _write_run(base / "run1.npy", include_llm_said=True)
    runs, *_ = load_runs(tmp_path)

    figure, shown_count, _filtered = build_figure(
        all_runs=runs,
        selected_setups=["motorspeed_dt"],
        selected_experiment_ids=["exp_a"],
        selected_attempts=[0],
        show_reference=False,
        show_control=False,
        normalize_response=False,
        hidden_groups=set(),
    )

    assert shown_count == 2
    run_traces = [trace for trace in figure.data if not str(trace.name).endswith(" ref")]
    run_colors = {trace.name: trace.line.color for trace in run_traces}
    assert len(run_colors) == 2
    assert len(set(run_colors.values())) == 2


def test_load_runs_accepts_dict_ref_and_meas_for_invertedpendulum(tmp_path):
    base = tmp_path / "invertedpendulum_dt" / "exp_dict" / "attempt0"
    base.mkdir(parents=True)
    _write_invertedpendulum_run(base / "run0.npy")

    runs, setups, experiment_ids, attempts, warnings = load_runs(tmp_path)

    assert len(runs) == 1
    assert setups == ["invertedpendulum_dt"]
    assert experiment_ids == ["exp_dict"]
    assert attempts == [0]
    assert all("not 1D" not in msg for msg in warnings)

    rec = runs[0]
    assert isinstance(rec.ref, dict)
    assert isinstance(rec.meas, dict)
    assert set(rec.ref) == {"x_cart", "phi_angle"}
    assert set(rec.meas) == {"x_cart", "phi_angle"}

    figure, shown_count, _filtered = build_figure(
        all_runs=runs,
        selected_setups=["invertedpendulum_dt"],
        selected_experiment_ids=["exp_dict"],
        selected_attempts=[0],
        show_reference=True,
        show_control=False,
        normalize_response=False,
        hidden_groups=set(),
    )
    assert shown_count == 1
    legend = _legend_group_key(rec)
    meas_traces = [trace for trace in figure.data if trace.name == legend]
    assert len(meas_traces) == 2
    axis_to_expected = {"y": rec.meas["x_cart"], "y2": rec.meas["phi_angle"]}
    assert {trace.yaxis for trace in meas_traces} == set(axis_to_expected)
    for trace in meas_traces:
        assert np.allclose(np.asarray(trace.y, dtype=float), axis_to_expected[trace.yaxis])

    settling_col = 4 + KPI_HOVER_KEYS.index("settling_time_sec")
    max_abs_col = 4 + KPI_HOVER_KEYS.index("max_abs_rad")
    by_axis = {trace.yaxis: trace for trace in meas_traces}
    x_custom = np.asarray(by_axis["y"].customdata, dtype=object)
    phi_custom = np.asarray(by_axis["y2"].customdata, dtype=object)
    assert x_custom[0, settling_col] == "0.8"
    assert phi_custom[0, settling_col] == "0.3"
    assert x_custom[0, max_abs_col] == "n/a"
    assert phi_custom[0, max_abs_col] == "0.01"


def test_build_figure_plots_more_than_two_channels_on_additional_axes(tmp_path):
    base = tmp_path / "invertedpendulum_dt" / "exp_three" / "attempt1"
    base.mkdir(parents=True)
    _write_three_channel_run(base / "run0.npy")
    runs, *_ = load_runs(tmp_path)
    rec = runs[0]

    figure, shown_count, _filtered = build_figure(
        all_runs=runs,
        selected_setups=["invertedpendulum_dt"],
        selected_experiment_ids=["exp_three"],
        selected_attempts=[1],
        show_reference=True,
        show_control=False,
        normalize_response=False,
        hidden_groups=set(),
    )

    assert shown_count == 1
    legend = _legend_group_key(rec)
    meas_traces = [trace for trace in figure.data if trace.name == legend]
    ref_traces = [trace for trace in figure.data if trace.name == f"{legend} ref"]

    assert len(meas_traces) == 3
    assert len(ref_traces) == 3
    assert {trace.yaxis for trace in meas_traces} == {"y", "y2", "y3"}

    meas_colors = {trace.line.color for trace in meas_traces}
    assert len(meas_colors) == 1

    ref_by_axis = {trace.yaxis: trace for trace in ref_traces}
    for meas_trace in meas_traces:
        assert ref_by_axis[meas_trace.yaxis].line.color == meas_trace.line.color

    assert figure.layout.yaxis.title.font.color != figure.layout.yaxis2.title.font.color
    assert figure.layout.yaxis3 is not None


def test_multichannel_response_uses_y3_when_control_subplot_is_enabled(tmp_path):
    base = tmp_path / "invertedpendulum_dt" / "exp_control" / "attempt0"
    base.mkdir(parents=True)
    _write_invertedpendulum_run(base / "run0.npy")
    runs, *_ = load_runs(tmp_path)
    rec = runs[0]

    figure, shown_count, _filtered = build_figure(
        all_runs=runs,
        selected_setups=["invertedpendulum_dt"],
        selected_experiment_ids=["exp_control"],
        selected_attempts=[0],
        show_reference=False,
        show_control=True,
        normalize_response=False,
        hidden_groups=set(),
    )

    assert shown_count == 1
    legend = _legend_group_key(rec)
    meas_traces = [trace for trace in figure.data if trace.name == legend]
    control_traces = [trace for trace in figure.data if trace.name == f"{legend} u"]

    assert len(meas_traces) == 2
    assert {trace.yaxis for trace in meas_traces} == {"y", "y3"}
    assert len(control_traces) == 1
    assert control_traces[0].yaxis == "y2"
    assert control_traces[0].line.color == meas_traces[0].line.color


def test_create_app_removes_signal_selector(tmp_path):
    base = tmp_path / "motorspeed_dt" / "exp_a" / "attempt0"
    base.mkdir(parents=True)
    _write_run(base / "run0.npy", include_llm_said=True)
    runs, setups, experiment_ids, attempts, warnings = load_runs(tmp_path)

    app = create_app(
        all_runs=runs,
        all_setups=setups,
        all_experiment_ids=experiment_ids,
        all_attempts=attempts,
        warnings=warnings,
    )
    ids = _collect_component_ids(app.layout)

    assert "signal-selector" not in ids
    assert "setup-selector" in ids
    assert "experiment-selector" in ids
    assert "attempt-selector" in ids


def test_create_app_defaults_best_only_checkbox_and_initial_filter(tmp_path):
    sim_folder = _build_best_mapping_fixture(tmp_path)
    runs, setups, experiment_ids, attempts, warnings = load_runs(sim_folder)
    best_legend_groups, _best_warnings = _resolve_best_legend_groups(sim_folder)

    app = create_app(
        all_runs=runs,
        all_setups=setups,
        all_experiment_ids=experiment_ids,
        all_attempts=attempts,
        warnings=warnings,
        best_legend_groups=best_legend_groups,
    )

    display_options = _find_component_by_id(app.layout, "display-options")
    assert display_options is not None
    assert "best_only" in display_options.value
    assert "design_checkpoint_only" not in display_options.value

    graph = _find_component_by_id(app.layout, "step-response-graph")
    assert graph is not None
    run_names = {str(trace.name) for trace in graph.figure.data}
    non_reference_run_names = [name for name in run_names if not name.endswith(" ref")]
    assert all(name.endswith("*") for name in non_reference_run_names)


def test_resolve_best_legend_groups_uses_pass_warn_and_ignores_fail(tmp_path):
    sim_folder = _build_best_mapping_fixture(tmp_path)

    best_legend_groups, warnings = _resolve_best_legend_groups(sim_folder)

    assert best_legend_groups == {"motorspeed_dt/exp_a/attempt0/run1"}
    assert any("without PASS/WARN row" in msg and "attempt1" in msg for msg in warnings)


def test_resolve_dagger_legend_groups_uses_why_phase_boundary(tmp_path):
    sim_folder = _build_best_mapping_fixture(tmp_path)
    runs, *_ = load_runs(sim_folder)

    dagger_legend_groups, warnings = _resolve_dagger_legend_groups(runs)

    assert warnings == []
    assert dagger_legend_groups == {"motorspeed_dt/exp_a/attempt0/run0"}


def test_best_run_star_shows_in_legend_table_and_hover(tmp_path):
    sim_folder = _build_best_mapping_fixture(tmp_path)
    runs, *_ = load_runs(sim_folder)
    best_legend_groups, _warnings = _resolve_best_legend_groups(sim_folder)

    figure, shown_count, filtered = build_figure(
        all_runs=runs,
        selected_setups=["motorspeed_dt"],
        selected_experiment_ids=["exp_a"],
        selected_attempts=[0],
        show_reference=False,
        show_control=False,
        normalize_response=False,
        best_legend_groups=best_legend_groups,
        hidden_groups=set(),
    )
    assert shown_count == 2

    run_names = {str(trace.name) for trace in figure.data}
    assert "motorspeed_dt/exp_a/attempt0/run0" in run_names
    assert "motorspeed_dt/exp_a/attempt0/run1*" in run_names

    starred_trace = next(trace for trace in figure.data if str(trace.name).endswith("*"))
    plain_trace = next(trace for trace in figure.data if not str(trace.name).endswith("*"))
    starred_customdata = np.asarray(starred_trace.customdata, dtype=object)
    plain_customdata = np.asarray(plain_trace.customdata, dtype=object)
    assert starred_customdata[0, -1] == " (🏆 best)"
    assert plain_customdata[0, -1] == ""

    table = _llm_said_table(filtered, hidden_groups=set(), best_legend_groups=best_legend_groups)
    body_rows = table.children[1].children
    legends = {row.children[0].children for row in body_rows}
    assert "motorspeed_dt/exp_a/attempt0/run1*" in legends
    assert "motorspeed_dt/exp_a/attempt0/run0" in legends


def test_best_run_star_shows_in_short_legend_mode(tmp_path):
    sim_folder = _build_best_mapping_fixture(tmp_path)
    runs, *_ = load_runs(sim_folder)
    best_legend_groups, _warnings = _resolve_best_legend_groups(sim_folder)

    figure, shown_count, _filtered = build_figure(
        all_runs=runs,
        selected_setups=["motorspeed_dt"],
        selected_experiment_ids=["exp_a"],
        selected_attempts=[0],
        show_reference=False,
        show_control=False,
        normalize_response=False,
        short_legend=True,
        best_legend_groups=best_legend_groups,
        hidden_groups=set(),
    )
    assert shown_count == 2

    run_names = {str(trace.name) for trace in figure.data}
    assert "Iteration 1" in run_names
    assert "Iteration 2*" in run_names


def test_build_figure_best_only_filter_shows_only_starred_runs(tmp_path):
    sim_folder = _build_best_mapping_fixture(tmp_path)
    runs, *_ = load_runs(sim_folder)
    best_legend_groups, _warnings = _resolve_best_legend_groups(sim_folder)

    figure, shown_count, _filtered = build_figure(
        all_runs=runs,
        selected_setups=["motorspeed_dt"],
        selected_experiment_ids=["exp_a"],
        selected_attempts=[0],
        show_reference=False,
        show_control=False,
        normalize_response=False,
        show_best_only=True,
        best_legend_groups=best_legend_groups,
        hidden_groups=set(),
    )
    assert shown_count == 1
    run_names = {str(trace.name) for trace in figure.data}
    assert "motorspeed_dt/exp_a/attempt0/run1*" in run_names
    assert "motorspeed_dt/exp_a/attempt0/run0" not in run_names


def test_dagger_run_shows_in_legend_table_and_hover(tmp_path):
    sim_folder = _build_best_mapping_fixture(tmp_path)
    runs, *_ = load_runs(sim_folder)
    dagger_legend_groups, _warnings = _resolve_dagger_legend_groups(runs)

    figure, shown_count, filtered = build_figure(
        all_runs=runs,
        selected_setups=["motorspeed_dt"],
        selected_experiment_ids=["exp_a"],
        selected_attempts=[0],
        show_reference=False,
        show_control=False,
        normalize_response=False,
        dagger_legend_groups=dagger_legend_groups,
        hidden_groups=set(),
    )
    assert shown_count == 2

    run_names = {str(trace.name) for trace in figure.data}
    assert "motorspeed_dt/exp_a/attempt0/run0†" in run_names
    assert "motorspeed_dt/exp_a/attempt0/run1" in run_names

    dagger_trace = next(trace for trace in figure.data if str(trace.name).endswith("†"))
    plain_trace = next(
        trace
        for trace in figure.data
        if str(trace.name) == "motorspeed_dt/exp_a/attempt0/run1"
    )
    dagger_customdata = np.asarray(dagger_trace.customdata, dtype=object)
    plain_customdata = np.asarray(plain_trace.customdata, dtype=object)
    assert dagger_customdata[0, -1] == " (⛳ design checkpoint)"
    assert plain_customdata[0, -1] == ""

    table = _llm_said_table(
        filtered,
        hidden_groups=set(),
        dagger_legend_groups=dagger_legend_groups,
    )
    body_rows = table.children[1].children
    legends = {row.children[0].children for row in body_rows}
    assert "motorspeed_dt/exp_a/attempt0/run0†" in legends
    assert "motorspeed_dt/exp_a/attempt0/run1" in legends


def test_build_figure_design_checkpoint_filter_shows_only_dagger_runs(tmp_path):
    sim_folder = _build_best_mapping_fixture(tmp_path)
    runs, *_ = load_runs(sim_folder)
    dagger_legend_groups, _warnings = _resolve_dagger_legend_groups(runs)

    figure, shown_count, _filtered = build_figure(
        all_runs=runs,
        selected_setups=["motorspeed_dt"],
        selected_experiment_ids=["exp_a"],
        selected_attempts=[0],
        show_reference=False,
        show_control=False,
        normalize_response=False,
        show_design_checkpoint_only=True,
        dagger_legend_groups=dagger_legend_groups,
        hidden_groups=set(),
    )
    assert shown_count == 1
    run_names = {str(trace.name) for trace in figure.data}
    assert "motorspeed_dt/exp_a/attempt0/run0†" in run_names
    assert "motorspeed_dt/exp_a/attempt0/run1" not in run_names


def test_build_figure_best_and_dagger_filters_union_when_both_enabled(tmp_path):
    sim_folder = _build_best_mapping_fixture(tmp_path)
    runs, *_ = load_runs(sim_folder)
    best_group = "motorspeed_dt/exp_a/attempt0/run1"
    dagger_group = "motorspeed_dt/exp_a/attempt0/run0"

    figure, shown_count, _filtered = build_figure(
        all_runs=runs,
        selected_setups=["motorspeed_dt"],
        selected_experiment_ids=["exp_a"],
        selected_attempts=[0],
        show_reference=False,
        show_control=False,
        normalize_response=False,
        show_best_only=True,
        show_design_checkpoint_only=True,
        best_legend_groups={best_group},
        dagger_legend_groups={dagger_group},
        hidden_groups=set(),
    )
    assert shown_count == 2

    run_names = {str(trace.name) for trace in figure.data}
    assert "motorspeed_dt/exp_a/attempt0/run1*" in run_names
    assert "motorspeed_dt/exp_a/attempt0/run0†" in run_names


def test_llm_said_table_controller_links_and_view_route(tmp_path):
    sim_folder = _build_best_mapping_fixture(tmp_path)
    runs, setups, experiment_ids, attempts, warnings = load_runs(sim_folder)
    current_run_folder = sim_folder.parent
    controller_to_run, run_to_controller, _lookup_warnings = _load_pass_warn_lookups(
        current_run_folder
    )
    controller_paths_by_legend, controller_names_by_legend, _controller_warnings = (
        _resolve_controller_targets(current_run_folder, run_to_controller)
    )
    best_legend_groups, _best_warnings = _resolve_best_legend_groups(
        current_run_folder,
        controller_to_run,
    )

    table = _llm_said_table(
        runs,
        hidden_groups=set(),
        best_legend_groups=best_legend_groups,
        controller_names_by_legend=controller_names_by_legend,
    )
    body_rows = table.children[1].children
    run1_row = next(
        row
        for row in body_rows
        if str(row.children[0].children).startswith("motorspeed_dt/exp_a/attempt0/run1")
    )
    controller_link = run1_row.children[1].children
    assert controller_link.children == "controller_2.py"
    assert controller_link.target == "_blank"
    assert controller_link.href.startswith(f"{CONTROLLER_VIEW_ROUTE}?legend=")
    assert run1_row.children[3].children == "4.0"

    app = create_app(
        all_runs=runs,
        all_setups=setups,
        all_experiment_ids=experiment_ids,
        all_attempts=attempts,
        warnings=warnings,
        best_legend_groups=best_legend_groups,
        current_run_folder=current_run_folder,
        controller_paths_by_legend=controller_paths_by_legend,
        controller_names_by_legend=controller_names_by_legend,
    )
    client = app.server.test_client()
    response = client.get(
        f"{CONTROLLER_VIEW_ROUTE}?legend="
        f"{quote('motorspeed_dt/exp_a/attempt0/run1', safe='')}"
    )
    assert response.status_code == 200
    assert response.mimetype == "text/plain"
    body = response.get_data(as_text=True)
    assert "def controller_update" in body
    assert "return 0.1" in body
