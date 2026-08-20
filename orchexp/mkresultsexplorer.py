#!/usr/bin/env python3
"""Generate a self-contained static site from results/current_run/.

Walks the four-level hierarchy (plant -> agent -> attempt -> run), extracts
per-run time series and KPIs into JSON, copies controller source files, and
normalizes Codex/Claude logs into a common event schema. The resulting
``site/`` directory is portable: dropping it anywhere and opening
``index.html`` should just work.
"""

from __future__ import annotations

import argparse
import csv
import datetime as _dt
import difflib
import json
import math
import shutil
import sys
import urllib.request
from pathlib import Path
from typing import Any, Iterable

import numpy as np

_SCRIPT_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _SCRIPT_DIR.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from dashes.lib_query_runs import (  # noqa: E402
    parse_sim_run_path,
    read_best_controller_name,
)
from dashes.parse_kpis import (  # noqa: E402
    compute_objective,
    explain_constraints,
    meets_design_spec,
)

ASSETS_DIRNAME = "mkresultsexplorer_assets"
MATCH_CSV = "npy_match.csv"
KNOWN_STATUSES_OK = {"PASS", "WARN"}

PLANT_MAP_PATH = _REPO_ROOT / "promptcomp" / "prompt_setup_descriptions" / "map_setups.json"
AGENT_MAP_PATH = _REPO_ROOT / "promptcomp" / "prompt_agent_commands" / "map_models.json"

VENDOR_URLS = {
    "plotly.min.js": "https://cdn.plot.ly/plotly-2.35.2.min.js",
    "marked.min.js": "https://cdn.jsdelivr.net/npm/marked@12.0.2/marked.min.js",
    "mathjax.tex-mml-chtml.js": "https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-mml-chtml.js",
    "bootstrap.bundle.min.js": "https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js",
    "highlight.min.js": "https://cdn.jsdelivr.net/gh/highlightjs/cdn-release@11.9.0/build/highlight.min.js",
    "python.min.js": "https://cdn.jsdelivr.net/gh/highlightjs/cdn-release@11.9.0/build/languages/python.min.js",
    "bash.min.js": "https://cdn.jsdelivr.net/gh/highlightjs/cdn-release@11.9.0/build/languages/bash.min.js",
    "json.min.js": "https://cdn.jsdelivr.net/gh/highlightjs/cdn-release@11.9.0/build/languages/json.min.js",
    "diff.min.js": "https://cdn.jsdelivr.net/gh/highlightjs/cdn-release@11.9.0/build/languages/diff.min.js",
    "bootstrap.min.css": "https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css",
    "github.min.css": "https://cdn.jsdelivr.net/gh/highlightjs/cdn-release@11.9.0/build/styles/github.min.css",
}


# ---------------------------------------------------------------------------
# Name maps (proper names for plant directories and agent directories)
# ---------------------------------------------------------------------------

def _load_name_maps() -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    plant_map: dict[str, dict[str, Any]] = {}
    agent_map: dict[str, dict[str, Any]] = {}
    if PLANT_MAP_PATH.exists():
        for k, v in json.loads(PLANT_MAP_PATH.read_text(encoding="utf-8")).items():
            stem = k[:-3] if k.endswith(".md") else k
            plant_map[stem] = v
    if AGENT_MAP_PATH.exists():
        for k, v in json.loads(AGENT_MAP_PATH.read_text(encoding="utf-8")).items():
            agent_map[k] = v
    return plant_map, agent_map


def _resolve_plant_label(plant_dir: str, plant_map: dict[str, dict[str, Any]]) -> dict[str, str]:
    info = plant_map.get(plant_dir) or {}
    return {
        "long_name": str(info.get("long_name") or plant_dir),
        "short_name": str(info.get("short_name") or plant_dir),
    }


def _resolve_agent_label(agent_dir: str, agent_map: dict[str, dict[str, Any]]) -> dict[str, str]:
    for model_key, info in agent_map.items():
        if agent_dir == model_key or agent_dir.endswith("_" + model_key):
            return {
                "long_name": str(info.get("long_name") or agent_dir),
                "short_name": str(info.get("short_name") or agent_dir),
                "very_short_name": str(info.get("very_short_name") or info.get("short_name") or agent_dir),
                "color": str(info.get("color") or ""),
            }
    return {
        "long_name": agent_dir,
        "short_name": agent_dir,
        "very_short_name": agent_dir,
        "color": "",
    }


