"""Tests for dashes/parse_kpis.py and dashes/tables.py."""

from __future__ import annotations

import csv
import math
import os
import textwrap
from pathlib import Path

import numpy as np
import pytest

from dashes.parse_kpis import (
    compute_objective,
    explain_constraints,
    explain_objective,
    failed_constraints,
    format_objective,
    meets_design_spec,
)


# ---------------------------------------------------------------------------
# meets_design_spec: scalar setup (motorspeed_dt)
# ---------------------------------------------------------------------------

class TestMeetsDesignSpecMotorspeed:
    """Feasibility checks for motorspeed_dt (scalar KPIs)."""

    def test_pass_all_constraints(self):
        kpis = {
            "settling_time_sec": 1.5,
            "overshoot_pct": 3.0,
            "steady_state_error_pct": 0.5,
        }
        assert meets_design_spec("motorspeed_dt", kpis) is True

    def test_fail_settling_time(self):
        kpis = {
            "settling_time_sec": 2.5,  # >= 2
            "overshoot_pct": 3.0,
            "steady_state_error_pct": 0.5,
        }
        assert meets_design_spec("motorspeed_dt", kpis) is False
        violations = failed_constraints("motorspeed_dt", kpis)
        assert "settling_time_sec < 2" in violations

    def test_fail_overshoot(self):
        kpis = {
            "settling_time_sec": 1.0,
            "overshoot_pct": 5.0,  # not < 5 (equal)
            "steady_state_error_pct": 0.5,
        }
        assert meets_design_spec("motorspeed_dt", kpis) is False

    def test_missing_key_is_infeasible(self):
        kpis = {
            "settling_time_sec": 1.0,
            "overshoot_pct": 3.0,
            # missing steady_state_error_pct
        }
        assert meets_design_spec("motorspeed_dt", kpis) is False
        violations = failed_constraints("motorspeed_dt", kpis)
        assert "steady_state_error_pct < 1" in violations

    def test_nan_value_is_infeasible(self):
        kpis = {
            "settling_time_sec": float("nan"),
            "overshoot_pct": 3.0,
            "steady_state_error_pct": 0.5,
        }
        assert meets_design_spec("motorspeed_dt", kpis) is False

    def test_boundary_just_below_passes(self):
        kpis = {
            "settling_time_sec": 1.999,
            "overshoot_pct": 4.999,
            "steady_state_error_pct": 0.999,
        }
        assert meets_design_spec("motorspeed_dt", kpis) is True


# ---------------------------------------------------------------------------
# meets_design_spec: SIMO setup (invertedpendulum_dt)
# ---------------------------------------------------------------------------

class TestMeetsDesignSpecInvertedPendulum:
    """Feasibility checks for invertedpendulum_dt (multi-channel KPIs)."""

    @staticmethod
    def _make_kpis(
        x_st=3.0, x_rt=0.3, x_sse=1.0,
        p_st=3.0, p_max_rad=0.2, p_sse=1.0,
    ):
        return {
            "channels": {
                "x_cart": {
                    "settling_time_sec": x_st,
                    "rise_time_sec": x_rt,
                    "steady_state_error_pct": x_sse,
                },
                "phi_angle": {
                    "settling_time_sec": p_st,
                    "max_abs_rad": p_max_rad,
                    "steady_state_error_pct": p_sse,
                },
            }
        }

    def test_pass_all(self):
        kpis = self._make_kpis()
        assert meets_design_spec("invertedpendulum_dt", kpis) is True

    def test_fail_x_cart_rise_time(self):
        kpis = self._make_kpis(x_rt=0.6)  # >= 0.5
        assert meets_design_spec("invertedpendulum_dt", kpis) is False
        violations = failed_constraints("invertedpendulum_dt", kpis)
        assert any("rise_time_sec" in v for v in violations)

    def test_fail_phi_max_abs_rad(self):
        kpis = self._make_kpis(p_max_rad=0.4)  # >= 0.35
        assert meets_design_spec("invertedpendulum_dt", kpis) is False

    def test_missing_channel_key(self):
        kpis = {
            "channels": {
                "x_cart": {
                    "settling_time_sec": 3.0,
                    "rise_time_sec": 0.3,
                    "steady_state_error_pct": 1.0,
                },
                # missing phi_angle entirely
            }
        }
        assert meets_design_spec("invertedpendulum_dt", kpis) is False
        violations = failed_constraints("invertedpendulum_dt", kpis)
        assert len(violations) >= 3  # at least phi settling, max_abs_rad, sse

    def test_missing_channels_dict(self):
        kpis = {"some_other_key": 42}
        assert meets_design_spec("invertedpendulum_dt", kpis) is False

    def test_realistic_variant_relaxed_rise_time(self):
        """invertedpendulum_dt_nl_lim_quanserip02 has rise_time < 0.8."""
        kpis = self._make_kpis(x_rt=0.6)  # passes realistic (< 0.8), fails CTMS (< 0.5)
        assert meets_design_spec("invertedpendulum_dt_nl_lim_quanserip02", kpis) is True
        assert meets_design_spec("invertedpendulum_dt", kpis) is False


