from __future__ import annotations

from typing import Any

from .models import TraceRecord


def build_signal_figure(trace: TraceRecord) -> dict[str, Any]:
    """Return Plotly figure payload for reference and measurement signals."""
    data: list[dict[str, Any]] = []
    t = trace.time_sec

    if isinstance(trace.ref, dict) and isinstance(trace.meas, dict):
        channel_keys = sorted(set(trace.ref) | set(trace.meas))
        for key in channel_keys:
            if key in trace.ref:
                data.append(
                    {
                        "x": t,
                        "y": trace.ref[key],
                        "name": f"ref.{key}",
                        "mode": "lines",
                        "line": {"dash": "dash"},
                    }
                )
            if key in trace.meas:
                data.append(
                    {
                        "x": t,
                        "y": trace.meas[key],
                        "name": f"meas.{key}",
                        "mode": "lines",
                    }
                )
    else:
        data.append(
            {
                "x": t,
                "y": trace.ref,
                "name": "ref",
                "mode": "lines",
                "line": {"dash": "dash"},
            }
        )
        data.append(
            {
                "x": t,
                "y": trace.meas,
                "name": "meas",
                "mode": "lines",
            }
        )

    layout = {
        "title": "Reference and Measurement",
        "xaxis": {"title": "Time [s]"},
        "yaxis": {"title": "Signal"},
        "legend": {"orientation": "h"},
        "margin": {"l": 60, "r": 25, "t": 50, "b": 50},
    }
    return {"data": data, "layout": layout}


def build_input_figure(trace: TraceRecord) -> dict[str, Any]:
    """Return Plotly figure payload for control and disturbance signals."""
    t = trace.time_sec
    data = [
        {
            "x": t,
            "y": trace.control,
            "name": "control",
            "mode": "lines",
        },
        {
            "x": t,
            "y": trace.disturbance,
            "name": "disturbance",
            "mode": "lines",
            "line": {"dash": "dot"},
        },
    ]

    layout = {
        "title": "Control and Disturbance",
        "xaxis": {"title": "Time [s]"},
        "yaxis": {"title": "Signal"},
        "legend": {"orientation": "h"},
        "margin": {"l": 60, "r": 25, "t": 50, "b": 50},
    }
    return {"data": data, "layout": layout}