# ---------------------------------------------------------------------------
# npy_match.csv
# ---------------------------------------------------------------------------

def _load_full_match_csv(source_root: Path) -> tuple[list[dict[str, str]], list[str]]:
    issues: list[str] = []
    path = source_root / MATCH_CSV
    if not path.exists():
        return [], [f"missing {path}"]
    rows: list[dict[str, str]] = []
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for lineno, row in enumerate(reader, start=2):
            status = (row.get("status") or "").strip().upper()
            run_path = (row.get("run_path") or "").strip()
            controller_path = (row.get("controller_path") or "").strip()
            if not status or not run_path or not controller_path:
                issues.append(f"{path}:{lineno}: malformed row")
                continue
            rows.append(
                {
                    "status": status,
                    "run_path": run_path,
                    "controller_path": controller_path,
                    "note": (row.get("note") or "").strip(),
                    "npy_why": (row.get("npy_why") or "").strip(),
                    "py_why": (row.get("py_why") or "").strip(),
                    "npy_description": (row.get("npy_description") or "").strip(),
                    "py_description": (row.get("py_description") or "").strip(),
                }
            )
    return rows, issues


def _build_accepted_match_lookups(
    rows: list[dict[str, str]],
) -> tuple[dict[str, dict[str, str]], dict[str, dict[str, str]]]:
    """Build run/controller lookups from reviewed PASS and WARN mappings only."""
    run_to_row: dict[str, dict[str, str]] = {}
    controller_to_row: dict[str, dict[str, str]] = {}
    for row in rows:
        if row["status"] not in KNOWN_STATUSES_OK:
            continue
        run_to_row[row["run_path"]] = row
        controller_to_row[row["controller_path"]] = row
    return run_to_row, controller_to_row


def _run_key(run_path: str) -> str:
    return run_path


def _controller_basename_from_path(controller_path: str) -> str:
    return Path(controller_path).name


def _controller_num_from_basename(basename: str) -> int | None:
    import re

    m = re.fullmatch(r"controller_(\d+)\.py", basename)
    return int(m.group(1)) if m else None


def _copy_site_file(src: Path, out_dir: Path, rel_path: str) -> str | None:
    if not src.is_file():
        return None
    dest = out_dir / rel_path
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dest)
    return rel_path


def _load_sanitize_replacements(
    config_path: Path,
    issues: list[str],
) -> list[tuple[str, str]]:
    if not config_path.exists():
        return []
    try:
        raw = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        issues.append(f"failed to load sanitize config {config_path}: {exc}")
        return []
    if not isinstance(raw, dict):
        issues.append(f"{config_path}: sanitize config must be a JSON object")
        return []
    entries = raw.get("literal_replacements", [])
    if not isinstance(entries, list):
        issues.append(f"{config_path}: literal_replacements must be a list")
        return []
    replacements: list[tuple[str, str]] = []
    for idx, entry in enumerate(entries):
        if not isinstance(entry, dict):
            issues.append(f"{config_path}: literal_replacements[{idx}] must be an object")
            continue
        src = entry.get("from")
        dst = entry.get("to", "")
        if not isinstance(src, str) or not src:
            issues.append(f"{config_path}: literal_replacements[{idx}].from must be a non-empty string")
            continue
        if not isinstance(dst, str):
            issues.append(f"{config_path}: literal_replacements[{idx}].to must be a string")
            continue
        replacements.append((src, dst))
    return replacements


def _sanitize_text(text: str, replacements: list[tuple[str, str]]) -> str:
    sanitized = text
    for src, dst in replacements:
        sanitized = sanitized.replace(src, dst)
    return sanitized


def _sanitize_jsonish(value: Any, replacements: list[tuple[str, str]]) -> Any:
    if isinstance(value, str):
        return _sanitize_text(value, replacements)
    if isinstance(value, dict):
        return {str(k): _sanitize_jsonish(v, replacements) for k, v in value.items()}
    if isinstance(value, list):
        return [_sanitize_jsonish(v, replacements) for v in value]
    if isinstance(value, tuple):
        return [_sanitize_jsonish(v, replacements) for v in value]
    return value