# ---------------------------------------------------------------------------
# compute_objective
# ---------------------------------------------------------------------------

class TestComputeObjective:
    def test_motorspeed_formula(self):
        kpis = {"overshoot_pct": 2.5, "settling_time_sec": 1.2}
        obj = compute_objective("motorspeed_dt", kpis)
        assert obj == pytest.approx(2.5 + 3 * 1.2)

    def test_cruisecontrol_formula(self):
        kpis = {"overshoot_pct": 4.0, "rise_time_sec": 3.0}
        obj = compute_objective("cruisecontrol_dt", kpis)
        assert obj == pytest.approx(4.0 + 2 * 3.0)

    def test_invertedpendulum_formula(self):
        kpis = {
            "channels": {
                "x_cart": {"settling_time_sec": 2.0, "steady_state_error_pct": 0.5},
                "phi_angle": {"settling_time_sec": 1.5, "steady_state_error_pct": 0.3},
            }
        }
        expected = 2.0 + 2 * 0.5 + 1.5 + 2 * 0.3
        obj = compute_objective("invertedpendulum_dt", kpis)
        assert obj == pytest.approx(expected)

    def test_missing_key_returns_inf(self):
        kpis = {"overshoot_pct": 2.5}  # missing settling_time_sec
        assert compute_objective("motorspeed_dt", kpis) == float("inf")

    def test_unknown_setup_raises(self):
        with pytest.raises(ValueError, match="Unknown setup"):
            compute_objective("nonexistent_setup", {})

    def test_non_dict_kpis_raises(self):
        with pytest.raises(TypeError):
            compute_objective("motorspeed_dt", "not a dict")


# ---------------------------------------------------------------------------
# format_objective
# ---------------------------------------------------------------------------

class TestFormatObjective:
    def test_less_than_1(self):
        assert format_objective(0.12345) == "0.1235"

    def test_less_than_1_trailing_zeros(self):
        assert format_objective(0.1) == "0.1"

    def test_between_1_and_10(self):
        assert format_objective(5.678) == "5.678"

    def test_between_1_and_10_trailing_zeros(self):
        assert format_objective(3.0) == "3.0"

    def test_between_10_and_100(self):
        assert format_objective(42.567) == "42.57"

    def test_above_100(self):
        assert format_objective(123.456) == "123.5"

    def test_zero(self):
        assert format_objective(0.0) == "0.0"

    def test_inf(self):
        assert format_objective(float("inf")) == "inf"

    def test_precision_snapshot_small(self):
        assert format_objective(0.0001) == "0.0001"

    def test_precision_snapshot_medium(self):
        assert format_objective(15.1) == "15.1"


# ---------------------------------------------------------------------------
# explain_constraints
# ---------------------------------------------------------------------------

