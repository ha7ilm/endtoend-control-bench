from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np

import orchexp.mkresultsexplorer as mkresultsexplorer
from orchexp.mkresultsexplorer import build_site


def _write_run(path: Path, repo_root: Path) -> None:
    payload = {
        "setup": "motorspeed_dt",
        "time_sec": np.array([0.0, 0.01]),
        "ref": np.array([1.0, 1.0]),
        "meas": np.array([0.0, 0.5]),
        "control": np.array([0.1, 0.2]),
        "kpis": {
            "settling_time_sec": 1.0,
            "overshoot_pct": 2.0,
            "steady_state_error_pct": 0.2,
        },
        "llm_said": {
            "setup": "motorspeed_dt",
            "description": f"Prompt used TOKEN42 from {repo_root}/private/workspace.",
            "why": f"Reasoning mentioned {repo_root}/private/workspace/controller_1.py.",
        },
    }
    np.save(path, payload, allow_pickle=True)


def test_match_lookups_accept_pass_warn_and_exclude_fail() -> None:
    rows = [
        {
            "status": status,
            "run_path": f"sim/setup/case/attempt0/run{index}.npy",
            "controller_path": f"wp/setup/case/attempt0/lwp/rlwp/controller_{index + 1}.py",
        }
        for index, status in enumerate(("PASS", "WARN", "FAIL"))
    ]

    run_to_row, controller_to_row = mkresultsexplorer._build_accepted_match_lookups(rows)

    assert set(run_to_row) == {
        "sim/setup/case/attempt0/run0.npy",
        "sim/setup/case/attempt0/run1.npy",
    }
    assert set(controller_to_row) == {
        "wp/setup/case/attempt0/lwp/rlwp/controller_1.py",
        "wp/setup/case/attempt0/lwp/rlwp/controller_2.py",
    }


def test_build_site_sanitizes_prompt_and_log_text(tmp_path: Path) -> None:
    repo_root = mkresultsexplorer._REPO_ROOT
    repo_prefix = f"{repo_root}/"
    source_root = tmp_path / "current_run"
    sim_attempt = source_root / "sim" / "motorspeed_dt" / "customctlchoice_codex53xhigh" / "attempt0"
    wp_attempt = source_root / "wp" / "motorspeed_dt" / "customctlchoice_codex53xhigh" / "attempt0"
    rlwp_dir = wp_attempt / "lwp" / "rlwp"
    codex_dir = rlwp_dir / ".codex"
    sim_attempt.mkdir(parents=True)
    codex_dir.mkdir(parents=True)

    _write_run(sim_attempt / "run0.npy", repo_root)

    (wp_attempt / "prompt.md").write_text(
        f"Use {repo_root}/private/workspace/controller_1.py and TOKEN42.\n",
        encoding="utf-8",
    )
    (rlwp_dir / "problem_description.md").write_text(
        f"Problem file lives under {repo_root}/private/workspace/problem.md.\n",
        encoding="utf-8",
    )
    (rlwp_dir / "howto_for_control_loop_software.md").write_text(
        f"Guide path: {repo_root}/private/workspace/howto.md.\n",
        encoding="utf-8",
    )
    (rlwp_dir / "controller_1.py").write_text("print('controller')\n", encoding="utf-8")

    log_path = codex_dir / "codexs_log_2026-04-18.log"
    log_lines = [
        {
            "type": "item.completed",
            "item": {
                "type": "reasoning",
                "text": f"Inspect {repo_root}/private/workspace/prompt.md and TOKEN42.",
            },
        },
        {
            "type": "item.completed",
            "item": {
                "type": "command_execution",
                "command": f"cat {repo_root}/private/workspace/controller_1.py",
                "aggregated_output": (
                    f"Loaded TOKEN42 from {repo_root}/private/workspace/controller_1.py"
                ),
                "exit_code": 0,
                "status": "completed",
            },
        },
    ]
    log_path.write_text("".join(json.dumps(line) + "\n" for line in log_lines), encoding="utf-8")

    with (source_root / "npy_match.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["status", "run_path", "controller_path", "npy_why", "npy_description"],
        )
        writer.writeheader()
        writer.writerow(
            {
                "status": "PASS",
                "run_path": "sim/motorspeed_dt/customctlchoice_codex53xhigh/attempt0/run0.npy",
                "controller_path": (
                    "wp/motorspeed_dt/customctlchoice_codex53xhigh/attempt0/lwp/rlwp/controller_1.py"
                ),
                "npy_why": f"Run path {repo_root}/private/workspace/run0.npy",
                "npy_description": "Description TOKEN42",
            }
        )

    sanitize_config = tmp_path / "sanitize.json"
    sanitize_config.write_text(
        json.dumps(
            {
                "literal_replacements": [
                    {"from": "TOKEN42", "to": "[redacted-token]"},
                ]
            }
        ),
        encoding="utf-8",
    )

    out_dir = tmp_path / "site"
    rc = build_site(
        source_root=source_root,
        out_dir=out_dir,
        vendor=False,
        clean=False,
        sanitize_config_path=sanitize_config,
    )

    assert rc == 0

    prompt_text = (
        out_dir
        / "data"
        / "prompt_inputs"
        / "motorspeed_dt"
        / "customctlchoice_codex53xhigh"
        / "attempt0"
        / "prompt.md"
    ).read_text(encoding="utf-8")
    assert repo_prefix not in prompt_text
    assert "[redacted-token]" in prompt_text
    assert "private/workspace/controller_1.py" in prompt_text

    log_text = (
        out_dir
        / "data"
        / "logs"
        / "motorspeed_dt"
        / "customctlchoice_codex53xhigh"
        / "attempt0.jsonl"
    ).read_text(encoding="utf-8")
    assert repo_prefix not in log_text
    assert "[redacted-token]" in log_text

    run_json = json.loads(
        (
            out_dir
            / "data"
            / "runs"
            / "motorspeed_dt"
            / "customctlchoice_codex53xhigh"
            / "attempt0"
            / "run0.json"
        ).read_text(encoding="utf-8")
    )
    assert repo_prefix not in json.dumps(run_json)
    assert "[redacted-token]" in json.dumps(run_json)


def test_build_site_copies_math_delimiter_preserving_doc_renderer(tmp_path: Path) -> None:
    source_root = tmp_path / "current_run"
    (source_root / "sim").mkdir(parents=True)
    (source_root / "npy_match.csv").write_text(
        "status,run_path,controller_path,npy_why,npy_description\n",
        encoding="utf-8",
    )

    out_dir = tmp_path / "site"
    rc = build_site(
        source_root=source_root,
        out_dir=out_dir,
        vendor=False,
        clean=False,
    )

    assert rc == 0

    doc_common = (out_dir / "js" / "doc_common.js").read_text(encoding="utf-8")
    assert "protectMathDelimiters" in doc_common
    assert "restoreMathDelimiters" in doc_common
    assert '@@RE_MATH_INLINE_OPEN@@' in doc_common
    assert '@@RE_MATH_DISPLAY_OPEN@@' in doc_common
    assert 'raw: "\\\\("' in doc_common
    assert 'raw: "\\\\)"' in doc_common
    assert 'raw: "\\\\["' in doc_common
    assert 'raw: "\\\\]"' in doc_common
