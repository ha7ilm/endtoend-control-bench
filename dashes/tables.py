"""Static HTML table generator for LLM controller experiment comparisons.

Reads run artifacts from results/current_run/ and writes:
  - success_rates.html                    (feasibility pass rates per setup/model)
  - success_rates.tex                     (same, as a LaTeX table snippet)
  - which_better.html                     (best-of-N objective comparison)
  - which_better.tex                      (same, as a LaTeX table snippet)
  - unified.html                          (combined success/objective/techniques table)
  - unified.tex                           (same, as a LaTeX table snippet)
  - which_better_background.txt           (per-attempt details behind the comparison)
  - objective_calculation_background.txt  (objective formula breakdown per attempt)
  - constraint_calculation_background.txt (constraint checks per attempt)

Usage:
    python dashes/tables.py [--prompt customctlchoice] [--folder results/current_run]
"""

from __future__ import annotations

import argparse
import csv
import math
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

from dashes.lib_query_runs import (
    build_controller_lookup,
    load_match_csv_rows,
    read_best_controller_name,
)
from dashes.parse_kpis import (
    compute_objective,
    explain_constraints,
    explain_objective,
    format_objective,
    meets_design_spec,
    failed_constraints,
)


# ---------------------------------------------------------------------------
# Data loading helpers
# ---------------------------------------------------------------------------

def _load_json(path: Path) -> Any:
    import json
    with open(path) as f:
        return json.load(f)


def _load_npy_match(folder: Path) -> dict[str, tuple[str, str]]:
    """Load npy_match.csv and build controller_path -> (run_path, status) map."""
    csv_path = folder / "npy_match.csv"
    rows, row_issues = load_match_csv_rows(folder)
    if not rows:
        if row_issues:
            for issue in row_issues:
                print(f"ERROR: npy_match: {issue}", file=sys.stderr)
        else:
            print(
                f"ERROR: no usable rows found in {csv_path}.",
                file=sys.stderr,
            )
        sys.exit(1)

    mapping, mapping_issues = build_controller_lookup(
        rows,
        allowed_statuses=None,
        duplicate_policy="last",
    )
    for issue in [*row_issues, *mapping_issues]:
        print(f"WARNING: npy_match: {issue}", file=sys.stderr)
    if not mapping:
        print(f"ERROR: {csv_path} produced an empty mapping.", file=sys.stderr)
        sys.exit(1)
    return mapping