class TestExplainConstraints:
    """Detailed constraint result tuples for transparency."""

    def test_scalar_all_pass(self):
        kpis = {"settling_time_sec": 1.5, "overshoot_pct": 3.0, "steady_state_error_pct": 0.5}
        results = explain_constraints("motorspeed_dt", kpis)
        assert len(results) == 3
        assert all(passed for _, _, _, passed in results)

    def test_scalar_one_fail(self):
        kpis = {"settling_time_sec": 2.5, "overshoot_pct": 3.0, "steady_state_error_pct": 0.5}
        results = explain_constraints("motorspeed_dt", kpis)
        settling = [r for r in results if "settling" in r[0]]
        assert len(settling) == 1
        desc, actual, limit, passed = settling[0]
        assert actual == 2.5
        assert limit == 2
        assert passed is False

    def test_multichannel(self):
        kpis = TestMeetsDesignSpecInvertedPendulum._make_kpis()
        results = explain_constraints("invertedpendulum_dt", kpis)
        assert all(passed for _, _, _, passed in results)
        descs = [r[0] for r in results]
        assert any("x_cart" in d for d in descs)
        assert any("phi_angle" in d for d in descs)

    def test_missing_key_nan(self):
        kpis = {"settling_time_sec": 1.0, "overshoot_pct": 3.0}
        results = explain_constraints("motorspeed_dt", kpis)
        sse = [r for r in results if "steady_state_error" in r[0]]
        assert len(sse) == 1
        _desc, actual, _limit, passed = sse[0]
        assert math.isnan(actual)
        assert passed is False


# ---------------------------------------------------------------------------
# explain_objective
# ---------------------------------------------------------------------------

class TestExplainObjective:
    """Objective formula breakdown for transparency."""

    def test_motorspeed_terms(self):
        kpis = {"overshoot_pct": 2.5, "settling_time_sec": 1.2}
        terms, total = explain_objective("motorspeed_dt", kpis)
        assert len(terms) == 2
        assert terms[0] == ("overshoot_pct", 2.5, 1.0)
        assert terms[1] == ("settling_time_sec", 1.2, 3.0)
        assert total == pytest.approx(2.5 + 3 * 1.2)

    def test_cruisecontrol_terms(self):
        kpis = {"overshoot_pct": 4.0, "rise_time_sec": 3.0}
        terms, total = explain_objective("cruisecontrol_dt", kpis)
        assert len(terms) == 2
        assert terms[0] == ("overshoot_pct", 4.0, 1.0)
        assert terms[1] == ("rise_time_sec", 3.0, 2.0)
        assert total == pytest.approx(4.0 + 2 * 3.0)

    def test_invertedpendulum_terms(self):
        kpis = {
            "channels": {
                "x_cart": {"settling_time_sec": 2.0, "steady_state_error_pct": 0.5},
                "phi_angle": {"settling_time_sec": 1.5, "steady_state_error_pct": 0.3},
            }
        }
        terms, total = explain_objective("invertedpendulum_dt", kpis)
        assert len(terms) == 4
        assert total == pytest.approx(2.0 + 2 * 0.5 + 1.5 + 2 * 0.3)


# ---------------------------------------------------------------------------
# tables.py integration: synthetic mini tree
# ---------------------------------------------------------------------------

