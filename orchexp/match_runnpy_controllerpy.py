#!/usr/bin/env python3
"""Match controller_N.py files with runN.npy files and write a CSV report.

Primary rule: controller_N.py  ->  run(N-1).npy
Cross-check: compare description and why fields from the controller source
(MachineClient kwargs) against llm_said stored in the run's .npy payload.

Output: results/current_run/npy_match.csv

Usage:
    python orchexp/match_runnpy_controllerpy.py [--prompt customctlchoice]
        [--sim-root results/current_run/sim]
        [--wp-root results/current_run/wp]
        [--out results/current_run/npy_match.csv]
"""

from __future__ import annotations

import argparse
import ast
import csv
import re
import sys
from pathlib import Path
from typing import Any

import numpy as np

CONTROLLER_RE = re.compile(r"^controller_(\d+)\.py$")
ATTEMPT_RE = re.compile(r"^attempt(\d+)$")

# ---------------------------------------------------------------------------
# AST extraction: description / why from MachineClient(...) in controller .py
# ---------------------------------------------------------------------------

def _collect_toplevel_assignments(tree: ast.Module) -> dict[str, Any]:
    """Gather simple Name = Constant assignments at module level."""
    env: dict[str, Any] = {}
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target = node.targets[0]
            if isinstance(target, ast.Name) and isinstance(node.value, ast.Constant):
                env[target.id] = node.value.value
    return env


def _resolve_fstring(node: ast.JoinedStr, env: dict[str, Any]) -> tuple[str | None, str]:
    """Resolve an f-string.  Returns (full_or_none, prefix_up_to_first_unresolved)."""
    parts: list[str] = []
    prefix_parts: list[str] = []
    prefix_done = False
    for value in node.values:
        if isinstance(value, ast.Constant):
            parts.append(str(value.value))
            if not prefix_done:
                prefix_parts.append(str(value.value))
        elif isinstance(value, ast.FormattedValue):
            inner = value.value
            if isinstance(inner, ast.Name) and inner.id in env:
                fmt = ""
                if value.format_spec is not None and isinstance(value.format_spec, ast.JoinedStr):
                    full, _ = _resolve_fstring(value.format_spec, env)
                    if full is None:
                        if not prefix_done:
                            prefix_done = True
                        parts.append(None)  # type: ignore[arg-type]
                        continue
                    fmt = full
                resolved = format(env[inner.id], fmt) if fmt else str(env[inner.id])
                parts.append(resolved)
                if not prefix_done:
                    prefix_parts.append(resolved)
            else:
                if not prefix_done:
                    prefix_done = True
                parts.append(None)  # type: ignore[arg-type]
        else:
            if not prefix_done:
                prefix_done = True
            parts.append(None)  # type: ignore[arg-type]

    prefix = "".join(prefix_parts)
    if None in parts:
        return None, prefix
    return "".join(parts), prefix  # type: ignore[arg-type]


