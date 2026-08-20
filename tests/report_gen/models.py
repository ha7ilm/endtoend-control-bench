from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


SignalPayload = list[float] | dict[str, list[float]]


@dataclass
class TraceRecord:
    setup_name: str
    time_sec: list[float]
    ref: SignalPayload
    meas: SignalPayload
    control: list[float]
    disturbance: list[float]
    kpis: dict[str, Any]


@dataclass
class CaseRecord:
    nodeid: str
    module_path: str
    test_name: str
    reason: str
    status: str = "notrun"
    duration_sec: float = 0.0
    failure_text: str | None = None
    trace_records: list[TraceRecord] = field(default_factory=list)
    report_relpath: str = ""
