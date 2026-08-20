#!/usr/bin/env python3
"""List inline Python executions from Codex and Claude logs as JSON."""

from __future__ import annotations

import argparse
import json
import re
import shlex
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

PY_CMD_RE = re.compile(r"^python(?:3(?:\.\d+)?)?$")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Scan codexs_*.log (Codex) and *.jsonl (Claude) logs and emit "
            "all inline-Python command invocations as JSON."
        )
    )
    parser.add_argument(
        "--scan-root",
        type=Path,
        default=Path("results/current_run/wp"),
        help="Root folder to recursively scan (default: results/current_run/wp).",
    )
    parser.add_argument(
        "--include-started",
        action="store_true",
        help=(
            "Include Codex command entries with status=in_progress as well. "
            "By default only completed/failed command executions are considered."
        ),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional output JSON file path. Defaults to stdout.",
    )
    parser.add_argument(
        "--indent",
        type=int,
        default=2,
        help="JSON indentation level (default: 2). Use 0 for compact output.",
    )
    parser.add_argument(
        "--truncate-command",
        type=int,
        default=0,
        help="If >0, truncate each command string to this many characters.",
    )
    return parser.parse_args()


def _split_command_chains(command: str) -> list[str]:
    return [p for p in re.split(r"\s*(?:&&|\|\||;)\s*", command) if p.strip()]


def _classify_inline_python(command: str, depth: int = 0) -> set[str]:
    if depth > 4:
        return set()

    kinds: set[str] = set()

    for chain in _split_command_chains(command):
        pipeline_parts = [p.strip() for p in chain.split("|") if p.strip()]

        for idx, part in enumerate(pipeline_parts):
            if re.match(r"^python(?:3(?:\.\d+)?)?\s+-c\b", part):
                kinds.add("python_c")
            if re.match(r"^python(?:3(?:\.\d+)?)?\s*<<", part):
                kinds.add("python_heredoc")
            if re.match(r"^python(?:3(?:\.\d+)?)?\s+/dev/stdin\b", part):
                kinds.add("python_dev_stdin")

            try:
                tokens = shlex.split(part, posix=True)
            except ValueError:
                tokens = []

            for i, tok in enumerate(tokens[:-1]):
                if tok in ("-c", "-lc"):
                    kinds.update(_classify_inline_python(tokens[i + 1], depth + 1))

            if tokens and PY_CMD_RE.match(tokens[0]):
                if len(tokens) >= 2 and (
                    tokens[1] == "-" or tokens[1] == "-c" or tokens[1].startswith("-c")
                ):
                    kinds.add("python_stdin_dash" if tokens[1] == "-" else "python_c")

                # Piped stdin into python, e.g. "cat x.py | python" or "... | python -"
                if idx > 0 and (
                    len(tokens) == 1 or (len(tokens) >= 2 and tokens[1] == "-")
                ):
                    kinds.add("python_pipe")

    return kinds


def _iter_codex_command_events(
    scan_root: Path, include_started: bool
) -> Iterator[tuple[Path, int, str]]:
    allowed_status = {"completed", "failed"}
    if include_started:
        allowed_status.add("in_progress")

    for log_path in sorted(scan_root.rglob("codexs_*.log")):
        with log_path.open("r", encoding="utf-8") as f:
            for line_no, line in enumerate(f, 1):
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue

                item = obj.get("item") or {}
                if item.get("type") != "command_execution":
                    continue

                status = item.get("status")
                if status not in allowed_status:
                    continue

                command = item.get("command")
                if isinstance(command, str) and command:
                    yield log_path, line_no, command


def _iter_claude_command_events(scan_root: Path) -> Iterator[tuple[Path, int, str]]:
    for log_path in sorted(scan_root.rglob("*.jsonl")):
        with log_path.open("r", encoding="utf-8") as f:
            for line_no, line in enumerate(f, 1):
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue

                if obj.get("type") != "assistant":
                    continue

                message = obj.get("message") or {}
                for part in message.get("content") or []:
                    if part.get("type") != "tool_use" or part.get("name") != "Bash":
                        continue

                    command = (part.get("input") or {}).get("command")
                    if isinstance(command, str) and command:
                        yield log_path, line_no, command


def _maybe_truncate(text: str, limit: int) -> str:
    if limit <= 0 or len(text) <= limit:
        return text
    if limit <= 3:
        return text[:limit]
    return text[: limit - 3] + "..."


def _build_output(
    scan_root: Path,
    include_started: bool,
    truncate_command: int,
) -> dict[str, Any]:
    codex_logs = sorted(scan_root.rglob("codexs_*.log"))
    claude_logs = sorted(scan_root.rglob("*.jsonl"))

    records: list[dict[str, Any]] = []
    codex_commands_scanned = 0
    claude_commands_scanned = 0

    for path, line_no, command in _iter_codex_command_events(scan_root, include_started):
        codex_commands_scanned += 1
        kinds = sorted(_classify_inline_python(command))
        if not kinds:
            continue

        records.append(
            {
                "source": "codex",
                "log_path": str(path),
                "line": line_no,
                "kinds": kinds,
                "command": _maybe_truncate(command, truncate_command),
            }
        )

    for path, line_no, command in _iter_claude_command_events(scan_root):
        claude_commands_scanned += 1
        kinds = sorted(_classify_inline_python(command))
        if not kinds:
            continue

        records.append(
            {
                "source": "claude",
                "log_path": str(path),
                "line": line_no,
                "kinds": kinds,
                "command": _maybe_truncate(command, truncate_command),
            }
        )

    codex_matches = sum(1 for r in records if r["source"] == "codex")
    claude_matches = sum(1 for r in records if r["source"] == "claude")

    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "scan_root": str(scan_root),
        "options": {
            "include_started": include_started,
            "truncate_command": truncate_command,
        },
        "summary": {
            "log_files": {
                "codex": len(codex_logs),
                "claude": len(claude_logs),
                "total": len(codex_logs) + len(claude_logs),
            },
            "commands_scanned": {
                "codex": codex_commands_scanned,
                "claude": claude_commands_scanned,
                "total": codex_commands_scanned + claude_commands_scanned,
            },
            "matches": {
                "codex": codex_matches,
                "claude": claude_matches,
                "total": len(records),
            },
        },
        "matches": records,
    }


def main() -> int:
    args = parse_args()
    payload = _build_output(
        scan_root=args.scan_root,
        include_started=args.include_started,
        truncate_command=args.truncate_command,
    )

    indent = None if args.indent <= 0 else args.indent
    rendered = json.dumps(payload, indent=indent, ensure_ascii=False)

    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