def _copy_text_site_file(
    src: Path,
    out_dir: Path,
    rel_path: str,
    replacements: list[tuple[str, str]],
    issues: list[str],
) -> str | None:
    if not src.is_file():
        return None
    dest = out_dir / rel_path
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        text = src.read_text(encoding="utf-8", errors="replace")
        dest.write_text(_sanitize_text(text, replacements), encoding="utf-8")
    except OSError as exc:
        issues.append(f"failed to copy text file {src} -> {dest}: {exc}")
        return None
    return rel_path


# ---------------------------------------------------------------------------
# Run payload extraction
# ---------------------------------------------------------------------------

def _as_float_list(arr: Any) -> list[float] | None:
    try:
        a = np.asarray(arr).astype(float)
    except (TypeError, ValueError):
        return None
    if a.ndim != 1:
        return None
    return [None if not math.isfinite(v) else float(v) for v in a]  # type: ignore[list-item]


def _serialize_signal(value: Any) -> Any:
    if isinstance(value, dict):
        out: dict[str, list[float] | None] = {}
        for k, v in value.items():
            arr = _as_float_list(v)
            if arr is None:
                return None
            out[str(k)] = arr
        return out
    return _as_float_list(value)


def _sanitize_kpis(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {str(k): _sanitize_kpis(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_sanitize_kpis(v) for v in obj]
    if isinstance(obj, (bool, np.bool_)):
        return bool(obj)
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (float, np.floating)):
        f = float(obj)
        return f if math.isfinite(f) else None
    if isinstance(obj, (int, str)) or obj is None:
        return obj
    if isinstance(obj, np.ndarray):
        try:
            return _sanitize_kpis(obj.tolist())
        except Exception:  # noqa: BLE001
            return str(obj)
    return str(obj)


def _serialize_run_payload(payload: dict[str, Any]) -> dict[str, Any] | None:
    time_sec = _as_float_list(payload.get("time_sec"))
    ref = _serialize_signal(payload.get("ref"))
    meas = _serialize_signal(payload.get("meas"))
    control = _as_float_list(payload.get("control"))
    if time_sec is None or ref is None or meas is None or control is None:
        return None
    disturbance = _as_float_list(payload.get("disturbance")) if payload.get("disturbance") is not None else None
    llm_said = payload.get("llm_said") or {}
    if not isinstance(llm_said, dict):
        llm_said = {}
    return {
        "time_sec": time_sec,
        "ref": ref,
        "meas": meas,
        "control": control,
        "disturbance": disturbance,
        "llm_said": {str(k): str(v) for k, v in llm_said.items() if isinstance(v, str)},
    }


def _channels_from_signal(value: Any) -> list[str]:
    if isinstance(value, dict):
        return sorted(value.keys())
    return []


# ---------------------------------------------------------------------------
# Log normalization
# ---------------------------------------------------------------------------

def _value_to_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, indent=2, ensure_ascii=False, default=str)
    except TypeError:
        return str(value)


def _relpath_for_ui(path_str: str) -> str:
    path = Path(path_str)
    try:
        return str(path.relative_to(_REPO_ROOT))
    except ValueError:
        return path_str


def _controller_predecessor(path: Path) -> Path | None:
    import re

    match = re.fullmatch(r"(.*?)(\d+)(\.[^.]+)", path.name)
    if not match:
        return None
    num = int(match.group(2))
    if num <= 1:
        return None
    return path.with_name(f"{match.group(1)}{num - 1}{match.group(3)}")


def _derive_change_preview(change: dict[str, Any]) -> dict[str, Any]:
    out = {
        "path": str(change.get("path", "")),
        "path_rel": _relpath_for_ui(str(change.get("path", ""))),
        "kind": str(change.get("kind", "")),
    }
    raw_path = out["path"]
    if not raw_path:
        return out

    path = Path(raw_path)
    predecessor = _controller_predecessor(path)
    predecessor_exists = predecessor is not None and predecessor.exists()
    if predecessor is not None:
        out["compare_path"] = str(predecessor)
        out["compare_path_rel"] = _relpath_for_ui(str(predecessor))

    if not path.exists():
        return out

    try:
        new_lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return out

    old_lines: list[str]
    fromfile: str
    compare_note: str | None = None
    if predecessor_exists and predecessor is not None:
        try:
            old_lines = predecessor.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            old_lines = []
        fromfile = out.get("compare_path_rel", str(predecessor))
        compare_note = "Compared against the previous numbered controller file."
    elif out["kind"] == "add":
        old_lines = []
        fromfile = "/dev/null"
        compare_note = "Created file; diff is shown against an empty file."
    else:
        return out

    diff_lines = list(
        difflib.unified_diff(
            old_lines,
            new_lines,
            fromfile=fromfile,
            tofile=out["path_rel"],
            lineterm="",
        )
    )
    if diff_lines:
        out["diff_text"] = "\n".join(diff_lines)
    if compare_note:
        out["diff_note"] = compare_note
    return out


