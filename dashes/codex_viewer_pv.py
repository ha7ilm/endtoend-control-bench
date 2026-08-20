#!/usr/bin/env python3
"""Terminal viewer for .logjsonl Codex agent logs.

Reads from stdin or a file, rendering events with rich formatting
for reasoning, messages, commands, and file changes.

Usage:
    cat log.logjsonl | python dashes/codex_viewer_pv.py
    some_process | python dashes/codex_viewer_pv.py
    python dashes/codex_viewer_pv.py results/log1.logjsonl

Requires: pip install rich
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.rule import Rule
from rich.syntax import Syntax
from rich.text import Text
from rich.theme import Theme

THEME = Theme({
    "reasoning": "italic #bc8cff",
    "meta": "dim italic",
    "exit_ok": "bold green",
    "exit_err": "bold red",
    "cmd_prompt": "bold green",
    "file_add": "bold green",
    "file_modify": "bold #58a6ff",
    "file_delete": "bold red",
    "item_num": "dim",
})

console = Console(theme=THEME)

_unfold = False
_FOLD_LINES = 3

# ── Rendering ──────────────────────────────────────────────────────────────


def render_meta(label: str, detail: str) -> None:
    text = f"{label}"
    if detail:
        text += f"  {detail}"
    console.print(Rule(text, style="dim"))


def render_reasoning(text: str, item_num: int) -> None:
    prefix = Text(f"#{item_num} ", style="item_num")
    content = Text(text, style="reasoning")
    console.print(Text.assemble(prefix, "  ", content))


def render_message(text: str, item_num: int) -> None:
    md = Markdown(text)
    console.print(
        Panel(
            md,
            title=f"[bold #58a6ff]Agent[/]",
            title_align="left",
            subtitle=f"[item_num]#{item_num}[/]",
            subtitle_align="right",
            border_style="#58a6ff",
            padding=(0, 1),
        )
    )


def _extract_shell_command(full_cmd: str) -> str:
    """Strip the /usr/bin/zsh -lc wrapper if present, returning the inner command."""
    for prefix in ("/usr/bin/zsh -lc ", "/bin/bash -lc ", "/bin/sh -c "):
        if full_cmd.startswith(prefix):
            inner = full_cmd[len(prefix):]
            # Strip outer quotes
            if (inner.startswith("'") and inner.endswith("'")) or (
                inner.startswith('"') and inner.endswith('"')
            ):
                inner = inner[1:-1]
            return inner
    return full_cmd


def render_command(
    command: str,
    output: str,
    exit_code: int | None,
    status: str,
    item_num: int,
) -> None:
    inner_cmd = _extract_shell_command(command)

    # Exit code badge
    if exit_code is not None:
        if exit_code == 0:
            badge = Text(" exit 0 ", style="exit_ok")
        else:
            badge = Text(f" exit {exit_code} ", style="exit_err")
    elif status == "in_progress":
        badge = Text(" running... ", style="bold yellow")
    else:
        badge = Text("")

    # Command line (fold multi-line commands like heredocs)
    cmd_lines = inner_cmd.split("\n")
    if not _unfold and len(cmd_lines) > _FOLD_LINES:
        inner_display = "\n".join(cmd_lines[:_FOLD_LINES]) + f"\n... ({len(cmd_lines) - _FOLD_LINES} more lines)"
    else:
        inner_display = inner_cmd

    prompt = Text("$ ", style="cmd_prompt")
    cmd_text = Text(inner_display)
    header = Text.assemble(prompt, cmd_text, "  ", badge)

    # Output
    parts = [header]
    if output and output.strip():
        lines = output.rstrip("\n").split("\n")
        if _unfold:
            max_lines = 60
        else:
            max_lines = _FOLD_LINES
        if len(lines) > max_lines:
            shown = "\n".join(lines[:max_lines])
            shown += f"\n... ({len(lines) - max_lines} more lines)"
        else:
            shown = "\n".join(lines)
        parts.append(Text(shown, style="dim"))

    content = Text("\n").join(parts)
    border = "#3fb950" if exit_code == 0 or exit_code is None else "#f85149"
    console.print(
        Panel(
            content,
            title=f"[bold {border}]Command[/]",
            title_align="left",
            subtitle=f"[item_num]#{item_num}[/]",
            subtitle_align="right",
            border_style=border,
            padding=(0, 1),
        )
    )


def render_file_change(changes: list[dict], item_num: int) -> None:
    lines = []
    for ch in changes:
        kind = ch.get("kind", "?")
        path = ch.get("path", "?")
        style = {"add": "file_add", "modify": "file_modify", "delete": "file_delete"}.get(
            kind, ""
        )
        badge = Text(f" {kind.upper()} ", style=style)
        lines.append(Text.assemble(badge, " ", Text(path)))

    content = Text("\n").join(lines) if lines else Text("(no changes listed)")
    console.print(
        Panel(
            content,
            title="[bold #f0883e]File Changes[/]",
            title_align="left",
            subtitle=f"[item_num]#{item_num}[/]",
            subtitle_align="right",
            border_style="#f0883e",
            padding=(0, 1),
        )
    )


def render_collab_tool_call(item: dict, item_num: int) -> None:
    tool = item.get("tool", "?")
    receiver_ids = item.get("receiver_thread_ids", [])
    prompt = item.get("prompt")
    agents_states = item.get("agents_states", {})

    if tool == "spawn_agent":
        title = "[bold #bc8cff]Spawn Agent[/]"
        border = "#bc8cff"
        parts: list[Text] = []
        for rid in receiver_ids:
            parts.append(Text(f"→ {rid}", style="dim"))
        if prompt:
            prompt_display = prompt if len(prompt) <= 200 else prompt[:197] + "..."
            parts.append(Text(f"Prompt: {prompt_display}", style="italic"))
    elif tool == "wait":
        title = "[bold #8b949e]Agent Wait[/]"
        border = "#8b949e"
        parts = []
        for tid, state in agents_states.items():
            st = state.get("status", "?")
            msg = state.get("message") or ""
            badge_style = "bold green" if st == "completed" else "bold yellow"
            parts.append(Text.assemble(Text(f"[{st}] ", style=badge_style), Text(tid, style="dim")))
            if msg:
                msg_display = msg if len(msg) <= 200 else msg[:197] + "..."
                parts.append(Text(f"  {msg_display}", style="dim italic"))
    else:
        title = f"[bold yellow]Collab: {tool}[/]"
        border = "yellow"
        parts = [Text(f"tool={tool}", style="dim")]

    content = Text("\n").join(parts) if parts else Text("(no details)")
    console.print(
        Panel(
            content,
            title=title,
            title_align="left",
            subtitle=f"[item_num]#{item_num}[/]",
            subtitle_align="right",
            border_style=border,
            padding=(0, 1),
        )
    )


def render_unknown(raw: dict, item_num: int) -> None:
    console.print(
        Panel(
            Syntax(json.dumps(raw, indent=2), "json", theme="monokai"),
            title="[bold yellow]Unknown Item[/]",
            title_align="left",
            subtitle=f"[item_num]#{item_num}[/]",
            subtitle_align="right",
            border_style="yellow",
            padding=(0, 1),
        )
    )


# ── Event Processing ──────────────────────────────────────────────────────

_item_counter = 0


def process_event(ev: dict) -> None:
    global _item_counter
    ev_type = ev.get("type", "")

    if ev_type == "thread.started":
        render_meta("Thread Started", ev.get("thread_id", ""))

    elif ev_type == "turn.started":
        render_meta("Turn Started", "")

    elif ev_type == "item.started":
        # We only show started for commands (as a "running" indicator)
        item = ev.get("item", {})
        if item.get("type") == "command_execution":
            _item_counter += 1
            render_command(
                command=item.get("command", ""),
                output="",
                exit_code=None,
                status="in_progress",
                item_num=_item_counter,
            )

    elif ev_type == "item.completed":
        item = ev.get("item", {})
        item_type = item.get("type", "")
        _item_counter += 1

        if item_type == "reasoning":
            render_reasoning(item.get("text", ""), _item_counter)

        elif item_type == "agent_message":
            render_message(item.get("text", ""), _item_counter)

        elif item_type == "command_execution":
            render_command(
                command=item.get("command", ""),
                output=item.get("aggregated_output", ""),
                exit_code=item.get("exit_code"),
                status=item.get("status", ""),
                item_num=_item_counter,
            )

        elif item_type == "file_change":
            render_file_change(item.get("changes", []), _item_counter)

        elif item_type == "collab_tool_call":
            render_collab_tool_call(item, _item_counter)

        else:
            render_unknown(item, _item_counter)


# ── Stream Processing ─────────────────────────────────────────────────────


def process_stream(stream) -> None:
    """Read JSONL lines from a stream and render each event."""
    for line in stream:
        line = line.strip()
        if line:
            try:
                ev = json.loads(line)
                process_event(ev)
            except json.JSONDecodeError as e:
                console.print(f"[red]JSON error:[/] {e}", style="dim")


# ── Main ──────────────────────────────────────────────────────────────────


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="Terminal viewer for .logjsonl Codex agent logs. "
        "Reads from a file argument or stdin.",
    )
    parser.add_argument(
        "file", type=Path, nargs="?", default=None, help="Path to .logjsonl file (omit to read stdin)"
    )
    parser.add_argument(
        "--unfold", action="store_true",
        help="Show full command output and file contents instead of folding after 3 lines",
    )
    args = parser.parse_args()

    global _unfold
    _unfold = args.unfold

    if args.file:
        if not args.file.is_file():
            console.print(f"[red]Error:[/] {args.file} not found")
            sys.exit(1)
        console.print(
            Rule(f"[bold #58a6ff]{args.file.name}[/]  [dim]{args.file}[/]")
        )
        console.print()
        stream = open(args.file)
    else:
        stream = sys.stdin

    try:
        process_stream(stream)
    except KeyboardInterrupt:
        console.print()
        console.print(Rule("[dim]interrupted[/]"))
    finally:
        if stream is not sys.stdin:
            stream.close()

    console.print()
    console.print(Rule("[dim]end of log[/]"))


if __name__ == "__main__":
    main()