class TestTablesIntegration:
    """Integration test using a synthetic result tree."""

    @pytest.fixture()
    def mini_tree(self, tmp_path):
        """Create a minimal results folder structure for two models, one setup, one prompt."""
        folder = tmp_path / "results"
        prompt = "customctlchoice"
        setup = "motorspeed_dt"
        models = {"modelA": {}, "modelB": {}}

        # Write map_models.json and map_setups.json at project root relative location
        project_root = tmp_path / "project"
        project_root.mkdir()
        (project_root / "promptcomp" / "prompt_agent_commands").mkdir(parents=True)
        (project_root / "promptcomp" / "prompt_setup_descriptions").mkdir(parents=True)

        import json
        (project_root / "promptcomp" / "prompt_agent_commands" / "map_models.json").write_text(
            json.dumps({"modelA": {"short_name": "Model A"}, "modelB": {"short_name": "Model B"}})
        )
        (project_root / "promptcomp" / "prompt_setup_descriptions" / "map_setups.json").write_text(
            json.dumps({"motorspeed_dt.md": {"short_name": "Motor speed CTMS"}})
        )

        # Build npy_match rows
        npy_rows = []

        for model_id in ["modelA", "modelB"]:
            for attempt_idx in range(3):
                attempt = f"attempt{attempt_idx}"
                case = f"{prompt}_{model_id}"

                # sim dir with one run file
                sim_attempt = folder / "sim" / setup / case / attempt
                sim_attempt.mkdir(parents=True)

                # wp dir with best.txt and controller
                wp_rlwp = folder / "wp" / setup / case / attempt / "lwp" / "rlwp"
                wp_rlwp.mkdir(parents=True)

                # Choose controller number and feasibility
                ctrl_num = attempt_idx + 1
                best_name = f"controller_{ctrl_num}.py"
                (wp_rlwp / "best.txt").write_text(best_name + "\n")
                (wp_rlwp / best_name).write_text("# placeholder")

                run_idx = ctrl_num - 1
                run_name = f"run{run_idx}.npy"

                # Create KPIs: modelA feasible, modelB attempt2 infeasible
                if model_id == "modelB" and attempt_idx == 2:
                    kpis = {"settling_time_sec": 3.0, "overshoot_pct": 2.0, "steady_state_error_pct": 0.5}
                elif model_id == "modelA":
                    # varying objectives
                    kpis = {
                        "settling_time_sec": 1.0 + attempt_idx * 0.1,
                        "overshoot_pct": 1.0 + attempt_idx * 0.5,
                        "steady_state_error_pct": 0.2,
                    }
                else:
                    kpis = {
                        "settling_time_sec": 1.5 - attempt_idx * 0.1,
                        "overshoot_pct": 2.0 - attempt_idx * 0.3,
                        "steady_state_error_pct": 0.3,
                    }

                run_data = {
                    "setup": setup,
                    "time_sec": np.array([0.0, 0.1, 0.2]),
                    "ref": np.array([1.0, 1.0, 1.0]),
                    "meas": np.array([0.0, 0.5, 1.0]),
                    "control": np.array([1.0, 0.5, 0.1]),
                    "disturbance": np.array([0.0, 0.0, 0.0]),
                    "llm_said": {"setup": setup, "description": "test", "why": "test"},
                    "kpis": kpis,
                }
                np.save(sim_attempt / run_name, run_data)

                run_rel = f"sim/{setup}/{case}/{attempt}/{run_name}"
                ctrl_rel = f"wp/{setup}/{case}/{attempt}/lwp/rlwp/{best_name}"
                npy_rows.append(("PASS", run_rel, ctrl_rel))

        # Write npy_match.csv
        csv_path = folder / "npy_match.csv"
        with open(csv_path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["status", "run_path", "controller_path", "note", "npy_why", "py_why", "npy_description", "py_description"])
            for status, run_path, ctrl_path in npy_rows:
                writer.writerow([status, run_path, ctrl_path, "", "", "", "", ""])

        return folder, project_root, prompt

    def test_controller_techniques_loaded_from_selected_run(self, mini_tree):
        """The optional techniques CSV is resolved relative to --folder."""
        folder, _project_root, _prompt = mini_tree
        (folder / "list_of_all_controllers.csv").write_text(
            "setup,model,control techniques applied (as claimed by the agent)\n"
            'motorspeed_dt,modelA,"PI, 2-DOF PI"\n'
        )

        from dashes.tables import _load_controller_techniques

        techniques = _load_controller_techniques(folder)

        assert techniques == {"motorspeed_dt": {"modelA": "PI, 2-DOF PI"}}

    def test_controller_techniques_file_is_optional(self, mini_tree, capsys):
        """A selected run without the CSV still loads with empty technique data."""
        folder, _project_root, _prompt = mini_tree

        from dashes.tables import _load_controller_techniques

        assert _load_controller_techniques(folder) == {}
        assert f"optional {folder / 'list_of_all_controllers.csv'} not found" in capsys.readouterr().err

    def test_success_rate_numerator_denominator(self, mini_tree):
        folder, project_root, prompt = mini_tree
        from dashes.tables import _load_npy_match, _discover_attempts, _build_success_rates, _load_json

        models = _load_json(project_root / "promptcomp" / "prompt_agent_commands" / "map_models.json")
        setups = _load_json(project_root / "promptcomp" / "prompt_setup_descriptions" / "map_setups.json")
        npy_match = _load_npy_match(folder)
        attempts_map = _discover_attempts(folder, prompt)

        rates, _constraint_bg = _build_success_rates(folder, prompt, attempts_map, models, setups, npy_match)

        # modelA: all 3 feasible
        assert rates["motorspeed_dt"]["modelA"] == (3, 3)
        # modelB: 2 feasible, 1 infeasible (attempt2 has settling_time=3.0 >= 2)
        assert rates["motorspeed_dt"]["modelB"] == (2, 3)

    def test_exclusion_list_content(self, mini_tree):
        folder, project_root, prompt = mini_tree
        from dashes.tables import _load_npy_match, _discover_attempts, _build_comparison_data, _load_json

        models = _load_json(project_root / "promptcomp" / "prompt_agent_commands" / "map_models.json")
        setups = _load_json(project_root / "promptcomp" / "prompt_setup_descriptions" / "map_setups.json")
        npy_match = _load_npy_match(folder)
        attempts_map = _discover_attempts(folder, prompt)

        _comparison, excluded, _obj_bg = _build_comparison_data(folder, prompt, attempts_map, models, setups, npy_match)

        # modelB/attempt2 should be excluded as infeasible
        assert len(excluded) == 1
        ex = excluded[0]
        assert ex.model == "modelB"
        assert ex.attempt == "attempt2"
        assert "infeasible" in ex.reason

    def test_green_highlight_on_better_objective(self, mini_tree):
        folder, project_root, prompt = mini_tree
        from dashes.tables import (
            _load_npy_match, _discover_attempts, _build_comparison_data,
            _render_which_better_html, _load_json,
        )

        models = _load_json(project_root / "promptcomp" / "prompt_agent_commands" / "map_models.json")
        setups = _load_json(project_root / "promptcomp" / "prompt_setup_descriptions" / "map_setups.json")
        npy_match = _load_npy_match(folder)
        attempts_map = _discover_attempts(folder, prompt)
        comparison, excluded, _obj_bg = _build_comparison_data(folder, prompt, attempts_map, models, setups, npy_match)

        model_ids = sorted(models.keys())
        html = _render_which_better_html(comparison, excluded, models, setups, model_ids, prompt)

        # The HTML should contain green class for the better objective
        assert 'class="green"' in html

    def test_missing_best_txt_handled(self, mini_tree):
        """If best.txt is removed, attempt counts in denominator but not numerator."""
        folder, project_root, prompt = mini_tree

        # Remove best.txt for modelA/attempt0
        best_path = folder / "wp" / "motorspeed_dt" / f"{prompt}_modelA" / "attempt0" / "lwp" / "rlwp" / "best.txt"
        best_path.unlink()

        from dashes.tables import _load_npy_match, _discover_attempts, _build_success_rates, _load_json

        models = _load_json(project_root / "promptcomp" / "prompt_agent_commands" / "map_models.json")
        setups = _load_json(project_root / "promptcomp" / "prompt_setup_descriptions" / "map_setups.json")
        npy_match = _load_npy_match(folder)
        attempts_map = _discover_attempts(folder, prompt)

        rates, _constraint_bg = _build_success_rates(folder, prompt, attempts_map, models, setups, npy_match)

        # modelA: 2 feasible out of 3 (attempt0 has no best.txt)
        assert rates["motorspeed_dt"]["modelA"] == (2, 3)

    def test_fail_status_in_npy_match_excluded(self, mini_tree):
        """If npy_match status is FAIL, the attempt's selected controller is not counted."""
        folder, project_root, prompt = mini_tree

        # Rewrite npy_match.csv with one FAIL row
        csv_path = folder / "npy_match.csv"
        with open(csv_path, newline="") as f:
            rows = list(csv.reader(f))

        for i, row in enumerate(rows):
            if i == 0:
                continue
            if "modelA" in row[2] and "attempt1" in row[2]:
                rows[i][0] = "FAIL"

        with open(csv_path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerows(rows)

        from dashes.tables import _load_npy_match, _discover_attempts, _build_success_rates, _load_json

        models = _load_json(project_root / "promptcomp" / "prompt_agent_commands" / "map_models.json")
        setups = _load_json(project_root / "promptcomp" / "prompt_setup_descriptions" / "map_setups.json")
        npy_match = _load_npy_match(folder)
        attempts_map = _discover_attempts(folder, prompt)

        rates, _constraint_bg = _build_success_rates(folder, prompt, attempts_map, models, setups, npy_match)

        # modelA: only 2 feasible (attempt1 has FAIL status)
        assert rates["motorspeed_dt"]["modelA"] == (2, 3)

    def test_which_better_html_no_attempt_column(self, mini_tree):
        """Best-of-N format: no Attempt column, one row per setup."""
        folder, project_root, prompt = mini_tree
        from dashes.tables import (
            _load_npy_match, _discover_attempts, _build_comparison_data,
            _render_which_better_html, _load_json,
        )

        models = _load_json(project_root / "promptcomp" / "prompt_agent_commands" / "map_models.json")
        setups = _load_json(project_root / "promptcomp" / "prompt_setup_descriptions" / "map_setups.json")
        npy_match = _load_npy_match(folder)
        attempts_map = _discover_attempts(folder, prompt)
        comparison, excluded, _obj_bg = _build_comparison_data(folder, prompt, attempts_map, models, setups, npy_match)

        model_ids = sorted(models.keys())
        html = _render_which_better_html(comparison, excluded, models, setups, model_ids, prompt)

        assert "<th>Attempt</th>" not in html
        # One data row per setup (only motorspeed_dt in mini tree)
        assert html.count("<tr><td>") == 1

    def test_which_better_background_generated(self, mini_tree):
        """Background text lists all feasible attempts per model with winner."""
        folder, project_root, prompt = mini_tree
        from dashes.tables import (
            _load_npy_match, _discover_attempts, _build_comparison_data,
            _render_which_better_background, _load_json,
        )

        models = _load_json(project_root / "promptcomp" / "prompt_agent_commands" / "map_models.json")
        setups = _load_json(project_root / "promptcomp" / "prompt_setup_descriptions" / "map_setups.json")
        npy_match = _load_npy_match(folder)
        attempts_map = _discover_attempts(folder, prompt)
        comparison, excluded, _obj_bg = _build_comparison_data(folder, prompt, attempts_map, models, setups, npy_match)

        model_ids = sorted(models.keys())
        text = _render_which_better_background(comparison, excluded, models, setups, model_ids)

        assert "Motor speed CTMS" in text
        assert "<-- best" in text
        assert "Winner:" in text

    def test_objective_background_generated(self, mini_tree):
        """Objective background shows formula terms per attempt."""
        folder, project_root, prompt = mini_tree
        from dashes.tables import (
            _load_npy_match, _discover_attempts, _build_comparison_data,
            _render_objective_background, _load_json,
        )

        models = _load_json(project_root / "promptcomp" / "prompt_agent_commands" / "map_models.json")
        setups = _load_json(project_root / "promptcomp" / "prompt_setup_descriptions" / "map_setups.json")
        npy_match = _load_npy_match(folder)
        attempts_map = _discover_attempts(folder, prompt)
        _comparison, _excluded, objective_bg = _build_comparison_data(folder, prompt, attempts_map, models, setups, npy_match)

        text = _render_objective_background(objective_bg, models, setups)

        assert "overshoot_pct" in text
        assert "settling_time_sec" in text
        assert "objective =" in text

    def test_constraint_background_generated(self, mini_tree):
        """Constraint background shows PASS/FAIL per constraint per attempt."""
        folder, project_root, prompt = mini_tree
        from dashes.tables import (
            _load_npy_match, _discover_attempts, _build_success_rates,
            _render_constraint_background, _load_json,
        )

        models = _load_json(project_root / "promptcomp" / "prompt_agent_commands" / "map_models.json")
        setups = _load_json(project_root / "promptcomp" / "prompt_setup_descriptions" / "map_setups.json")
        npy_match = _load_npy_match(folder)
        attempts_map = _discover_attempts(folder, prompt)
        _rates, constraint_bg = _build_success_rates(folder, prompt, attempts_map, models, setups, npy_match)

        text = _render_constraint_background(constraint_bg, models, setups)

        assert "PASS" in text
        assert "FEASIBLE" in text
