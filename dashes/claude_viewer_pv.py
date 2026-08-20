#!/usr/bin/env python3
"""Terminal viewer for Claude JSONL agent logs.

Reads from stdin or a file, rendering events with rich formatting
for reasoning, messages, tool calls/results, and final summaries.

Usage:
    cat log.jsonl | python dashes/claude_viewer_pv.py
    python dashes/claude_viewer_pv.py results/session.jsonl

Requires: pip install rich
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

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
    "tool_ok": "bold #3fb950",
    "tool_err": "bold #f85149",
    "item_num": "dim",
})

console = Console(theme=THEME)

_unfold = False
_FOLD_LINES = 3


# ── Helpers ───────────────────────────────────────────────────────────────

def _fold_text(text: str, max_lines: int) -> str:
    lines = text.splitlines()
    if _unfold or len(lines) <= max_lines:
        return text
    shown = "\n".join(lines[:max_lines])
    return f"{shown}\n... ({len(lines) - max_lines} more lines)"


def _value_to_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, indent=2, ensure_ascii=False)
    except TypeError:
        return str(value)


def _extract_shell_command(full_cmd: str) -> str:
    """Strip common shell wrappers, returning the inner command if present."""
    for prefix in ("/usr/bin/zsh -lc ", "/bin/bash -lc ", "/bin/sh -c "):
        if full_cmd.startswith(prefix):
            inner = full_cmd[len(prefix):]
            if (inner.startswith("'") and inner.endswith("'")) or (
                inner.startswith('"') and inner.endswith('"')
            ):
                inner = inner[1:-1]
            return inner
    return full_cmd


# ── Rendering ─────────────────────────────────────────────────────────────

def render_meta(label: str, detail: str) -> None:
    text = label
    if detail:
        text += f"  {detail}"
    console.print(Rule(text, style="dim"))


def render_reasoning(text: str, item_num: int) -> None:
    prefix = Text(f"#{item_num} ", style="item_num")
    content = Text(_fold_text(text, 24), style="reasoning")
    console.print(Text.assemble(prefix, "  ", content))


def render_message(text: str, item_num: int, title: str = "[bold #58a6ff]Assistant[/]") -> None:
    md = Markdown(_fold_text(text, 120))
    console.print(
        Panel(
            md,
            title=title,
            title_align="left",
            subtitle=f"[item_num]#{item_num}[/]",
            subtitle_align="right",
            border_style="#58a6ff",
            padding=(0, 1),
        )
    )


def render_command(
    command: str,
    output: str,
    exit_code: int | None,
    status: str,
    item_num: int,
    description: str | None = None,
) -> None:
    inner_cmd = _extract_shell_command(command)

    if exit_code is not None:
        badge = Text(" exit 0 ", style="exit_ok") if exit_code == 0 else Text(f" exit {exit_code} ", style="exit_err")
    elif status == "in_progress":
        badge = Text(" running... ", style="bold yellow")
    else:
        badge = Text("")

    cmd_lines = inner_cmd.split("\n")
    if not _unfold and len(cmd_lines) > _FOLD_LINES:
        inner_display = "\n".join(cmd_lines[:_FOLD_LINES]) + f"\n... ({len(cmd_lines) - _FOLD_LINES} more lines)"
    else:
        inner_display = inner_cmd

    prompt = Text("$ ", style="cmd_prompt")
    cmd_text = Text(inner_display)
    header = Text.assemble(prompt, cmd_text, "  ", badge)

    parts = [header]
    if description:
        parts.append(Text(f"desc: {description}", style="dim italic"))
    if output and output.strip():
        shown = _fold_text(output.rstrip("\n"), 60 if _unfold else _FOLD_LINES)
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


def render_tool_use(tool_name: str, tool_id: str, tool_input: Any, item_num: int) -> None:
    input_text = _value_to_text(tool_input)
    shown = _fold_text(input_text, 30 if _unfold else _FOLD_LINES)
    body = Text.assemble(
        Text("id: ", style="meta"),
        Text(tool_id or "(none)", style="bold"),
        Text("\ninput:\n", style="meta"),
        Text(shown, style="dim"),
    )
    console.print(
        Panel(
            body,
            title=f"[bold #bc8cff]Tool Use: {tool_name}[/]",
            title_align="left",
            subtitle=f"[item_num]#{item_num}[/]",
            subtitle_align="right",
            border_style="#bc8cff",
            padding=(0, 1),
        )
    )


def render_tool_result(tool_use_id: str, content: Any, is_error: bool, item_num: int) -> None:
    status_text = Text("ERROR", style="tool_err") if is_error else Text("OK", style="tool_ok")
    content_text = _value_to_text(content)
    shown = _fold_text(content_text, 30 if _unfold else _FOLD_LINES)
    body = Text.assemble(
        Text("tool_use_id: ", style="meta"),
        Text(tool_use_id or "(unknown)", style="bold"),
        Text("\nstatus: ", style="meta"),
        status_text,
        Text("\ncontent:\n", style="meta"),
        Text(shown, style="dim"),
    )
    border = "#f85149" if is_error else "#3fb950"
    console.print(
        Panel(
            body,
            title="[bold #8b949e]Tool Result[/]",
            title_align="left",
            subtitle=f"[item_num]#{item_num}[/]",
            subtitle_align="right",
            border_style=border,
            padding=(0, 1),
        )
    )


def render_final_result(ev: dict[str, Any], item_num: int) -> None:
    subtype = ev.get("subtype", "")
    is_error = bool(ev.get("is_error", False))
    duration_ms = ev.get("duration_ms")
    num_turns = ev.get("num_turns")
    result_text = _value_to_text(ev.get("result", ""))
    shown_result = _fold_text(result_text, 60 if _unfold else _FOLD_LINES)

    status = Text("error", style="tool_err") if is_error else Text("success", style="tool_ok")
    header = Text.assemble(
        Text("subtype: ", style="meta"),
        Text(str(subtype)),
        Text("  status: ", style="meta"),
        status,
        Text("  duration_ms: ", style="meta"),
        Text(str(duration_ms)),
        Text("  turns: ", style="meta"),
        Text(str(num_turns)),
    )
    body = Text("\n").join([header, Text(shown_result)])
    border = "#f85149" if is_error else "#3fb950"
    console.print(
        Panel(
            body,
            title="[bold #58a6ff]Run Result[/]",
            title_align="left",
            subtitle=f"[item_num]#{item_num}[/]",
            subtitle_align="right",
            border_style=border,
            padding=(0, 1),
        )
    )

    denials = ev.get("permission_denials", [])
    if denials:
        lines = []
        for denial in denials:
            tool_name = denial.get("tool_name", "?")
            tool_input = denial.get("tool_input", {})
            target = ""
            if isinstance(tool_input, dict):
                target = str(tool_input.get("file_path") or tool_input.get("command") or "")
            lines.append(f"- {tool_name}: {target}")
        txt = _fold_text("\n".join(lines), 30 if _unfold else _FOLD_LINES)
        console.print(
            Panel(
                Text(txt, style="dim"),
                title="[bold #f85149]Permission Denials[/]",
                title_align="left",
                border_style="#f85149",
                padding=(0, 1),
            )
        )


def render_unknown(raw: Any, item_num: int) -> None:
    console.print(
        Panel(
            Syntax(_value_to_text(raw), "json", theme="monokai"),
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


def _next_item() -> int:
    global _item_counter
    _item_counter += 1
    return _item_counter


def _process_assistant_event(ev: dict[str, Any]) -> None:
    message = ev.get("message", {})
    if not isinstance(message, dict):
        render_unknown(ev, _next_item())
        return

    content_items = message.get("content", [])
    if not isinstance(content_items, list):
        render_message(_value_to_text(content_items), _next_item())
        return

    for c in content_items:
        if not isinstance(c, dict):
            render_unknown(c, _next_item())
            continue

        ctype = c.get("type")
        if ctype == "thinking":
            render_reasoning(_value_to_text(c.get("thinking", "")), _next_item())
        elif ctype == "text":
            render_message(_value_to_text(c.get("text", "")), _next_item())
        elif ctype == "tool_use":
            name = _value_to_text(c.get("name", "tool"))
            tool_id = _value_to_text(c.get("id", ""))
            tool_input = c.get("input", {})
            if name == "Bash" and isinstance(tool_input, dict):
                cmd = _value_to_text(tool_input.get("command", ""))
                desc = _value_to_text(tool_input.get("description", "")) or None
                render_command(
                    command=cmd,
                    output="",
                    exit_code=None,
                    status="in_progress",
                    item_num=_next_item(),
                    description=desc,
                )
            else:
                render_tool_use(name, tool_id, tool_input, _next_item())
        else:
            render_unknown(c, _next_item())


def _process_user_event(ev: dict[str, Any]) -> None:
    message = ev.get("message", {})
    if not isinstance(message, dict):
        render_unknown(ev, _next_item())
        return

    content_items = message.get("content", [])
    if not isinstance(content_items, list):
        render_message(_value_to_text(content_items), _next_item(), title="[bold #f2cc60]User[/]")
        return

    for c in content_items:
        if not isinstance(c, dict):
            render_unknown(c, _next_item())
            continue

        ctype = c.get("type")
        if ctype == "tool_result":
            render_tool_result(
                tool_use_id=_value_to_text(c.get("tool_use_id", "")),
                content=c.get("content", ""),
                is_error=bool(c.get("is_error", False)),
                item_num=_next_item(),
            )
        else:
            render_message(_value_to_text(c), _next_item(), title="[bold #f2cc60]User[/]")


def process_event(ev: dict[str, Any]) -> None:
    ev_type = ev.get("type", "")

    if ev_type == "system":
        subtype = ev.get("subtype", "")
        label = "System Init" if subtype == "init" else "System"
        fields = []
        for key in ("model", "cwd", "session_id", "permissionMode"):
            val = ev.get(key)
            if val:
                fields.append(f"{key}={val}")
        render_meta(label, "  ".join(fields))

    elif ev_type == "assistant":
        _process_assistant_event(ev)

    elif ev_type == "user":
        _process_user_event(ev)

    elif ev_type == "rate_limit_event":
        info = ev.get("rate_limit_info", {})
        if isinstance(info, dict):
            status = info.get("status", "")
            reset = info.get("resetsAt", "")
            rl_type = info.get("rateLimitType", "")
            detail = f"status={status}  resetsAt={reset}  type={rl_type}"
        else:
            detail = _value_to_text(info)
        render_meta("Rate Limit", detail)

    elif ev_type == "result":
        render_final_result(ev, _next_item())

    else:
        render_unknown(ev, _next_item())


# ── Stream Processing ─────────────────────────────────────────────────────

def process_stream(stream) -> None:
    """Read JSONL lines from a stream and render each event."""
    for line in stream:
        line = line.strip()
        if not line:
            continue
        try:
            ev = json.loads(line)
        except json.JSONDecodeError as exc:
            console.print(f"[red]JSON error:[/] {exc}", style="dim")
            continue
        if not isinstance(ev, dict):
            render_unknown(ev, _next_item())
            continue
        process_event(ev)


# ── Main ──────────────────────────────────────────────────────────────────

def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="Terminal viewer for Claude JSONL logs. Reads from a file argument or stdin.",
    )
    parser.add_argument(
        "file",
        type=Path,
        nargs="?",
        default=None,
        help="Path to .jsonl file (omit to read stdin)",
    )
    parser.add_argument(
        "--unfold",
        action="store_true",
        help="Show full command output and long payloads instead of folding",
    )
    args = parser.parse_args()

    global _unfold
    _unfold = args.unfold

    if args.file:
        if not args.file.is_file():
            console.print(f"[red]Error:[/] {args.file} not found")
            sys.exit(1)
        console.print(Rule(f"[bold #58a6ff]{args.file.name}[/]  [dim]{args.file}[/]"))
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
