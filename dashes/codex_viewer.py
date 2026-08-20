#!/usr/bin/env python3
"""Viewer for .logjsonl files from Codex agent runs.

Usage:
    python dashes/codex_viewer.py results/2026-02-22_tesztelodunk/log1.logjsonl
    python dashes/codex_viewer.py results/  # browse directory for .logjsonl files

Auto-starts a Flask server on a free port above 8000, bound to 127.0.0.1.
"""

import json
import os
import socket
import sys
from pathlib import Path

from flask import Flask, render_template_string
from markupsafe import escape

app = Flask(__name__)

# Will be set from CLI args
_LOG_PATH: Path | None = None
_LOG_DIR: Path | None = None


def find_free_port(start: int = 8001) -> int:
    for port in range(start, start + 200):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    raise RuntimeError("No free port found")


def load_events(path: Path) -> list[dict]:
    events = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                events.append(json.loads(line))
    return events


def build_timeline(events: list[dict]) -> list[dict]:
    """Convert raw JSONL events into a timeline of display items."""
    timeline = []
    # Track started items so we can merge start+complete
    started: dict[str, dict] = {}

    for ev in events:
        ev_type = ev.get("type", "")

        if ev_type == "thread.started":
            timeline.append({
                "kind": "meta",
                "label": "Thread Started",
                "detail": ev.get("thread_id", ""),
            })

        elif ev_type == "turn.started":
            timeline.append({
                "kind": "meta",
                "label": "Turn Started",
                "detail": "",
            })

        elif ev_type == "item.started":
            item = ev.get("item", {})
            item_id = item.get("id", "")
            started[item_id] = item

        elif ev_type == "item.completed":
            item = ev.get("item", {})
            item_type = item.get("type", "")
            item_id = item.get("id", "")

            if item_type == "reasoning":
                timeline.append({
                    "kind": "reasoning",
                    "text": item.get("text", ""),
                })

            elif item_type == "agent_message":
                timeline.append({
                    "kind": "message",
                    "text": item.get("text", ""),
                })

            elif item_type == "command_execution":
                timeline.append({
                    "kind": "command",
                    "command": item.get("command", ""),
                    "output": item.get("aggregated_output", ""),
                    "exit_code": item.get("exit_code"),
                    "status": item.get("status", ""),
                })

            elif item_type == "file_change":
                changes = item.get("changes", [])
                timeline.append({
                    "kind": "file_change",
                    "changes": changes,
                    "status": item.get("status", ""),
                })

            elif item_type == "collab_tool_call":
                timeline.append({
                    "kind": "collab_tool_call",
                    "tool": item.get("tool", "?"),
                    "receiver_thread_ids": item.get("receiver_thread_ids", []),
                    "prompt": item.get("prompt"),
                    "agents_states": item.get("agents_states", {}),
                })

            else:
                timeline.append({
                    "kind": "unknown",
                    "raw": item,
                })

            # Remove from started tracker
            started.pop(item_id, None)

    return timeline


def find_logjsonl_files(directory: Path) -> list[Path]:
    files = sorted(directory.rglob("*.logjsonl"))
    return files


# ── HTML Template ──────────────────────────────────────────────────────────

TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{{ title }}</title>
<script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
<style>
  :root {
    --bg: #0d1117;
    --surface: #161b22;
    --surface2: #1c2128;
    --border: #30363d;
    --text: #e6edf3;
    --text-dim: #8b949e;
    --accent: #58a6ff;
    --green: #3fb950;
    --red: #f85149;
    --yellow: #d29922;
    --purple: #bc8cff;
    --orange: #f0883e;
  }
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;
    background: var(--bg);
    color: var(--text);
    line-height: 1.5;
  }
  .header {
    background: var(--surface);
    border-bottom: 1px solid var(--border);
    padding: 16px 24px;
    position: sticky;
    top: 0;
    z-index: 100;
  }
  .header h1 {
    font-size: 18px;
    font-weight: 600;
    color: var(--accent);
  }
  .header .subtitle {
    font-size: 13px;
    color: var(--text-dim);
    margin-top: 2px;
  }
  .container {
    max-width: 960px;
    margin: 0 auto;
    padding: 24px 16px;
  }
  .timeline {
    position: relative;
    padding-left: 32px;
  }
  .timeline::before {
    content: '';
    position: absolute;
    left: 11px;
    top: 0;
    bottom: 0;
    width: 2px;
    background: var(--border);
  }

  .item {
    position: relative;
    margin-bottom: 16px;
  }
  .item::before {
    content: '';
    position: absolute;
    left: -25px;
    top: 10px;
    width: 10px;
    height: 10px;
    border-radius: 50%;
    border: 2px solid var(--border);
    background: var(--bg);
  }

  /* Kind-specific dot colors */
  .item.meta::before     { border-color: var(--text-dim); background: var(--text-dim); width: 6px; height: 6px; left: -23px; top: 12px; }
  .item.reasoning::before { border-color: var(--purple); }
  .item.message::before   { border-color: var(--accent); background: var(--accent); }
  .item.command::before   { border-color: var(--green); }
  .item.command.failed::before { border-color: var(--red); background: var(--red); }
  .item.file_change::before { border-color: var(--orange); background: var(--orange); }
  .item.collab_tool_call::before { border-color: var(--purple); }

  .item-card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 8px;
    overflow: hidden;
  }

  /* Meta items */
  .meta-label {
    padding: 6px 12px;
    font-size: 12px;
    color: var(--text-dim);
    font-style: italic;
  }
  .meta-label span {
    color: var(--text-dim);
    font-family: monospace;
    font-size: 11px;
    margin-left: 8px;
  }

  /* Reasoning */
  .reasoning-content {
    padding: 10px 14px;
    font-size: 13px;
    color: var(--purple);
    font-style: italic;
    border-left: 3px solid var(--purple);
  }

  /* Agent message (rendered markdown) */
  .message-content {
    padding: 12px 16px;
    font-size: 14px;
    word-wrap: break-word;
  }
  .message-content p { margin: 0 0 8px 0; }
  .message-content p:last-child { margin-bottom: 0; }
  .message-content code {
    background: var(--surface2);
    padding: 1px 5px;
    border-radius: 4px;
    font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
    font-size: 13px;
  }
  .message-content pre {
    background: var(--surface2);
    padding: 10px 12px;
    border-radius: 6px;
    overflow-x: auto;
    margin: 8px 0;
  }
  .message-content pre code {
    background: none;
    padding: 0;
  }
  .message-content ul, .message-content ol {
    margin: 6px 0;
    padding-left: 20px;
  }
  .message-content strong { color: #f0f6fc; }
  .message-content a { color: var(--accent); }

  /* Command */
  .cmd-header {
    padding: 8px 12px;
    background: var(--surface2);
    border-bottom: 1px solid var(--border);
    display: flex;
    align-items: center;
    gap: 8px;
  }
  .cmd-icon {
    font-size: 12px;
    color: var(--green);
    font-weight: bold;
  }
  .cmd-text {
    font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
    font-size: 12px;
    color: var(--text);
    word-break: break-all;
    white-space: pre-wrap;
    flex: 1;
  }
  .exit-badge {
    font-size: 11px;
    padding: 1px 6px;
    border-radius: 10px;
    font-weight: 600;
    white-space: nowrap;
  }
  .exit-badge.ok {
    background: rgba(63, 185, 80, 0.15);
    color: var(--green);
  }
  .exit-badge.err {
    background: rgba(248, 81, 73, 0.15);
    color: var(--red);
  }
  .cmd-output {
    padding: 10px 12px;
    font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
    font-size: 12px;
    color: var(--text-dim);
    white-space: pre-wrap;
    word-wrap: break-word;
    max-height: 400px;
    overflow-y: auto;
    line-height: 1.4;
  }
  .cmd-output:empty {
    display: none;
  }
  .cmd-output.collapsed {
    max-height: 80px;
    overflow: hidden;
    position: relative;
  }
  .cmd-output.collapsed::after {
    content: '';
    position: absolute;
    bottom: 0;
    left: 0;
    right: 0;
    height: 40px;
    background: linear-gradient(transparent, var(--surface));
    pointer-events: none;
  }
  .expand-btn {
    display: block;
    width: 100%;
    background: var(--surface2);
    border: none;
    border-top: 1px solid var(--border);
    color: var(--accent);
    font-size: 12px;
    padding: 4px;
    cursor: pointer;
  }
  .expand-btn:hover { background: var(--border); }

  /* File changes */
  .file-change-list {
    padding: 8px 12px;
  }
  .file-change-entry {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 4px 0;
    font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
    font-size: 12px;
  }
  .file-badge {
    font-size: 10px;
    padding: 1px 5px;
    border-radius: 3px;
    font-weight: 600;
    text-transform: uppercase;
  }
  .file-badge.add    { background: rgba(63, 185, 80, 0.15); color: var(--green); }
  .file-badge.modify { background: rgba(88, 166, 255, 0.15); color: var(--accent); }
  .file-badge.delete { background: rgba(248, 81, 73, 0.15); color: var(--red); }

  /* Collab tool call */
  .collab-header {
    padding: 8px 12px;
    background: var(--surface2);
    border-bottom: 1px solid var(--border);
    display: flex;
    align-items: center;
    gap: 8px;
  }
  .collab-tool-badge {
    font-size: 11px;
    padding: 2px 7px;
    border-radius: 10px;
    font-weight: 600;
    background: rgba(188, 140, 255, 0.15);
    color: var(--purple);
  }
  .collab-body {
    padding: 8px 12px;
    font-size: 13px;
    color: var(--text-dim);
  }
  .collab-prompt {
    font-style: italic;
    margin-top: 4px;
    word-wrap: break-word;
  }
  .collab-agent-row {
    display: flex;
    gap: 8px;
    align-items: baseline;
    margin: 4px 0;
  }
  .collab-agent-status {
    font-size: 11px;
    padding: 1px 5px;
    border-radius: 8px;
    font-weight: 600;
    white-space: nowrap;
  }
  .collab-agent-status.completed { background: rgba(63,185,80,.15); color: var(--green); }
  .collab-agent-status.pending_init, .collab-agent-status.pending { background: rgba(210,153,34,.15); color: var(--yellow); }
  .collab-agent-msg {
    font-size: 12px;
    color: var(--text-dim);
    font-style: italic;
    margin-left: 12px;
    word-wrap: break-word;
  }

  /* Unknown */
  .unknown-content {
    padding: 10px 14px;
    font-family: monospace;
    font-size: 12px;
    color: var(--text-dim);
    white-space: pre-wrap;
  }

  /* Item number */
  .item-num {
    position: absolute;
    right: 100%;
    margin-right: 30px;
    top: 8px;
    font-size: 11px;
    color: var(--text-dim);
    font-family: monospace;
    opacity: 0.5;
    white-space: nowrap;
  }

  /* File browser page */
  .file-list {
    list-style: none;
  }
  .file-list li {
    margin-bottom: 8px;
  }
  .file-list a {
    display: block;
    padding: 12px 16px;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 8px;
    color: var(--accent);
    text-decoration: none;
    font-family: monospace;
    font-size: 14px;
    transition: border-color 0.15s;
  }
  .file-list a:hover {
    border-color: var(--accent);
  }
  .file-size {
    color: var(--text-dim);
    font-size: 12px;
    margin-left: 12px;
  }

  /* Stats bar */
  .stats {
    display: flex;
    gap: 16px;
    margin-bottom: 20px;
    flex-wrap: wrap;
  }
  .stat {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 8px 14px;
    font-size: 13px;
  }
  .stat-label {
    color: var(--text-dim);
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }
  .stat-value {
    font-weight: 600;
    font-size: 18px;
    margin-top: 2px;
  }
  .stat-value.purple { color: var(--purple); }
  .stat-value.blue   { color: var(--accent); }
  .stat-value.green  { color: var(--green); }
  .stat-value.orange { color: var(--orange); }
</style>
</head>
<body>

<div class="header">
  <h1>{{ title }}</h1>
  {% if subtitle %}<div class="subtitle">{{ subtitle }}</div>{% endif %}
</div>

<div class="container">

{% if mode == "browse" %}
  <ul class="file-list">
  {% for f in files %}
    <li><a href="/view?path={{ f.path }}">{{ f.relpath }}<span class="file-size">{{ f.size }}</span></a></li>
  {% endfor %}
  </ul>
  {% if not files %}
    <p style="color: var(--text-dim)">No .logjsonl files found in this directory.</p>
  {% endif %}

{% elif mode == "view" %}

  <div class="stats">
    <div class="stat">
      <div class="stat-label">Reasoning</div>
      <div class="stat-value purple">{{ counts.reasoning }}</div>
    </div>
    <div class="stat">
      <div class="stat-label">Messages</div>
      <div class="stat-value blue">{{ counts.message }}</div>
    </div>
    <div class="stat">
      <div class="stat-label">Commands</div>
      <div class="stat-value green">{{ counts.command }}</div>
    </div>
    <div class="stat">
      <div class="stat-label">File Changes</div>
      <div class="stat-value orange">{{ counts.file_change }}</div>
    </div>
  </div>

  <div class="timeline">
  {% for item in timeline %}
    <div class="item {{ item.kind }}{% if item.kind == 'command' and item.get('exit_code') is not none and item.get('exit_code') != 0 %} failed{% endif %}" id="item-{{ loop.index }}">
      <span class="item-num">#{{ loop.index }}</span>

      {% if item.kind == "meta" %}
        <div class="item-card">
          <div class="meta-label">{{ item.label }}{% if item.detail %}<span>{{ item.detail }}</span>{% endif %}</div>
        </div>

      {% elif item.kind == "reasoning" %}
        <div class="item-card">
          <div class="reasoning-content">{{ item.text }}</div>
        </div>

      {% elif item.kind == "message" %}
        <div class="item-card">
          <div class="message-content" data-md>{{ item.text }}</div>
        </div>

      {% elif item.kind == "command" %}
        <div class="item-card">
          <div class="cmd-header">
            <span class="cmd-icon">$</span>
            <span class="cmd-text">{{ item.command }}</span>
            {% if item.exit_code is not none %}
              <span class="exit-badge {{ 'ok' if item.exit_code == 0 else 'err' }}">
                {{ 'exit 0' if item.exit_code == 0 else 'exit ' ~ item.exit_code }}
              </span>
            {% endif %}
          </div>
          {% if item.output %}
          <div class="cmd-output{% if item.output_lines > 6 %} collapsed{% endif %}" id="output-{{ loop.index }}">{{ item.output }}</div>
          {% if item.output_lines > 6 %}
          <button class="expand-btn" onclick="toggleOutput({{ loop.index }})">Show all ({{ item.output_lines }} lines)</button>
          {% endif %}
          {% endif %}
        </div>

      {% elif item.kind == "file_change" %}
        <div class="item-card">
          <div class="file-change-list">
          {% for ch in item.changes %}
            <div class="file-change-entry">
              <span class="file-badge {{ ch.kind }}">{{ ch.kind }}</span>
              <span>{{ ch.path }}</span>
            </div>
          {% endfor %}
          </div>
        </div>

      {% elif item.kind == "collab_tool_call" %}
        <div class="item-card">
          <div class="collab-header">
            <span class="collab-tool-badge">{{ item.tool }}</span>
            {% for rid in item.receiver_thread_ids %}
              <span style="font-family:monospace;font-size:12px;color:var(--text-dim)">→ {{ rid }}</span>
            {% endfor %}
          </div>
          <div class="collab-body">
            {% if item.prompt %}
              <div class="collab-prompt">{{ item.prompt }}</div>
            {% endif %}
            {% for tid, state in item.agents_states.items() %}
              <div class="collab-agent-row">
                <span class="collab-agent-status {{ state.status }}">{{ state.status }}</span>
                <span style="font-family:monospace;font-size:11px;color:var(--text-dim)">{{ tid }}</span>
              </div>
              {% if state.message %}
                <div class="collab-agent-msg">{{ state.message }}</div>
              {% endif %}
            {% endfor %}
          </div>
        </div>

      {% elif item.kind == "unknown" %}
        <div class="item-card">
          <div class="unknown-content">{{ item.raw_json }}</div>
        </div>

      {% endif %}
    </div>
  {% endfor %}
  </div>

{% endif %}

</div>

<script>
function toggleOutput(idx) {
  const el = document.getElementById('output-' + idx);
  const btn = el.nextElementSibling;
  if (el.classList.contains('collapsed')) {
    el.classList.remove('collapsed');
    btn.textContent = 'Collapse';
  } else {
    el.classList.add('collapsed');
    const lines = el.textContent.split('\n').length;
    btn.textContent = 'Show all (' + lines + ' lines)';
  }
}

// Render markdown in agent messages
document.querySelectorAll('[data-md]').forEach(el => {
  const raw = el.textContent;
  el.innerHTML = marked.parse(raw);
});
</script>

</body>
</html>"""


@app.route("/")
def index():
    if _LOG_PATH and _LOG_PATH.is_file():
        return view_file(_LOG_PATH)

    if _LOG_DIR:
        files = find_logjsonl_files(_LOG_DIR)
        file_infos = []
        for f in files:
            try:
                size = f.stat().st_size
                if size < 1024:
                    size_str = f"{size} B"
                elif size < 1024 * 1024:
                    size_str = f"{size / 1024:.1f} KB"
                else:
                    size_str = f"{size / (1024*1024):.1f} MB"
            except OSError:
                size_str = "?"
            file_infos.append({
                "path": str(f),
                "relpath": str(f.relative_to(_LOG_DIR)),
                "size": size_str,
            })
        return render_template_string(
            TEMPLATE,
            title="Codex Log Browser",
            subtitle=str(_LOG_DIR),
            mode="browse",
            files=file_infos,
        )

    return "No log file or directory specified", 400


@app.route("/view")
def view_from_query():
    from flask import request
    path = request.args.get("path", "")
    if not path:
        return "Missing path parameter", 400
    p = Path(path)
    if not p.is_file():
        return f"File not found: {path}", 404
    return view_file(p)


def view_file(path: Path) -> str:
    events = load_events(path)
    timeline = build_timeline(events)

    # Prepare output for template
    counts = {"reasoning": 0, "message": 0, "command": 0, "file_change": 0}
    for item in timeline:
        k = item["kind"]
        if k in counts:
            counts[k] += 1
        if k == "command" and item.get("output"):
            item["output_lines"] = item["output"].count("\n") + 1
        elif k == "command":
            item["output_lines"] = 0
        if k == "unknown":
            item["raw_json"] = json.dumps(item["raw"], indent=2)

    return render_template_string(
        TEMPLATE,
        title=path.name,
        subtitle=str(path),
        mode="view",
        timeline=timeline,
        counts=counts,
    )


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    target = Path(sys.argv[1])
    global _LOG_PATH, _LOG_DIR

    if target.is_file():
        _LOG_PATH = target.resolve()
    elif target.is_dir():
        _LOG_DIR = target.resolve()
    else:
        print(f"Error: {target} is not a file or directory")
        sys.exit(1)

    port = find_free_port()
    print(f"Serving on http://127.0.0.1:{port}")
    app.run(host="127.0.0.1", port=port, debug=False)


if __name__ == "__main__":
    main()