def _resolve_string_node(node: ast.expr, env: dict[str, Any]) -> tuple[str | None, str]:
    """Resolve an AST node to a string.  Returns (full_or_none, prefix)."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value, node.value
    if isinstance(node, ast.JoinedStr):
        return _resolve_fstring(node, env)
    return None, ""


def _extract_machineclient_fields(source: str, path: str) -> dict[str, str | None]:
    """Return {description, description_prefix, description_source, why} from MachineClient call."""
    out: dict[str, str | None] = {
        "description": None,
        "description_prefix": "",
        "description_source": None,
        "why": None,
        "parse_error": None,
    }
    try:
        tree = ast.parse(source, filename=path)
    except SyntaxError as exc:
        out["parse_error"] = f"syntax error: {exc}"
        return out

    env = _collect_toplevel_assignments(tree)

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Name) and func.id == "MachineClient":
            pass
        elif isinstance(func, ast.Attribute) and func.attr == "MachineClient":
            pass
        else:
            continue
        for kw in node.keywords:
            if kw.arg == "description":
                full, prefix = _resolve_string_node(kw.value, env)
                out["description"] = full
                out["description_prefix"] = prefix
                raw = ast.get_source_segment(source, kw.value)
                out["description_source"] = raw
            elif kw.arg == "why":
                full, _ = _resolve_string_node(kw.value, env)
                out["why"] = full
        return out

    out["parse_error"] = "no MachineClient call found"
    return out


# ---------------------------------------------------------------------------
# Run .npy extraction
# ---------------------------------------------------------------------------

def _load_run_fields(path: Path) -> dict[str, str | None]:
    out: dict[str, str | None] = {"description": None, "why": None, "load_error": None}
    try:
        loaded = np.load(path, allow_pickle=True)
    except Exception as exc:  # noqa: BLE001
        out["load_error"] = str(exc)
        return out

    payload: Any = loaded
    if isinstance(loaded, np.ndarray) and loaded.shape == ():
        try:
            payload = loaded.item()
        except Exception as exc:  # noqa: BLE001
            out["load_error"] = str(exc)
            return out

    if not isinstance(payload, dict):
        out["load_error"] = "payload is not a dict"
        return out

    llm_said = payload.get("llm_said")
    if not isinstance(llm_said, dict):
        out["load_error"] = "llm_said missing or not a dict"
        return out

    d = llm_said.get("description")
    w = llm_said.get("why")
    out["description"] = d if isinstance(d, str) else None
    out["why"] = w if isinstance(w, str) else None
    return out


# ---------------------------------------------------------------------------
# Matching one controller -> run(N-1)
# ---------------------------------------------------------------------------

MIN_PREFIX_LEN = 20


def _build_run_why_index(sim_dir: Path) -> dict[int, str]:
    """Load why field from every runN.npy in sim_dir. Returns {run_index: why}."""
    index: dict[int, str] = {}
    if not sim_dir.is_dir():
        return index
    for p in sim_dir.iterdir():
        m = re.match(r"^run(\d+)\.npy$", p.name)
        if m is None:
            continue
        ri = int(m.group(1))
        f = _load_run_fields(p)
        if f["why"] is not None:
            index[ri] = f["why"]
    return index


def _find_shifted_run(
    ctrl_why: str | None, run_index: int, run_why_index: dict[int, str],
) -> int | None:
    """Find a nearby run (within +/-3) whose why matches ctrl_why. Returns run index or None."""
    if ctrl_why is None:
        return None
    for offset in (-1, 1, -2, 2, -3, 3):
        candidate = run_index + offset
        if candidate in run_why_index and run_why_index[candidate] == ctrl_why:
            return candidate
    return None


def _try_match_run(
    ctrl_f: dict[str, str | None], run_f: dict[str, str | None],
) -> tuple[str, str]:
    """Compare ctrl fields against a run's fields. Returns (status, note_fragment)."""
    why_match = (
        ctrl_f["why"] is not None
        and run_f["why"] is not None
        and ctrl_f["why"] == run_f["why"]
    )
    if not why_match:
        return "fail", "why mismatch"

    desc_exact = (
        ctrl_f["description"] is not None
        and run_f["description"] is not None
        and ctrl_f["description"] == run_f["description"]
    )
    if desc_exact:
        return "pass", ""

    desc_prefix_ok = False
    if run_f["description"] is not None:
        prefix = ctrl_f["description_prefix"] or ""
        if len(prefix) >= MIN_PREFIX_LEN and run_f["description"].startswith(prefix):
            desc_prefix_ok = True

    if desc_prefix_ok:
        return "pass", f"description prefix match ({len(ctrl_f['description_prefix'])} chars)"
    if ctrl_f["description"] is None:
        prefix = ctrl_f["description_prefix"] or ""
        return "pass", f"description not resolvable from AST (prefix {len(prefix)} chars)"
    # why matches but description explicitly differs
    return "fail", "why match but description mismatch"


def _match_one(
    ctrl_n: int,
    ctrl_path: Path,
    sim_dir: Path,
    current_run: Path,
    run_why_index: dict[int, str],
) -> dict[str, str]:
    """Return one CSV row as a dict."""
    run_index = ctrl_n - 1
    run_name = f"run{run_index}.npy"
    run_path = sim_dir / run_name

    ctrl_rel = str(ctrl_path.relative_to(current_run))

    ctrl_source = ctrl_path.read_text(encoding="utf-8")
    ctrl_f = _extract_machineclient_fields(ctrl_source, str(ctrl_path))

    if ctrl_f["parse_error"]:
        return {
            "status": "FAIL",
            "run_path": str(run_path.relative_to(current_run)),
            "controller_path": ctrl_rel,
            "note": f"controller parse error: {ctrl_f['parse_error']}",
            "npy_why": "",
            "py_why": "",
            "npy_description": "",
            "py_description": "",
        }

    # --- Try the naive N-1 run first ---
    if run_path.exists():
        run_f = _load_run_fields(run_path)
        if run_f["load_error"] is None:
            result, detail = _try_match_run(ctrl_f, run_f)
            if result == "pass":
                note = f"matched run{run_index} (N-1 rule)"
                if detail:
                    note += f"; {detail}"
                return {
                    "status": "PASS" if not detail else "WARN",
                    "run_path": str(run_path.relative_to(current_run)),
                    "controller_path": ctrl_rel,
                    "note": note if detail else "",
                    "npy_why": run_f["why"] or "",
                    "py_why": ctrl_f["why"] or "",
                    "npy_description": run_f["description"] or "",
                    "py_description": ctrl_f["description"] or ctrl_f["description_source"] or "",
                }

    # --- N-1 didn't work; try shifted match ---
    shifted_ri = _find_shifted_run(ctrl_f["why"], run_index, run_why_index)
    if shifted_ri is not None:
        shifted_path = sim_dir / f"run{shifted_ri}.npy"
        shifted_f = _load_run_fields(shifted_path)
        if shifted_f["load_error"] is None:
            result, detail = _try_match_run(ctrl_f, shifted_f)
            if result == "pass":
                offset = shifted_ri - run_index
                note = f"shifted: matched run{shifted_ri} ({offset:+d}) instead of run{run_index}"
                if detail:
                    note += f"; {detail}"
                return {
                    "status": "WARN",
                    "run_path": str(shifted_path.relative_to(current_run)),
                    "controller_path": ctrl_rel,
                    "note": note,
                    "npy_why": shifted_f["why"] or "",
                    "py_why": ctrl_f["why"] or "",
                    "npy_description": shifted_f["description"] or "",
                    "py_description": ctrl_f["description"] or ctrl_f["description_source"] or "",
                }

    # --- Nothing matched ---
    # Build FAIL row against the N-1 run (or note it missing)
    if not run_path.exists():
        return {
            "status": "FAIL",
            "run_path": str(run_path.relative_to(current_run)),
            "controller_path": ctrl_rel,
            "note": f"run file missing: {run_name}; no shifted match found",
            "npy_why": "",
            "py_why": ctrl_f["why"] or "",
            "npy_description": "",
            "py_description": ctrl_f["description"] or ctrl_f["description_source"] or "",
        }

    run_f = _load_run_fields(run_path)
    if run_f["load_error"]:
        return {
            "status": "FAIL",
            "run_path": str(run_path.relative_to(current_run)),
            "controller_path": ctrl_rel,
            "note": f"run load error: {run_f['load_error']}",
            "npy_why": "",
            "py_why": ctrl_f["why"] or "",
            "npy_description": "",
            "py_description": ctrl_f["description"] or ctrl_f["description_source"] or "",
        }

    if ctrl_f["why"] is None:
        note = "controller why not extractable"
    elif run_f["why"] is None:
        note = "run why field missing"
    else:
        note = "why mismatch; no shifted match found"

    return {
        "status": "FAIL",
        "run_path": str(run_path.relative_to(current_run)),
        "controller_path": ctrl_rel,
        "note": note,
        "npy_why": run_f["why"] or "",
        "py_why": ctrl_f["why"] or "",
        "npy_description": run_f["description"] or "",
        "py_description": ctrl_f["description"] or ctrl_f["description_source"] or "",
    }


