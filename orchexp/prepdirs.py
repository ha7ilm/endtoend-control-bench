#!/usr/bin/env python3
"""Prepare WP experiment directories and seed prompt files."""

from __future__ import annotations

import argparse
import re
import shutil
import stat
import sys
from pathlib import Path

SETUPS = [
    "aircraftpitch_dt",
    "ballandbeam_dt_nl_act_mg996r",
    "cruisecontrol_dt",
    "invertedpendulum_dt_nl_lim_quanserip02",
    "motorspeed_dt",
    "ballandbeam_dt",
    "cruisecontrol_dt_lim_hondajazz",
    "invertedpendulum_dt",
    "motorspeed_dt_lim_maxonre30",
]

PROMPTS = ["customctlchoice"]
MODELS = ["codex53xhigh", "opus46high"]


def _non_negative_int(value: str) -> int:
    parsed = int(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("attempts must be >= 0")
    return parsed


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Prepare WP experiment directories and seed prompt files."
    )
    parser.add_argument(
        "-a",
        "--attempts",
        type=_non_negative_int,
        default=3,
        help="Number of attempt directories to generate per setup/case (default: 3).",
    )
    parser.add_argument(
        "--onlynew",
        action="store_true",
        help="Skip attempt directories that already exist; leave them untouched.",
    )
    return parser


def _render_template(template_text: str, setup: str, case: str, attempt: int) -> str:
    return (
        template_text.replace("%SETUP%", setup)
        .replace("%CASE%", case)
        .replace("%ATTEMPT%", str(attempt))
    )


_SETUP_BLOCK_RE = re.compile(r'%\{([^:}]+):([^}%]+)\}%\n?')


def _render_prompt_template(text: str, setup: str) -> str:
    """Resolve %{setup_list: content}% conditional blocks for a given setup."""
    def _replace(m: re.Match) -> str:
        setups = [s.strip() for s in m.group(1).split(",")]
        if setup in setups:
            return m.group(2).strip() + "\n"
        return ""
    return _SETUP_BLOCK_RE.sub(_replace, text)


def _validate_sources(
    repo_root: Path,
    model: str,
) -> tuple[Path, list[Path], dict[str, Path], dict[str, list[Path]]]:
    howto_path = (
        repo_root
        / "promptcomp"
        / "prompt_controller_description"
        / "howto_for_control_loop_software.md"
    )
    if not howto_path.is_file():
        raise FileNotFoundError(f"missing source file: {howto_path}")

    agent_command_dir = repo_root / "promptcomp" / "prompt_agent_commands" / model
    if not agent_command_dir.is_dir():
        raise FileNotFoundError(f"missing agent command directory: {agent_command_dir}")
    agent_command_files = sorted(
        path for path in agent_command_dir.iterdir()
        if path.is_file() and not path.name.startswith("_")
    )
    if not agent_command_files:
        raise FileNotFoundError(f"no files found in agent command directory: {agent_command_dir}")

    setup_description_paths: dict[str, Path] = {}
    for setup in SETUPS:
        setup_path = (
            repo_root / "promptcomp" / "prompt_setup_descriptions" / f"{setup}.md"
        )
        if not setup_path.is_file():
            raise FileNotFoundError(f"missing setup description: {setup_path}")
        setup_description_paths[setup] = setup_path

    direct_command_files: dict[str, list[Path]] = {}
    for prompt in PROMPTS:
        prompt_dir = repo_root / "promptcomp" / "prompt_direct_commands" / prompt
        if not prompt_dir.is_dir():
            raise FileNotFoundError(f"missing prompt directory: {prompt_dir}")
        files = sorted(
            path for path in prompt_dir.glob("*.md")
            if path.is_file() and not path.name.startswith("_")
        )
        if not files:
            raise FileNotFoundError(f"no markdown files found in: {prompt_dir}")
        direct_command_files[prompt] = files

    return howto_path, agent_command_files, setup_description_paths, direct_command_files


def main() -> int:
    args = _build_parser().parse_args()
    repo_root = Path(__file__).resolve().parent.parent
    wp_root = repo_root / "results" / "current_run" / "wp"
    if wp_root.exists() and not args.onlynew:
        print(f"{wp_root} already exists; prepdirs did nothing.")
        return 0

    created_attempt_dirs = 0
    skipped_attempt_dirs = 0
    created_dirs: set[tuple[str, str, str, int]] = set()
    for model in MODELS:
        (
            howto_path,
            agent_command_files,
            setup_description_paths,
            direct_command_files,
        ) = _validate_sources(repo_root, model)

        for setup in SETUPS:
            for prompt in PROMPTS:
                case = f"{prompt}_{model}"
                for attempt in range(args.attempts):
                    attempt_dir = wp_root / setup / case / f"attempt{attempt}"
                    if args.onlynew and attempt_dir.exists():
                        skipped_attempt_dirs += 1
                        continue
                    lwp_dir = attempt_dir / "lwp" / "rlwp"
                    lwp_dir.mkdir(parents=True, exist_ok=True)

                    shutil.copy2(
                        howto_path,
                        lwp_dir / "howto_for_control_loop_software.md",
                    )
                    shutil.copy2(
                        setup_description_paths[setup],
                        lwp_dir / "problem_description.md",
                    )
                    for source_prompt in direct_command_files[prompt]:
                        rendered = _render_prompt_template(
                            source_prompt.read_text(encoding="utf-8"), setup
                        )
                        (attempt_dir / source_prompt.name).write_text(rendered, encoding="utf-8")

                    for agent_source in agent_command_files:
                        target_path = attempt_dir / agent_source.name
                        if agent_source.suffix == ".sh":
                            target_path.write_text(
                                _render_template(
                                    agent_source.read_text(encoding="utf-8"),
                                    setup,
                                    case,
                                    attempt,
                                ),
                                encoding="utf-8",
                            )
                            target_path.chmod(
                                target_path.stat().st_mode
                                | stat.S_IXUSR
                                | stat.S_IXGRP
                                | stat.S_IXOTH
                            )
                        else:
                            shutil.copy2(agent_source, target_path)
                    print(f"  created: {attempt_dir.relative_to(wp_root)}")
                    created_attempt_dirs += 1
                    created_dirs.add((setup, prompt, model, attempt))

    run_all_lines = [
        "#!/usr/bin/env bash",
        "set -euo pipefail",
        "",
        'SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"',
        "",
    ]
    for attempt in range(args.attempts):
        attempt_lines = []
        for setup in SETUPS:
            for prompt in PROMPTS:
                for model in MODELS:
                    if args.onlynew and (setup, prompt, model, attempt) not in created_dirs:
                        continue
                    case = f"{prompt}_{model}"
                    rel = f"{setup}/{case}/attempt{attempt}"
                    attempt_lines.append(f'(cd "$SCRIPT_DIR/{rel}" && ./start_llm_auto.sh)')
        if attempt_lines:
            run_all_lines.append(f"# attempt{attempt}")
            run_all_lines.extend(attempt_lines)
            run_all_lines.append("")

    run_all_path = wp_root / "run_all_auto.sh"
    run_all_path.write_text("\n".join(run_all_lines), encoding="utf-8")
    run_all_path.chmod(
        run_all_path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH
    )

    print(f"Created {created_attempt_dirs} attempt directories under {wp_root}.")
    if skipped_attempt_dirs:
        print(f"Skipped {skipped_attempt_dirs} existing attempt directories (--onlynew).")
    print(f"Generated {run_all_path.relative_to(repo_root)}.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # pragma: no cover
        print(f"prepdirs failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
