from __future__ import annotations

import hashlib
import html
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from .models import CaseRecord
from .plotly_embed import build_input_figure, build_signal_figure

PLOTLY_CDN = "https://cdn.plot.ly/plotly-2.35.2.min.js"


def _safe_case_filename(nodeid: str) -> str:
    safe = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in nodeid)
    digest = hashlib.sha1(nodeid.encode("utf-8")).hexdigest()[:10]
    trimmed = safe[:130]
    return f"{trimmed}_{digest}.html"


def _status_counts(cases: list[CaseRecord]) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    for case in cases:
        counts[case.status] += 1
    return counts


def _flatten_kpis(kpis: dict[str, object], prefix: str = "") -> list[tuple[str, object]]:
    rows: list[tuple[str, object]] = []
    for key in sorted(kpis):
        full_key = f"{prefix}.{key}" if prefix else str(key)
        value = kpis[key]
        if isinstance(value, dict):
            rows.extend(_flatten_kpis(value, prefix=full_key))
            continue
        rows.append((full_key, value))
    return rows


def _case_page_html(case: CaseRecord) -> str:
    escaped_reason = html.escape(case.reason)
    escaped_nodeid = html.escape(case.nodeid)
    escaped_module = html.escape(case.module_path)

    failure_block = ""
    if case.failure_text:
        failure_block = (
            "<section><h2>Failure Details</h2>"
            f"<pre>{html.escape(case.failure_text)}</pre></section>"
        )

    trace_blocks: list[str] = []
    plot_specs: list[tuple[str, dict, dict]] = []
    for idx, trace in enumerate(case.trace_records, start=1):
        signal_div_id = f"signal-plot-{idx}"
        input_div_id = f"input-plot-{idx}"
        signal_fig = build_signal_figure(trace)
        input_fig = build_input_figure(trace)
        plot_specs.append((signal_div_id, signal_fig["data"], signal_fig["layout"]))
        plot_specs.append((input_div_id, input_fig["data"], input_fig["layout"]))

        kpi_rows = "".join(
            (
                f"<tr><td>{html.escape(str(key))}</td>"
                f"<td>{html.escape(str(value))}</td></tr>"
            )
            for key, value in _flatten_kpis(trace.kpis)
        )

        trace_blocks.append(
            "<section class='trace-block'>"
            f"<h3>Trace {idx}: {html.escape(trace.setup_name)}</h3>"
            f"<div class='plot' id='{signal_div_id}'></div>"
            f"<div class='plot' id='{input_div_id}'></div>"
            "<h4>KPIs</h4>"
            f"<table><thead><tr><th>Metric</th><th>Value</th></tr></thead><tbody>{kpi_rows}</tbody></table>"
            "</section>"
        )

    if trace_blocks:
        traces_html = "<section><h2>Signals</h2>" + "".join(trace_blocks) + "</section>"
    else:
        traces_html = (
            "<section><h2>Signals</h2>"
            "<p>No signals captured for this test case.</p>"
            "</section>"
        )

    plot_script = ""
    if plot_specs:
        lines = [
            "<script src='{}'></script>".format(PLOTLY_CDN),
            "<script>",
        ]
        for div_id, data, layout in plot_specs:
            lines.append(
                "Plotly.newPlot(" + json.dumps(div_id) + ", "
                + json.dumps(data)
                + ", "
                + json.dumps(layout)
                + ", {responsive: true});"
            )
        lines.append("</script>")
        plot_script = "\n".join(lines)

    return f"""<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\">
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">
  <title>{escaped_nodeid}</title>
  <style>
    body {{ font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, sans-serif; margin: 0; padding: 20px; color: #17202a; background: #f8fafc; }}
    h1 {{ margin-top: 0; font-size: 1.2rem; }}
    h2 {{ margin-bottom: 8px; }}
    section {{ background: #ffffff; border: 1px solid #dce4ec; border-radius: 10px; padding: 14px; margin-bottom: 14px; }}
    .status {{ display: inline-block; padding: 2px 10px; border-radius: 999px; font-size: 0.86rem; background: #e5e7eb; text-transform: uppercase; }}
    .status.passed {{ background: #dcfce7; color: #166534; }}
    .status.failed, .status.error {{ background: #fee2e2; color: #991b1b; }}
    .status.skipped {{ background: #fef3c7; color: #92400e; }}
    .plot {{ width: 100%; height: 360px; margin: 8px 0 16px; }}
    table {{ border-collapse: collapse; width: 100%; }}
    th, td {{ border: 1px solid #dce4ec; padding: 6px 8px; text-align: left; }}
    pre {{ white-space: pre-wrap; overflow-wrap: anywhere; background: #0f172a; color: #e2e8f0; padding: 10px; border-radius: 8px; }}
  </style>
</head>
<body>
  <h1>{escaped_nodeid}</h1>
  <section>
    <div><strong>Module:</strong> {escaped_module}</div>
    <div><strong>Status:</strong> <span class=\"status {html.escape(case.status)}\">{html.escape(case.status)}</span></div>
    <div><strong>Duration:</strong> {case.duration_sec:.3f} s</div>
  </section>
  <section>
    <h2>Reason</h2>
    <p>{escaped_reason}</p>
  </section>
  {failure_block}
  {traces_html}
  {plot_script}
</body>
</html>
"""