def _load_controller_techniques(folder: Path) -> dict[str, dict[str, str]]:
    """Load the selected run's optional controller-techniques CSV."""
    csv_path = folder / "list_of_all_controllers.csv"
    if not csv_path.exists():
        print(
            f"WARNING: optional {csv_path} not found. Techniques columns will be empty.",
            file=sys.stderr,
        )
        return {}

    techniques_map: dict[str, dict[str, str]] = {}
    with open(csv_path, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            setup = row.get("setup", "").strip()
            model = row.get("model", "").strip()
            techniques = row.get("control techniques applied (as claimed by the agent)", "").strip()
            if not setup or not model:
                continue
            techniques_map.setdefault(setup, {})[model] = techniques
    return techniques_map


def _read_best_txt(wp_dir: Path) -> str | None:
    """Read best.txt and extract controller filename. Returns None on failure."""
    controller_name, _issue = read_best_controller_name(wp_dir)
    return controller_name


def _extract_controller_number(controller_name: str) -> int | None:
    """Extract N from controller_N.py."""
    m = re.match(r"controller_(\d+)\.py", controller_name)
    if m:
        return int(m.group(1))
    return None


def _load_kpis_from_run(folder: Path, run_rel_path: str) -> dict | None:
    """Load KPIs from a .npy run file."""
    full_path = folder / run_rel_path
    if not full_path.exists():
        return None
    try:
        data = np.load(full_path, allow_pickle=True).item()
        return data.get("kpis")
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------

def _discover_attempts(
    folder: Path, prompt: str
) -> dict[str, dict[str, list[str]]]:
    """Discover setup/model/attempt combinations from sim directory.

    Returns: {setup_name: {model_id: [attempt_dir_names]}}
    """
    sim_dir = folder / "sim"
    result: dict[str, dict[str, list[str]]] = {}
    if not sim_dir.exists():
        return result
    for setup_dir in sorted(sim_dir.iterdir()):
        if not setup_dir.is_dir():
            continue
        setup_name = setup_dir.name
        for case_dir in sorted(setup_dir.iterdir()):
            if not case_dir.is_dir():
                continue
            # case_dir.name is like "customctlchoice_opus46high"
            if not case_dir.name.startswith(prompt + "_"):
                continue
            model_id = case_dir.name[len(prompt) + 1:]
            attempts = sorted(
                d.name for d in case_dir.iterdir()
                if d.is_dir() and d.name.startswith("attempt")
            )
            if attempts:
                result.setdefault(setup_name, {}).setdefault(model_id, []).extend(attempts)
    return result


# ---------------------------------------------------------------------------
# Table 1: Success Rates
# ---------------------------------------------------------------------------

def _build_success_rates(
    folder: Path,
    prompt: str,
    attempts_map: dict[str, dict[str, list[str]]],
    models: dict[str, dict],
    setups: dict[str, dict],
    npy_match: dict[str, tuple[str, str]],
) -> tuple[
    dict[str, dict[str, tuple[int, int]]],
    list[tuple[str, str, str, list[tuple[str, float, float, bool]], bool]],
]:
    """Build success rate data and constraint calculation background.

    Returns: (rates, constraint_bg)
    - rates: {setup: {model: (num_feasible, num_attempts)}}
    - constraint_bg: [(setup_name, model_id, attempt, constraint_results, feasible)]
    """
    rates: dict[str, dict[str, tuple[int, int]]] = {}
    constraint_bg: list[tuple[str, str, str, list[tuple[str, float, float, bool]], bool]] = []

    for setup_name in sorted(attempts_map):
        rates[setup_name] = {}
        for model_id in sorted(attempts_map[setup_name]):
            attempt_names = attempts_map[setup_name][model_id]
            n_feasible = 0
            n_total = len(attempt_names)

            for attempt in attempt_names:
                # Read best.txt
                wp_dir = folder / "wp" / setup_name / f"{prompt}_{model_id}" / attempt / "lwp" / "rlwp"
                best_ctrl = _read_best_txt(wp_dir)
                if best_ctrl is None:
                    print(
                        f"WARNING: missing or malformed best.txt for {setup_name}/{prompt}_{model_id}/{attempt}",
                        file=sys.stderr,
                    )
                    continue

                # Resolve controller -> run via npy_match
                ctrl_rel = f"wp/{setup_name}/{prompt}_{model_id}/{attempt}/lwp/rlwp/{best_ctrl}"
                match = npy_match.get(ctrl_rel)
                if match is None or match[1] == "FAIL":
                    status_info = f"status={match[1]}" if match else "not found in npy_match"
                    print(
                        f"WARNING: controller {ctrl_rel} mapping invalid ({status_info})",
                        file=sys.stderr,
                    )
                    continue

                run_rel, _status = match
                kpis = _load_kpis_from_run(folder, run_rel)
                if kpis is None:
                    print(
                        f"WARNING: could not load KPIs from {run_rel}",
                        file=sys.stderr,
                    )
                    continue

                constr = explain_constraints(setup_name, kpis)
                feasible = meets_design_spec(setup_name, kpis)
                constraint_bg.append((setup_name, model_id, attempt, constr, feasible))

                if feasible:
                    n_feasible += 1

            rates[setup_name][model_id] = (n_feasible, n_total)

    return rates, constraint_bg


# ---------------------------------------------------------------------------
# Table 2: Which Better (objective comparison)
# ---------------------------------------------------------------------------

class _AttemptResult:
    """Result for one attempt's selected controller."""
    __slots__ = ("setup", "model", "attempt", "feasible", "objective", "iterations", "reason")

    def __init__(
        self, setup: str, model: str, attempt: str,
        feasible: bool, objective: float, iterations: int, reason: str,
    ):
        self.setup = setup
        self.model = model
        self.attempt = attempt
        self.feasible = feasible
        self.objective = objective
        self.iterations = iterations
        self.reason = reason


def _build_comparison_data(
    folder: Path,
    prompt: str,
    attempts_map: dict[str, dict[str, list[str]]],
    models: dict[str, dict],
    setups: dict[str, dict],
    npy_match: dict[str, tuple[str, str]],
) -> tuple[
    dict[str, dict[str, list[_AttemptResult]]],
    list[_AttemptResult],
    list[tuple[str, str, str, list[tuple[str, float, float]], float]],
]:
    """Build per-attempt objective results, excluded cases, and objective background.

    Returns: (results_by_setup_model, excluded_list, objective_bg)
    """
    results: dict[str, dict[str, list[_AttemptResult]]] = {}
    excluded: list[_AttemptResult] = []
    objective_bg: list[tuple[str, str, str, list[tuple[str, float, float]], float]] = []

    for setup_name in sorted(attempts_map):
        results[setup_name] = {}
        for model_id in sorted(attempts_map[setup_name]):
            attempt_results: list[_AttemptResult] = []

            for attempt in attempts_map[setup_name][model_id]:
                wp_dir = folder / "wp" / setup_name / f"{prompt}_{model_id}" / attempt / "lwp" / "rlwp"
                best_ctrl = _read_best_txt(wp_dir)

                if best_ctrl is None:
                    r = _AttemptResult(setup_name, model_id, attempt, False, float("inf"), 0, "missing best.txt")
                    excluded.append(r)
                    print(f"WARNING: excluded {setup_name}/{model_id}/{attempt}: missing best.txt", file=sys.stderr)
                    continue

                ctrl_num = _extract_controller_number(best_ctrl)
                iterations = ctrl_num if ctrl_num is not None else 0

                ctrl_rel = f"wp/{setup_name}/{prompt}_{model_id}/{attempt}/lwp/rlwp/{best_ctrl}"
                match = npy_match.get(ctrl_rel)
                if match is None or match[1] == "FAIL":
                    status_info = f"status={match[1]}" if match else "not in npy_match"
                    r = _AttemptResult(setup_name, model_id, attempt, False, float("inf"), iterations, f"mapping invalid ({status_info})")
                    excluded.append(r)
                    print(f"WARNING: excluded {setup_name}/{model_id}/{attempt}: {r.reason}", file=sys.stderr)
                    continue

                run_rel, _status = match
                kpis = _load_kpis_from_run(folder, run_rel)
                if kpis is None:
                    r = _AttemptResult(setup_name, model_id, attempt, False, float("inf"), iterations, f"missing run file {run_rel}")
                    excluded.append(r)
                    print(f"WARNING: excluded {setup_name}/{model_id}/{attempt}: {r.reason}", file=sys.stderr)
                    continue

                # Objective background (before feasibility filter)
                terms, total = explain_objective(setup_name, kpis)
                objective_bg.append((setup_name, model_id, attempt, terms, total))

                feasible = meets_design_spec(setup_name, kpis)
                if not feasible:
                    violations = failed_constraints(setup_name, kpis)
                    reason = f"infeasible selected controller ({', '.join(violations)})"
                    r = _AttemptResult(setup_name, model_id, attempt, False, float("inf"), iterations, reason)
                    excluded.append(r)
                    print(f"WARNING: excluded {setup_name}/{model_id}/{attempt}: {r.reason}", file=sys.stderr)
                    continue

                obj = compute_objective(setup_name, kpis)
                attempt_results.append(
                    _AttemptResult(setup_name, model_id, attempt, True, obj, iterations, "")
                )

            results[setup_name][model_id] = attempt_results

    return results, excluded, objective_bg


# ---------------------------------------------------------------------------
# HTML generation
# ---------------------------------------------------------------------------

_CSS = """\
body { font-family: sans-serif; margin: 2em; }
table { border-collapse: collapse; margin-top: 1em; }
th, td { border: 1px solid #999; padding: 6px 12px; text-align: center; }
th { background: #eee; }
.green { color: #1a7f1a; font-weight: bold; }
.meta { color: #666; font-size: 0.9em; margin-bottom: 1em; }
.exclusions { margin-top: 2em; font-size: 0.9em; }
.exclusions li { margin-bottom: 0.3em; }
"""


def _html_header(title: str, prompt: str) -> str:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    return f"""\
<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>{title}</title>
<style>{_CSS}</style></head><body>
<h1>{title}</h1>
<p class="meta">Prompt: <b>{prompt}</b> &mdash; Generated: {ts}</p>
"""


def _html_footer() -> str:
    return "</body></html>\n"


def _setup_label(setup_name: str, setups: dict[str, dict]) -> str:
    key = setup_name + ".md"
    entry = setups.get(key)
    if entry:
        return entry.get("short_name", setup_name)
    return setup_name


def _model_label(model_id: str, models: dict[str, dict]) -> str:
    entry = models.get(model_id)
    if entry:
        return entry.get("short_name", model_id)
    return model_id


def _model_very_short_label(model_id: str, models: dict[str, dict]) -> str:
    """Return compact model label for tight grouped table headers."""
    entry = models.get(model_id)
    if entry:
        return entry.get("very_short_name") or entry.get("short_name", model_id)
    return model_id


def _html_escape(s: str) -> str:
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _render_success_rates_html(
    rates: dict[str, dict[str, tuple[int, int]]],
    models: dict[str, dict],
    setups: dict[str, dict],
    model_ids: list[str],
    prompt: str,
) -> str:
    html = _html_header("Success Rates", prompt)
    html += "<table>\n<tr><th>Setup</th>"
    for mid in model_ids:
        html += f"<th>{_model_label(mid, models)}</th>"
    html += "</tr>\n"

    for setup_name in sorted(rates):
        html += f"<tr><td>{_setup_label(setup_name, setups)}</td>"
        for mid in model_ids:
            if mid in rates[setup_name]:
                num, den = rates[setup_name][mid]
                html += f"<td>{num}/{den}</td>"
            else:
                html += "<td></td>"
        html += "</tr>\n"

    html += "</table>\n"
    html += _html_footer()
    return html


def _render_which_better_html(
    comparison: dict[str, dict[str, list[_AttemptResult]]],
    excluded: list[_AttemptResult],
    models: dict[str, dict],
    setups: dict[str, dict],
    model_ids: list[str],
    prompt: str,
) -> str:
    """Best-of-N format: one row per setup, showing the best attempt from each model."""
    html = _html_header("Which agent tunes to a better objective?", prompt)
    html += "<table>\n<tr><th>Setup</th>"
    for mid in model_ids:
        html += f"<th>{_model_label(mid, models)}</th>"
    html += "</tr>\n"

    for setup_name in sorted(comparison):
        html += f"<tr><td>{_setup_label(setup_name, setups)}</td>"

        # Best attempt per model
        best_by_model: dict[str, _AttemptResult | None] = {}
        for mid in model_ids:
            attempts = comparison[setup_name].get(mid, [])
            if not attempts:
                best_by_model[mid] = None
            else:
                best_by_model[mid] = min(attempts, key=lambda r: r.objective)

        # Overall winner (lowest objective across models)
        valid_objs = [
            r.objective for r in best_by_model.values()
            if r is not None and math.isfinite(r.objective)
        ]
        best_obj = min(valid_objs) if valid_objs else None

        for mid in model_ids:
            r = best_by_model.get(mid)
            if r is None:
                html += "<td></td>"
                continue
            obj_str = format_objective(r.objective)
            cell = f"{obj_str} ({r.iterations} iterations)"
            if best_obj is not None and math.isfinite(r.objective) and abs(r.objective - best_obj) <= 1e-9:
                html += f'<td><span class="green">{cell}</span></td>'
            else:
                html += f"<td>{cell}</td>"
        html += "</tr>\n"

    html += "</table>\n"
    html += (
        '<p class="meta">Best feasible objective value per model across all attempts '
        "(lower is better); the number of LLM-driven iterations within that attempt to "
        "reach the selected controller is shown in parentheses.</p>\n"
    )

    # Exclusion list
    if excluded:
        html += '<div class="exclusions"><h2>Excluded Cases</h2><ul>\n'
        for r in excluded:
            html += f"<li><b>{r.setup}</b> / {r.model} / {r.attempt}: {r.reason}</li>\n"
        html += "</ul></div>\n"

    html += _html_footer()
    return html


def _render_unified_html(
    rates: dict[str, dict[str, tuple[int, int]]],
    comparison: dict[str, dict[str, list[_AttemptResult]]],
    controller_techniques: dict[str, dict[str, str]],
    models: dict[str, dict],
    setups: dict[str, dict],
    unified_model_ids: list[str],
    prompt: str,
) -> str:
    """Render one merged table with grouped columns and one row per setup."""
    if len(unified_model_ids) != 2:
        raise ValueError("Unified table requires exactly 2 models.")

    model_headers = [_html_escape(_model_very_short_label(mid, models)) for mid in unified_model_ids]

    html = _html_header("Unified Controller Comparison", prompt)
    html += "<table>\n"
    html += (
        "<tr>"
        '<th rowspan="2">Setup</th>'
        '<th colspan="2">Success rates</th>'
        '<th colspan="2">Which better</th>'
        '<th colspan="2">List of control techniques</th>'
        "</tr>\n"
    )
    html += "<tr>"
    for _ in range(3):
        for label in model_headers:
            html += f"<th>{label}</th>"
    html += "</tr>\n"

    setup_names = sorted(set(rates) | set(comparison) | set(controller_techniques))

    for setup_name in setup_names:
        html += f"<tr><td>{_html_escape(_setup_label(setup_name, setups))}</td>"

        # Success rates
        for mid in unified_model_ids:
            maybe_rate = rates.get(setup_name, {}).get(mid)
            if maybe_rate is None:
                html += "<td></td>"
            else:
                num, den = maybe_rate
                html += f"<td>{num}/{den}</td>"

        # Which better (best feasible objective per model)
        best_by_model: dict[str, _AttemptResult | None] = {}
        for mid in unified_model_ids:
            attempts = comparison.get(setup_name, {}).get(mid, [])
            best_by_model[mid] = min(attempts, key=lambda r: r.objective) if attempts else None

        valid_objs = [
            r.objective for r in best_by_model.values()
            if r is not None and math.isfinite(r.objective)
        ]
        best_obj = min(valid_objs) if valid_objs else None

        for mid in unified_model_ids:
            r = best_by_model.get(mid)
            if r is None:
                html += "<td></td>"
                continue
            cell = f"{format_objective(r.objective)} ({r.iterations} iterations)"
            if best_obj is not None and math.isfinite(r.objective) and abs(r.objective - best_obj) <= 1e-9:
                html += f'<td><span class="green">{_html_escape(cell)}</span></td>'
            else:
                html += f"<td>{_html_escape(cell)}</td>"

        # Controller techniques from CSV
        for mid in unified_model_ids:
            techniques = controller_techniques.get(setup_name, {}).get(mid, "")
            if techniques:
                html += f'<td style="text-align:left">{_html_escape(techniques)}</td>'
            else:
                html += "<td></td>"

        html += "</tr>\n"

    html += "</table>\n"
    html += _html_footer()
    return html


# ---------------------------------------------------------------------------
# Background text file renderers
# ---------------------------------------------------------------------------

def _render_which_better_background(
    comparison: dict[str, dict[str, list[_AttemptResult]]],
    excluded: list[_AttemptResult],
    models: dict[str, dict],
    setups: dict[str, dict],
    model_ids: list[str],
) -> str:
    """Per-setup breakdown of all feasible attempts and cross-model winner."""
    lines: list[str] = []
    for setup_name in sorted(comparison):
        lines.append(f"=== {_setup_label(setup_name, setups)} ===")

        best_by_model: dict[str, _AttemptResult | None] = {}
        for mid in model_ids:
            attempts = comparison[setup_name].get(mid, [])
            label = _model_label(mid, models)
            lines.append(f"  {label}:")
            if not attempts:
                lines.append("    (no feasible attempts)")
                best_by_model[mid] = None
                continue
            best = min(attempts, key=lambda r: r.objective)
            best_by_model[mid] = best
            for r in attempts:
                obj_str = format_objective(r.objective)
                marker = "  <-- best" if abs(r.objective - best.objective) <= 1e-9 else ""
                lines.append(f"    {r.attempt}: {obj_str} ({r.iterations} iterations){marker}")

        # Winner
        valid = [
            (mid, best_by_model[mid])
            for mid in model_ids
            if best_by_model.get(mid) is not None and math.isfinite(best_by_model[mid].objective)
        ]
        if len(valid) >= 2:
            valid.sort(key=lambda x: x[1].objective)
            w_mid, w_r = valid[0]
            r_mid, r_r = valid[1]
            w_label = _model_label(w_mid, models)
            w_obj = format_objective(w_r.objective)
            r_obj = format_objective(r_r.objective)
            if abs(w_r.objective - r_r.objective) <= 1e-9:
                lines.append(f"  Winner: Tie ({w_obj})")
            else:
                lines.append(f"  Winner: {w_label} ({w_obj} < {r_obj})")
        elif len(valid) == 1:
            w_label = _model_label(valid[0][0], models)
            lines.append(f"  Winner: {w_label} (only model with feasible attempts)")
        else:
            lines.append("  Winner: none (no feasible attempts)")
        lines.append("")

    if excluded:
        lines.append("=== Excluded Cases ===")
        for r in excluded:
            lines.append(f"  {r.setup} / {r.model} / {r.attempt}: {r.reason}")
        lines.append("")

    return "\n".join(lines) + "\n"


def _render_objective_background(
    objective_bg: list[tuple[str, str, str, list[tuple[str, float, float]], float]],
    models: dict[str, dict],
    setups: dict[str, dict],
) -> str:
    """Per-attempt objective formula breakdown."""
    lines: list[str] = []
    for setup_name, model_id, attempt, terms, total in objective_bg:
        setup_label = _setup_label(setup_name, setups)
        model_label = _model_label(model_id, models)
        lines.append(f"=== {setup_label} / {model_label} / {attempt} ===")

        formula_parts: list[str] = []
        for label, value, weight in terms:
            val_str = format_objective(value) if math.isfinite(value) else "NaN"
            lines.append(f"  {label} = {val_str}  (weight {weight:g})")
            if math.isnan(value):
                formula_parts.append("NaN")
            elif weight == 1.0:
                formula_parts.append(val_str)
            else:
                formula_parts.append(f"{weight:g} * {val_str}")

        total_str = format_objective(total)
        lines.append(f"  objective = {' + '.join(formula_parts)} = {total_str}")
        lines.append("")

    return "\n".join(lines) + "\n"


def _render_constraint_background(
    constraint_bg: list[tuple[str, str, str, list[tuple[str, float, float, bool]], bool]],
    models: dict[str, dict],
    setups: dict[str, dict],
) -> str:
    """Per-attempt constraint check details."""
    lines: list[str] = []
    for setup_name, model_id, attempt, constr_results, feasible in constraint_bg:
        setup_label = _setup_label(setup_name, setups)
        model_label = _model_label(model_id, models)
        lines.append(f"=== {setup_label} / {model_label} / {attempt} ===")

        for desc, actual, limit, passed in constr_results:
            key_name = desc.split(" < ")[0]
            status = "PASS" if passed else "FAIL"
            if math.isnan(actual):
                lines.append(f"  {key_name}: NaN < {limit:g}  {status}")
            else:
                lines.append(f"  {key_name}: {actual:g} < {limit:g}  {status}")

        lines.append(f"  Result: {'FEASIBLE' if feasible else 'INFEASIBLE'}")
        lines.append("")

    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# LaTeX generation
# ---------------------------------------------------------------------------

def _tex_escape(s: str) -> str:
    """Escape LaTeX special characters in a plain-text string."""
    replacements = [
        ("\\", r"\textbackslash{}"),
        ("&",  r"\&"),
        ("%",  r"\%"),
        ("$",  r"\$"),
        ("#",  r"\#"),
        ("_",  r"\_"),
        ("{",  r"\{"),
        ("}",  r"\}"),
        ("~",  r"\textasciitilde{}"),
        ("^",  r"\textasciicircum{}"),
    ]
    for char, escaped in replacements:
        s = s.replace(char, escaped)
    return s


def _tex_header(prompt: str) -> str:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    return f"% Generated: {ts} — Prompt: {prompt}\n"


def _render_success_rates_tex(
    rates: dict[str, dict[str, tuple[int, int]]],
    models: dict[str, dict],
    setups: dict[str, dict],
    model_ids: list[str],
    prompt: str,
) -> str:
    n = len(model_ids)
    col_spec = "l " + " ".join(["c"] * n)
    lines = [
        _tex_header(prompt),
        r"\begin{table}[ht]",
        r"\centering",
        r"\begin{tabular}{" + col_spec + "}",
        r"\toprule",
    ]

    header_cols = ["Setup"] + [_tex_escape(_model_label(mid, models)) for mid in model_ids]
    lines.append(" & ".join(header_cols) + r" \\")
    lines.append(r"\midrule")

    for setup_name in sorted(rates):
        row = [_tex_escape(_setup_label(setup_name, setups))]
        for mid in model_ids:
            if mid in rates[setup_name]:
                num, den = rates[setup_name][mid]
                row.append(f"{num}/{den}")
            else:
                row.append("")
        lines.append(" & ".join(row) + r" \\")

    lines += [
        r"\bottomrule",
        r"\end{tabular}",
        r"\caption{Fraction of attempts producing a feasible controller, per setup and model.}",
        r"\label{tab:success_rates}",
        r"\end{table}",
        "",
    ]
    return "\n".join(lines)


def _render_which_better_tex(
    comparison: dict[str, dict[str, list[_AttemptResult]]],
    models: dict[str, dict],
    setups: dict[str, dict],
    model_ids: list[str],
    prompt: str,
) -> str:
    n = len(model_ids)
    col_spec = "l " + " ".join(["c"] * n)
    lines = [
        _tex_header(prompt),
        r"\begin{table}[ht]",
        r"\centering",
        r"\begin{tabular}{" + col_spec + "}",
        r"\toprule",
    ]

    header_cols = ["Setup"] + [_tex_escape(_model_label(mid, models)) for mid in model_ids]
    lines.append(" & ".join(header_cols) + r" \\")
    lines.append(r"\midrule")

    for setup_name in sorted(comparison):
        best_by_model: dict[str, _AttemptResult | None] = {}
        for mid in model_ids:
            attempts = comparison[setup_name].get(mid, [])
            best_by_model[mid] = min(attempts, key=lambda r: r.objective) if attempts else None

        valid_objs = [
            r.objective for r in best_by_model.values()
            if r is not None and math.isfinite(r.objective)
        ]
        best_obj = min(valid_objs) if valid_objs else None

        row = [_tex_escape(_setup_label(setup_name, setups))]
        for mid in model_ids:
            r = best_by_model.get(mid)
            if r is None:
                row.append("")
                continue
            cell = f"{format_objective(r.objective)} ({r.iterations} iter.)"
            if best_obj is not None and math.isfinite(r.objective) and abs(r.objective - best_obj) <= 1e-9:
                cell = r"\textbf{" + cell + "}"
            row.append(cell)
        lines.append(" & ".join(row) + r" \\")

    lines += [
        r"\bottomrule",
        r"\end{tabular}",
        r"\caption{Best feasible objective value per model across all attempts (lower is better); "
        r"the number of LLM-driven iterations within that attempt to reach the selected controller "
        r"is shown in parentheses. Bold indicates the best result for each setup.}",
        r"\label{tab:which_better}",
        r"\end{table}",
        "",
    ]
    return "\n".join(lines)


def _render_unified_tex(
    rates: dict[str, dict[str, tuple[int, int]]],
    comparison: dict[str, dict[str, list[_AttemptResult]]],
    controller_techniques: dict[str, dict[str, str]],
    models: dict[str, dict],
    setups: dict[str, dict],
    unified_model_ids: list[str],
    prompt: str,
) -> str:
    if len(unified_model_ids) != 2:
        raise ValueError("Unified table requires exactly 2 models.")

    m0, m1 = unified_model_ids
    h0 = _tex_escape(_model_very_short_label(m0, models))
    h1 = _tex_escape(_model_very_short_label(m1, models))

    lines = [
        _tex_header(prompt),
        r"\begin{table}[ht]",
        r"\centering",
        r"\begin{tabular}{l c c c c c c}",
        r"\toprule",
        r"\multirow{2}{*}{Setup} & \multicolumn{2}{c}{Success rates} & \multicolumn{2}{c}{Which better} & \multicolumn{2}{c}{List of control techniques} \\",
        r"\cmidrule(lr){2-3}\cmidrule(lr){4-5}\cmidrule(lr){6-7}",
        f"& {h0} & {h1} & {h0} & {h1} & {h0} & {h1} \\\\",
        r"\midrule",
    ]

    setup_names = sorted(set(rates) | set(comparison) | set(controller_techniques))
    for setup_name in setup_names:
        row = [_tex_escape(_setup_label(setup_name, setups))]

        # Success rates
        for mid in unified_model_ids:
            maybe_rate = rates.get(setup_name, {}).get(mid)
            if maybe_rate is None:
                row.append("")
            else:
                num, den = maybe_rate
                row.append(f"{num}/{den}")

        # Which better (best feasible objective per model)
        best_by_model: dict[str, _AttemptResult | None] = {}
        for mid in unified_model_ids:
            attempts = comparison.get(setup_name, {}).get(mid, [])
            best_by_model[mid] = min(attempts, key=lambda r: r.objective) if attempts else None

        valid_objs = [
            r.objective for r in best_by_model.values()
            if r is not None and math.isfinite(r.objective)
        ]
        best_obj = min(valid_objs) if valid_objs else None

        for mid in unified_model_ids:
            r = best_by_model.get(mid)
            if r is None:
                row.append("")
                continue
            base_cell = _tex_escape(f"{format_objective(r.objective)} ({r.iterations} iter.)")
            if best_obj is not None and math.isfinite(r.objective) and abs(r.objective - best_obj) <= 1e-9:
                row.append(r"\textbf{" + base_cell + "}")
            else:
                row.append(base_cell)

        # Controller techniques from CSV
        for mid in unified_model_ids:
            techniques = controller_techniques.get(setup_name, {}).get(mid, "")
            row.append(_tex_escape(techniques))

        lines.append(" & ".join(row) + r" \\")

    lines += [
        r"\bottomrule",
        r"\end{tabular}",
        r"\caption{Unified setup-wise comparison: success rates, best feasible objective values, and the listed control techniques for Codex and Opus.}",
        r"\label{tab:unified}",
        r"\end{table}",
        "",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Generate comparison tables for LLM controller experiments.")
    parser.add_argument("--prompt", default="customctlchoice", help="Prompt filter (default: customctlchoice)")
    parser.add_argument("--folder", default="results/current_run", help="Base results folder")
    args = parser.parse_args(argv)

    folder = Path(args.folder)
    prompt = args.prompt

    # Load registries
    project_root = Path(__file__).resolve().parent.parent
    models = _load_json(project_root / "promptcomp" / "prompt_agent_commands" / "map_models.json")
    setups = _load_json(project_root / "promptcomp" / "prompt_setup_descriptions" / "map_setups.json")
    controller_techniques = _load_controller_techniques(folder)

    # Load npy_match
    npy_match = _load_npy_match(folder)

    # Discover attempts
    attempts_map = _discover_attempts(folder, prompt)
    if not attempts_map:
        print(f"No attempts found in {folder / 'sim'} for prompt={prompt}", file=sys.stderr)
        sys.exit(1)

    # Filter to models in map_models.json that appear in the data
    data_models = set()
    for setup_models in attempts_map.values():
        data_models.update(setup_models)
    model_ids = sorted(mid for mid in models if mid in data_models)

    if not model_ids:
        print("No matching models found in data.", file=sys.stderr)
        sys.exit(1)

    # Unified output model order (requested): Codex, Opus
    unified_model_ids = [mid for mid in ["codex53xhigh", "opus46high"] if mid in models]
    if len(unified_model_ids) < 2:
        for mid in model_ids:
            if mid not in unified_model_ids:
                unified_model_ids.append(mid)
            if len(unified_model_ids) == 2:
                break
    if len(unified_model_ids) < 2:
        print("Unified table requires at least two models.", file=sys.stderr)
        sys.exit(1)

    # Build tables
    rates, constraint_bg = _build_success_rates(folder, prompt, attempts_map, models, setups, npy_match)
    comparison, excluded, objective_bg = _build_comparison_data(folder, prompt, attempts_map, models, setups, npy_match)

    # Output
    out_dir = folder / "analysis_artifacts" / "tables"
    out_dir.mkdir(parents=True, exist_ok=True)

    sr_html = _render_success_rates_html(rates, models, setups, model_ids, prompt)
    (out_dir / "success_rates.html").write_text(sr_html)

    wb_html = _render_which_better_html(comparison, excluded, models, setups, model_ids, prompt)
    (out_dir / "which_better.html").write_text(wb_html)

    wb_bg = _render_which_better_background(comparison, excluded, models, setups, model_ids)
    (out_dir / "which_better_background.txt").write_text(wb_bg)

    obj_bg = _render_objective_background(objective_bg, models, setups)
    (out_dir / "objective_calculation_background.txt").write_text(obj_bg)

    constr_bg = _render_constraint_background(constraint_bg, models, setups)
    (out_dir / "constraint_calculation_background.txt").write_text(constr_bg)

    sr_tex = _render_success_rates_tex(rates, models, setups, model_ids, prompt)
    (out_dir / "success_rates.tex").write_text(sr_tex)

    wb_tex = _render_which_better_tex(comparison, models, setups, model_ids, prompt)
    (out_dir / "which_better.tex").write_text(wb_tex)

    unified_html = _render_unified_html(
        rates, comparison, controller_techniques, models, setups, unified_model_ids, prompt
    )
    (out_dir / "unified.html").write_text(unified_html)

    unified_tex = _render_unified_tex(
        rates, comparison, controller_techniques, models, setups, unified_model_ids, prompt
    )
    (out_dir / "unified.tex").write_text(unified_tex)

    paths = [
        out_dir / "success_rates.html",
        out_dir / "success_rates.tex",
        out_dir / "which_better.html",
        out_dir / "which_better.tex",
        out_dir / "unified.html",
        out_dir / "unified.tex",
        out_dir / "which_better_background.txt",
        out_dir / "objective_calculation_background.txt",
        out_dir / "constraint_calculation_background.txt",
    ]
    print("Tables written:")
    for p in paths:
        print(f"  {p}")


if __name__ == "__main__":
    main()