def _normalize_codex_line(ev: dict[str, Any]) -> dict[str, Any] | None:
    ev_type = ev.get("type", "")
    if ev_type == "thread.started":
        return {"kind": "meta", "label": "Thread Started", "detail": ev.get("thread_id", "")}
    if ev_type == "turn.started":
        return {"kind": "meta", "label": "Turn Started", "detail": ""}
    if ev_type == "item.completed":
        item = ev.get("item", {}) or {}
        item_type = item.get("type", "")
        if item_type == "reasoning":
            return {"kind": "reasoning", "text": str(item.get("text", ""))}
        if item_type == "agent_message":
            return {"kind": "assistant_text", "text": str(item.get("text", ""))}
        if item_type == "command_execution":
            return {
                "kind": "tool_use",
                "tool_name": "Bash",
                "tool_input": str(item.get("command", "")),
                "tool_output": str(item.get("aggregated_output", "")),
                "exit_code": item.get("exit_code"),
                "status": str(item.get("status", "")),
                "is_error": (item.get("exit_code") not in (0, None)),
            }
        if item_type == "file_change":
            changes = item.get("changes", [])
            return {
                "kind": "tool_use",
                "tool_name": "FileChange",
                "tool_input": changes,
                "tool_changes": [
                    _derive_change_preview(change)
                    for change in changes
                    if isinstance(change, dict)
                ],
            }
        if item_type == "collab_tool_call":
            return {
                "kind": "tool_use",
                "tool_name": f"Collab:{item.get('tool', '?')}",
                "tool_input": item,
            }
        return {"kind": "unknown", "raw": item}
    return None