# ---------------------------------------------------------------------------
# Discovery and main
# ---------------------------------------------------------------------------

def _discover_attempts(
    sim_root: Path,
    wp_root: Path,
    prompt: str,
) -> list[tuple[str, str, int, Path, Path]]:
    """Return (setup, exp_id, attempt_n, wp_rlwp_dir, sim_attempt_dir)."""
    entries: list[tuple[str, str, int, Path, Path]] = []
    if not sim_root.is_dir():
        return entries
    for setup_dir in sorted(sim_root.iterdir()):
        if not setup_dir.is_dir():
            continue
        setup = setup_dir.name
        for exp_dir in sorted(setup_dir.iterdir()):
            if not exp_dir.is_dir():
                continue
            exp_id = exp_dir.name
            if not exp_id.startswith(prompt + "_"):
                continue
            for att_dir in sorted(exp_dir.iterdir()):
                if not att_dir.is_dir():
                    continue
                m = ATTEMPT_RE.match(att_dir.name)
                if m is None:
                    continue
                att_n = int(m.group(1))
                wp_rlwp = wp_root / setup / exp_id / f"attempt{att_n}" / "lwp" / "rlwp"
                entries.append((setup, exp_id, att_n, wp_rlwp, att_dir))
    return entries


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Match controller_N.py <-> run(N-1).npy, write CSV report."
    )
    parser.add_argument("--prompt", default="customctlchoice")
    parser.add_argument("--sim-root", type=Path, default=Path("results/current_run/sim"))
    parser.add_argument("--wp-root", type=Path, default=Path("results/current_run/wp"))
    parser.add_argument("--out", type=Path, default=Path("results/current_run/npy_match.csv"))
    args = parser.parse_args()

    current_run = args.sim_root.parent
    attempts = _discover_attempts(args.sim_root, args.wp_root, args.prompt)
    if not attempts:
        print(f"No attempts found for prompt={args.prompt!r}", file=sys.stderr)
        sys.exit(1)

    fieldnames = [
        "status",
        "run_path",
        "controller_path",
        "note",
        "npy_why",
        "py_why",
        "npy_description",
        "py_description",
    ]

    rows: list[dict[str, str]] = []
    counts: dict[str, int] = {"PASS": 0, "WARN": 0, "FAIL": 0}

    for setup, exp_id, att_n, wp_dir, sim_dir in attempts:
        run_why_index = _build_run_why_index(sim_dir)
        ctrl_files = sorted(wp_dir.glob("controller_*.py"))
        for cf in ctrl_files:
            m = CONTROLLER_RE.match(cf.name)
            if m is None:
                continue
            n = int(m.group(1))
            row = _match_one(n, cf, sim_dir, current_run, run_why_index)
            rows.append(row)
            counts[row["status"]] = counts.get(row["status"], 0) + 1

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote {len(rows)} rows to {args.out}", file=sys.stderr)
    print(
        f"  PASS={counts['PASS']}  WARN={counts['WARN']}  FAIL={counts['FAIL']}",
        file=sys.stderr,
    )
    if counts["FAIL"] > 0:
        sys.exit(2)


if __name__ == "__main__":
    main()