def _index_html(cases: list[CaseRecord], generated_at: str) -> str:
    by_module: dict[str, list[CaseRecord]] = defaultdict(list)
    for case in cases:
        by_module[case.module_path].append(case)

    for entries in by_module.values():
        entries.sort(key=lambda record: record.nodeid)

    nav_parts: list[str] = []
    for module in sorted(by_module):
        entries = by_module[module]
        links = "".join(
            (
                "<li><a class='case-link status-{}' href='{}' target='case-frame'>{}</a></li>"
            ).format(
                html.escape(entry.status),
                html.escape(entry.report_relpath),
                html.escape(entry.nodeid.split("::", 1)[-1]),
            )
            for entry in entries
        )
        nav_parts.append(
            f"<details open><summary>{html.escape(module)} ({len(entries)})</summary><ul>{links}</ul></details>"
        )

    counts = _status_counts(cases)
    summary = (
        f"Total: {len(cases)} | "
        f"Passed: {counts.get('passed', 0)} | "
        f"Failed: {counts.get('failed', 0)} | "
        f"Errors: {counts.get('error', 0)} | "
        f"Skipped: {counts.get('skipped', 0)}"
    )

    initial_src = html.escape(cases[0].report_relpath) if cases else "about:blank"

    return f"""<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\">
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">
  <title>Test Report Index</title>
  <link rel=\"stylesheet\" href=\"https://cdn.jsdelivr.net/npm/split.js@1.6.5/dist/split.min.css\">
  <style>
    body {{ margin: 0; font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, sans-serif; color: #17202a; }}
    .layout {{ display: flex; height: 100vh; overflow: hidden; }}
    .sidebar {{ background: #f8fafc; overflow-y: auto; overflow-x: hidden; padding: 14px; box-sizing: border-box; min-width: 160px; }}
    .sidebar h1 {{ margin: 0 0 8px; font-size: 1.1rem; }}
    .summary {{ margin-bottom: 10px; font-size: 0.9rem; color: #334155; word-break: break-word; }}
    details {{ margin-bottom: 8px; border: 1px solid #dce4ec; border-radius: 8px; background: #fff; padding: 6px 8px; }}
    summary {{ font-weight: 600; cursor: pointer; word-break: break-word; }}
    ul {{ list-style: none; padding: 0 0 0 8px; margin: 8px 0 0; }}
    li {{ margin: 6px 0; }}
    .case-link {{ text-decoration: none; color: #1f2937; font-size: 0.9rem; word-break: break-word; display: block; }}
    .status-passed::before {{ content: 'PASS '; color: #15803d; font-weight: 700; }}
    .status-failed::before {{ content: 'FAIL '; color: #b91c1c; font-weight: 700; }}
    .status-error::before {{ content: 'ERROR '; color: #b91c1c; font-weight: 700; }}
    .status-skipped::before {{ content: 'SKIP '; color: #a16207; font-weight: 700; }}
    .gutter {{ background: #dce4ec; transition: background 0.15s; }}
    .gutter:hover, .gutter-dragging {{ background: #94a3b8 !important; }}
    #main-pane {{ overflow: hidden; min-width: 200px; }}
    .viewer {{ width: 100%; height: 100%; border: 0; }}
    .topnote {{ font-size: 0.8rem; color: #64748b; margin-bottom: 12px; }}
  </style>
</head>
<body>
  <div class=\"layout\">
    <aside class=\"sidebar\" id=\"sidebar\">
      <h1>Pytest HTML Reports</h1>
      <div class=\"summary\">{html.escape(summary)}</div>
      <div class=\"topnote\">Generated at {html.escape(generated_at)} UTC</div>
      {''.join(nav_parts)}
    </aside>
    <main id=\"main-pane\">
      <iframe class=\"viewer\" name=\"case-frame\" src=\"{initial_src}\"></iframe>
    </main>
  </div>
  <script src=\"https://cdn.jsdelivr.net/npm/split.js@1.6.5/dist/split.min.js\"></script>
  <script>
    Split(['#sidebar', '#main-pane'], {{
      sizes: [27, 73],
      minSize: [160, 200],
      gutterSize: 6,
      cursor: 'col-resize',
      onDragStart: function() {{
        document.querySelector('.gutter').classList.add('gutter-dragging');
      }},
      onDragEnd: function() {{
        document.querySelector('.gutter').classList.remove('gutter-dragging');
      }},
    }});
  </script>
</body>
</html>
"""


def render_reports(output_root: Path, cases: list[CaseRecord]) -> None:
    case_dir = output_root / "cases"
    case_dir.mkdir(parents=True, exist_ok=True)

    for case in cases:
        filename = _safe_case_filename(case.nodeid)
        case.report_relpath = f"cases/{filename}"
        content = _case_page_html(case)
        (case_dir / filename).write_text(content, encoding="utf-8")

    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    index_html = _index_html(cases, generated_at=generated_at)
    (output_root / "index.html").write_text(index_html, encoding="utf-8")