def _normalize_claude_line(ev: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    ev_type = ev.get("type", "")
    if ev_type == "system":
        subtype = ev.get("subtype", "")
        label = "System Init" if subtype == "init" else f"System:{subtype}"
        parts = []
        for key in ("model", "cwd", "session_id", "permissionMode"):
            val = ev.get(key)
            if val:
                parts.append(f"{key}={val}")
        out.append({"kind": "meta", "label": label, "detail": "  ".join(parts)})
        return out
    if ev_type == "rate_limit_event":
        info = ev.get("rate_limit_info", {}) or {}
        detail = ""
        if isinstance(info, dict):
            status = info.get("status", "")
            reset = info.get("resetsAt", "")
            rl_type = info.get("rateLimitType", "")
            detail = f"status={status} resetsAt={reset} type={rl_type}"
        out.append({"kind": "meta", "label": "Rate Limit", "detail": detail})
        return out
    if ev_type == "result":
        out.append(
            {
                "kind": "result",
                "subtype": str(ev.get("subtype", "")),
                "is_error": bool(ev.get("is_error", False)),
                "duration_ms": ev.get("duration_ms"),
                "num_turns": ev.get("num_turns"),
                "text": _value_to_text(ev.get("result", "")),
            }
        )
        return out
    if ev_type in ("assistant", "user"):
        message = ev.get("message", {}) or {}
        content = message.get("content") if isinstance(message, dict) else None
        if not isinstance(content, list):
            out.append(
                {
                    "kind": "assistant_text" if ev_type == "assistant" else "user_text",
                    "text": _value_to_text(content),
                }
            )
            return out
        for c in content:
            if not isinstance(c, dict):
                out.append({"kind": "unknown", "raw": c})
                continue
            ctype = c.get("type")
            if ctype == "thinking":
                out.append({"kind": "reasoning", "text": str(c.get("thinking", ""))})
            elif ctype == "text":
                kind = "assistant_text" if ev_type == "assistant" else "user_text"
                out.append({"kind": kind, "text": str(c.get("text", ""))})
            elif ctype == "tool_use":
                out.append(
                    {
                        "kind": "tool_use",
                        "tool_name": str(c.get("name", "tool")),
                        "tool_input": c.get("input", {}),
                        "tool_id": str(c.get("id", "")),
                    }
                )
            elif ctype == "tool_result":
                content_val = c.get("content", "")
                out.append(
                    {
                        "kind": "tool_result",
                        "tool_use_id": str(c.get("tool_use_id", "")),
                        "is_error": bool(c.get("is_error", False)),
                        "tool_output": _value_to_text(content_val),
                        "tool_result_meta": _sanitize_kpis(ev.get("tool_use_result")),
                    }
                )
            else:
                out.append({"kind": "unknown", "raw": c})
        return out
    return [{"kind": "unknown", "raw": ev}]


def _find_attempt_log(attempt_dir: Path) -> tuple[Path | None, str | None]:
    """Return (path, kind) for the attempt's log file (kind = 'codex' or 'claude')."""
    rlwp = attempt_dir / "lwp" / "rlwp"
    codex_dir = rlwp / ".codex"
    claude_dir = rlwp / ".claude"
    if codex_dir.is_dir():
        candidates = sorted(codex_dir.glob("codexs_log_*.log"))
        if candidates:
            return candidates[-1], "codex"
    if claude_dir.is_dir():
        candidates = sorted(claude_dir.glob("claude_log_*.jsonl"))
        if candidates:
            return candidates[-1], "claude"
    return None, None


def _write_normalized_log(
    src_path: Path,
    kind: str,
    dest_path: Path,
    issues: list[str],
    replacements: list[tuple[str, str]],
) -> None:
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    with src_path.open("r", encoding="utf-8", errors="replace") as src, dest_path.open("w", encoding="utf-8") as dst:
        for lineno, raw_line in enumerate(src, start=1):
            line = raw_line.strip()
            if not line:
                continue
            try:
                ev = json.loads(line)
            except json.JSONDecodeError as exc:
                issues.append(f"{src_path}:{lineno}: JSON decode error ({exc})")
                continue
            if not isinstance(ev, dict):
                continue
            if kind == "codex":
                norm = _normalize_codex_line(ev)
                if norm is not None:
                    dst.write(json.dumps(_sanitize_jsonish(norm, replacements), ensure_ascii=False) + "\n")
            else:
                for norm in _normalize_claude_line(ev):
                    dst.write(json.dumps(_sanitize_jsonish(norm, replacements), ensure_ascii=False) + "\n")


# ---------------------------------------------------------------------------
# Main build
# ---------------------------------------------------------------------------

def _attempt_key(plant: str, agent: str, attempt_n: int) -> str:
    return f"{plant}__{agent}__attempt{attempt_n}"


def _iter_attempt_dirs(
    sim_dir: Path,
    exclude_agents: set[str] | None = None,
) -> Iterable[tuple[str, str, int, Path]]:
    excluded = exclude_agents or set()
    for plant_dir in sorted(p for p in sim_dir.iterdir() if p.is_dir()):
        plant = plant_dir.name
        for agent_dir in sorted(p for p in plant_dir.iterdir() if p.is_dir()):
            agent = agent_dir.name
            if agent in excluded:
                continue
            for att_dir in sorted(p for p in agent_dir.iterdir() if p.is_dir()):
                name = att_dir.name
                if not name.startswith("attempt"):
                    continue
                try:
                    n = int(name[len("attempt"):])
                except ValueError:
                    continue
                yield plant, agent, n, att_dir


def _vendor_download(site_dir: Path, issues: list[str]) -> None:
    vendor_dir = site_dir / "js" / "vendor"
    vendor_dir.mkdir(parents=True, exist_ok=True)
    for filename, url in VENDOR_URLS.items():
        dest = vendor_dir / filename
        try:
            with urllib.request.urlopen(url, timeout=30) as resp:  # noqa: S310
                dest.write_bytes(resp.read())
        except Exception as exc:  # noqa: BLE001
            issues.append(f"vendor download failed for {filename}: {exc}")


def build_site(
    source_root: Path,
    out_dir: Path,
    vendor: bool,
    clean: bool,
    exclude_agents: set[str] | None = None,
    sanitize_config_path: Path | None = None,
) -> int:
    issues: list[str] = []
    warnings: list[str] = []
    excluded = exclude_agents or set()
    replacements = [(f"{_REPO_ROOT}/", "")]
    if sanitize_config_path is not None:
        replacements.extend(
            _load_sanitize_replacements(sanitize_config_path.resolve(), issues)
        )

    sim_dir = source_root / "sim"
    wp_dir = source_root / "wp"
    if not sim_dir.is_dir():
        print(f"ERROR: missing {sim_dir}", file=sys.stderr)
        return 1

    if clean and out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    data_dir = out_dir / "data"
    runs_dir = data_dir / "runs"
    controllers_dir = data_dir / "controllers"
    logs_dir = data_dir / "logs"
    prompt_inputs_dir = data_dir / "prompt_inputs"
    summaries_dir = data_dir / "summaries"
    for d in (data_dir, runs_dir, controllers_dir, logs_dir, prompt_inputs_dir, summaries_dir):
        d.mkdir(parents=True, exist_ok=True)

    match_rows, match_issues = _load_full_match_csv(source_root)
    issues.extend(match_issues)

    run_to_row, controller_to_row = _build_accepted_match_lookups(match_rows)

    plants: set[str] = set()
    agents: set[str] = set()
    attempts_per_agent: dict[str, list[int]] = {}
    iterations: dict[str, list[dict[str, Any]]] = {}
    plant_specs: dict[str, dict[str, Any]] = {}

    run_count = 0
    copied_controllers = 0
    logs_written = 0

    for plant, agent, attempt_n, att_dir in _iter_attempt_dirs(sim_dir, exclude_agents=excluded):
        plants.add(plant)
        agents.add(agent)
        attempts_per_agent.setdefault(agent, [])
        if attempt_n not in attempts_per_agent[agent]:
            attempts_per_agent[agent].append(attempt_n)

        attempt_key = _attempt_key(plant, agent, attempt_n)
        iteration_list: list[dict[str, Any]] = []

        run_files = sorted(att_dir.glob("run*.npy"), key=lambda p: int(p.stem[3:]) if p.stem[3:].isdigit() else -1)

        rlwp_dir = wp_dir / plant / agent / f"attempt{attempt_n}" / "lwp" / "rlwp"
        attempt_wp_dir = wp_dir / plant / agent / f"attempt{attempt_n}"
        summary_rel = _copy_text_site_file(
            rlwp_dir / "summary.md",
            out_dir,
            f"data/summaries/{plant}/{agent}/attempt{attempt_n}.md",
            replacements,
            issues,
        )
        prompt_inputs: list[dict[str, str]] = []
        for src, name, title, subtitle in (
            (
                attempt_wp_dir / "prompt.md",
                "prompt.md",
                "Prompt shown to the LLM",
                "from prompt.md",
            ),
            (
                rlwp_dir / "problem_description.md",
                "problem_description.md",
                "Problem description available in the agent working directory",
                "from lwp/rlwp/problem_description.md",
            ),
            (
                rlwp_dir / "howto_for_control_loop_software.md",
                "howto_for_control_loop_software.md",
                "Control-loop software guide available in the agent working directory",
                "from lwp/rlwp/howto_for_control_loop_software.md",
            ),
        ):
            rel_path = _copy_text_site_file(
                src,
                out_dir,
                f"data/prompt_inputs/{plant}/{agent}/attempt{attempt_n}/{name}",
                replacements,
                issues,
            )
            if rel_path is not None:
                prompt_inputs.append(
                    {
                        "title": title,
                        "subtitle": subtitle,
                        "file": rel_path,
                        "filename": name,
                    }
                )
        best_basename, best_issue = (None, None)
        if rlwp_dir.is_dir():
            best_basename, best_issue = read_best_controller_name(rlwp_dir)
            if best_issue:
                warnings.append(best_issue)

        best_run_index: int | None = None
        if best_basename is not None:
            controller_rel = f"wp/{plant}/{agent}/attempt{attempt_n}/lwp/rlwp/{best_basename}"
            row = controller_to_row.get(controller_rel)
            if row is not None:
                parsed = parse_sim_run_path(row["run_path"])
                if parsed is not None:
                    _, _, _, best_run_index = parsed

        first_feasible_run_index: int | None = None

        for run_file in run_files:
            if not run_file.stem.startswith("run"):
                continue
            try:
                run_index = int(run_file.stem[3:])
            except ValueError:
                issues.append(f"skipping non-numeric run file: {run_file}")
                continue

            run_count += 1
            try:
                loaded = np.load(run_file, allow_pickle=True)
                payload = loaded.item() if isinstance(loaded, np.ndarray) and loaded.shape == () else loaded
            except Exception as exc:  # noqa: BLE001
                issues.append(f"failed to load {run_file}: {exc}")
                continue
            if not isinstance(payload, dict):
                issues.append(f"{run_file}: payload is not a dict")
                continue

            serialized = _serialize_run_payload(payload)
            if serialized is None:
                issues.append(f"{run_file}: failed to serialize time series")
                continue

            kpis_raw = payload.get("kpis") or {}
            if not isinstance(kpis_raw, dict):
                kpis_raw = {}

            try:
                feasible = meets_design_spec(plant, kpis_raw)
                objective = compute_objective(plant, kpis_raw)
                constraint_rows = explain_constraints(plant, kpis_raw)
            except (TypeError, ValueError) as exc:
                issues.append(f"{run_file}: KPI evaluation failed ({exc})")
                continue

            if feasible and first_feasible_run_index is None:
                first_feasible_run_index = run_index

            # Channels for plant_specs
            channels = _channels_from_signal(serialized["meas"])
            if plant not in plant_specs:
                plant_specs[plant] = {
                    "channels": channels,
                    "constraints_desc": [desc for desc, _v, _l, _p in constraint_rows],
                }

            run_json_rel = f"data/runs/{plant}/{agent}/attempt{attempt_n}/run{run_index}.json"
            run_json_path = out_dir / run_json_rel
            run_json_path.parent.mkdir(parents=True, exist_ok=True)
            run_json = {
                "plant": plant,
                "agent": agent,
                "attempt": attempt_n,
                "run_index": run_index,
                "time_sec": serialized["time_sec"],
                "ref": serialized["ref"],
                "meas": serialized["meas"],
                "control": serialized["control"],
                "disturbance": serialized["disturbance"],
                "kpis": _sanitize_kpis(kpis_raw),
                "llm_said": _sanitize_jsonish(serialized["llm_said"], replacements),
            }
            run_json_path.write_text(json.dumps(run_json, ensure_ascii=False))

            # Resolve matching controller via npy_match
            run_rel = f"sim/{plant}/{agent}/attempt{attempt_n}/run{run_index}.npy"
            row = run_to_row.get(run_rel)
            controller_basename: str | None = None
            controller_rel_to_site: str | None = None
            why = ""
            description = ""
            if row is not None:
                controller_basename = _controller_basename_from_path(row["controller_path"])
                controller_src = source_root / row["controller_path"]
                if controller_src.exists():
                    ctrl_dest_rel = (
                        f"data/controllers/{plant}/{agent}/attempt{attempt_n}/{controller_basename}"
                    )
                    ctrl_dest = out_dir / ctrl_dest_rel
                    ctrl_dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(controller_src, ctrl_dest)
                    copied_controllers += 1
                    controller_rel_to_site = ctrl_dest_rel
                else:
                    issues.append(f"missing controller source {controller_src}")
                why = row.get("npy_why") or row.get("py_why") or ""
                description = row.get("npy_description") or row.get("py_description") or ""
            else:
                # Fall back to run.npy's own llm_said
                why = serialized["llm_said"].get("why", "")
                description = serialized["llm_said"].get("description", "")
                issues.append(f"no npy_match row for {run_rel}")

            iteration_list.append(
                {
                    "run_index": run_index,
                    "iteration_num": run_index + 1,
                    "controller_file": controller_rel_to_site,
                    "controller_basename": controller_basename,
                    "run_file": run_json_rel,
                    "objective": objective if math.isfinite(objective) else None,
                    "objective_is_inf": not math.isfinite(objective),
                    "feasible": bool(feasible),
                    "constraints": [
                        {
                            "desc": desc,
                            "value": None if not math.isfinite(val) else float(val),
                            "limit": float(limit),
                            "passed": bool(passed),
                        }
                        for (desc, val, limit, passed) in constraint_rows
                    ],
                    "why": why,
                    "description": description,
                    "is_best": best_run_index is not None and run_index == best_run_index,
                    "is_first_feasible": False,
                }
            )

        # mark first feasible after loop
        if first_feasible_run_index is not None:
            for it in iteration_list:
                if it["run_index"] == first_feasible_run_index:
                    it["is_first_feasible"] = True
                    break

        iteration_list.sort(key=lambda it: it["run_index"])

        # Common log path per attempt
        log_src, log_kind = _find_attempt_log(wp_dir / plant / agent / f"attempt{attempt_n}")
        log_rel: str | None = None
        if log_src is not None:
            log_rel = f"data/logs/{plant}/{agent}/attempt{attempt_n}.jsonl"
            try:
                _write_normalized_log(log_src, log_kind, out_dir / log_rel, issues, replacements)
                logs_written += 1
            except Exception as exc:  # noqa: BLE001
                issues.append(f"log parse failed for {log_src}: {exc}")
                log_rel = None
        else:
            issues.append(
                f"no log file for {plant}/{agent}/attempt{attempt_n}"
            )

        # Attach log ref to each iteration (one log per attempt shared across iters)
        for it in iteration_list:
            it["log_file"] = log_rel
            it["summary_file"] = summary_rel
            it["prompt_inputs"] = prompt_inputs

        iterations[attempt_key] = iteration_list

    # Deduplicate/sort attempts lists
    for agent, lst in attempts_per_agent.items():
        attempts_per_agent[agent] = sorted(set(lst))

    plant_map, agent_map = _load_name_maps()
    plant_labels = {p: _resolve_plant_label(p, plant_map) for p in sorted(plants)}
    agent_labels = {a: _resolve_agent_label(a, agent_map) for a in sorted(agents)}

    catalog = _sanitize_jsonish(
        {
        "plants": sorted(plants),
        "agents": sorted(agents),
        "plant_labels": plant_labels,
        "agent_labels": agent_labels,
        "attempts_per_agent": attempts_per_agent,
        "iterations": iterations,
        "plant_specs": plant_specs,
        "excluded_agents": sorted(excluded),
        "generated_at": _dt.datetime.now().isoformat(timespec="seconds"),
        "source_root": str(source_root),
        },
        replacements,
    )
    (data_dir / "catalog.json").write_text(json.dumps(catalog, ensure_ascii=False))

    # Copy frontend assets
    assets_src = _SCRIPT_DIR / ASSETS_DIRNAME
    if not assets_src.is_dir():
        issues.append(f"missing assets directory {assets_src}")
    else:
        shutil.copytree(assets_src, out_dir, dirs_exist_ok=True)

    if vendor:
        _vendor_download(out_dir, issues)
        (data_dir / "vendor_enabled").write_text("1")

    (data_dir / "build_issues.json").write_text(
        json.dumps({"issues": issues, "warnings": warnings}, ensure_ascii=False, indent=2)
    )

    print(
        "built site: "
        f"{len(plants)} plants, {len(agents)} agents, "
        f"{len(iterations)} attempts, {run_count} runs, "
        f"{copied_controllers} controllers, {logs_written} logs; "
        f"{len(issues)} issues, {len(warnings)} warnings -> {out_dir}"
    )
    return 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a static results-explorer site from a results tree."
    )
    parser.add_argument("--source", type=Path, default=Path("results/current_run"))
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--vendor", action="store_true", help="Download Plotly/marked/highlight into js/vendor/.")
    parser.add_argument("--clean", action="store_true", help="Wipe the output directory before writing.")
    parser.add_argument(
        "--sanitize-config",
        type=Path,
        default=None,
        help="Optional JSON config with additional literal replacements applied to exported text.",
    )
    parser.add_argument(
        "--exclude-agent",
        action="append",
        default=[],
        metavar="AGENT",
        help="Skip an agent directory by name. Repeat the flag to exclude multiple agents.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    source = args.source.resolve()
    out = (args.out or (args.source / "site")).resolve()
    excluded_agents = {name.strip() for name in args.exclude_agent if str(name).strip()}
    return build_site(
        source_root=source,
        out_dir=out,
        vendor=args.vendor,
        clean=args.clean,
        exclude_agents=excluded_agents,
        sanitize_config_path=args.sanitize_config,
    )


if __name__ == "__main__":
    raise SystemExit(main())
