from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any, Callable

import numpy as np
import pytest

from controlserver.session import SimulationTrace

from .models import CaseRecord, TraceRecord
from .reason_registry import ReasonRegistry
from .render_html import render_reports


class ReportPlugin:
    """Pytest plugin that emits per-test HTML reports when --report is enabled."""

    def __init__(self, config: pytest.Config) -> None:
        self._config = config
        self._output_root = Path("results/current_run/tests")
        self._case_records: dict[str, CaseRecord] = {}
        self._case_order: list[str] = []
        self._reasons = ReasonRegistry()
        self._original_run_feedback_loop_key: pytest.StashKey[Callable[..., Any] | None] = (
            pytest.StashKey()
        )

    def pytest_collection_modifyitems(
        self,
        session: pytest.Session,
        config: pytest.Config,
        items: list[pytest.Item],
    ) -> None:
        del session
        del config

        missing = self._reasons.missing_reason_nodeids(items)
        if missing:
            head = "\n".join(f" - {nodeid}" for nodeid in missing[:40])
            tail = ""
            if len(missing) > 40:
                tail = f"\n - ... ({len(missing) - 40} more)"
            raise pytest.UsageError(
                "Missing report reasons for collected tests. "
                "Add reason entries in tests/report_gen/*_report.py:\n"
                f"{head}{tail}"
            )

        for item in items:
            module_path = str(item.location[0]).replace("\\", "/")
            test_name = self._reasons.test_name_for_item(item)
            reason = self._reasons.resolve(item.nodeid, module_path, test_name)
            self._case_records[item.nodeid] = CaseRecord(
                nodeid=item.nodeid,
                module_path=module_path,
                test_name=test_name,
                reason=reason,
            )
            self._case_order.append(item.nodeid)

    def pytest_sessionstart(self, session: pytest.Session) -> None:
        del session
        self._prepare_output_dir()

    def _prepare_output_dir(self) -> None:
        if self._output_root.exists():
            for html_file in self._output_root.glob("*.html"):
                html_file.unlink()
            case_dir = self._output_root / "cases"
            if case_dir.exists():
                shutil.rmtree(case_dir)
        self._output_root.mkdir(parents=True, exist_ok=True)

    def pytest_runtest_setup(self, item: pytest.Item) -> None:
        module = getattr(item, "module", None)
        original = getattr(module, "run_feedback_loop", None) if module is not None else None
        if not callable(original):
            item.stash[self._original_run_feedback_loop_key] = None
            return

        nodeid = item.nodeid

        def wrapped_run_feedback_loop(*args: Any, **kwargs: Any):
            result = original(*args, **kwargs)
            trace_record = _extract_trace_record(result)
            if trace_record is not None:
                self._case_records[nodeid].trace_records.append(trace_record)
            return result

        setattr(module, "run_feedback_loop", wrapped_run_feedback_loop)
        item.stash[self._original_run_feedback_loop_key] = original

    def pytest_runtest_teardown(self, item: pytest.Item) -> None:
        original = item.stash.get(self._original_run_feedback_loop_key, None)
        if original is None:
            return

        module = getattr(item, "module", None)
        if module is not None:
            setattr(module, "run_feedback_loop", original)

    def pytest_runtest_logreport(self, report: pytest.TestReport) -> None:
        case = self._case_records.get(report.nodeid)
        if case is None:
            return

        case.duration_sec += float(report.duration)

        if report.when == "call":
            if report.passed:
                case.status = "passed"
            elif report.failed:
                case.status = "failed"
                case.failure_text = getattr(report, "longreprtext", str(report.longrepr))
            elif report.skipped:
                case.status = "skipped"
                case.failure_text = getattr(report, "longreprtext", str(report.longrepr))
            return

        if report.when in {"setup", "teardown"}:
            if report.failed:
                case.status = "error"
                case.failure_text = getattr(report, "longreprtext", str(report.longrepr))
            elif report.skipped and case.status == "notrun":
                case.status = "skipped"
                case.failure_text = getattr(report, "longreprtext", str(report.longrepr))

    def pytest_sessionfinish(
        self,
        session: pytest.Session,
        exitstatus: int,
    ) -> None:
        del exitstatus
        cases = [self._case_records[nodeid] for nodeid in self._case_order]
        render_reports(self._output_root, cases)

        terminal_reporter = session.config.pluginmanager.get_plugin("terminalreporter")
        if terminal_reporter is not None:
            terminal_reporter.write_line(
                f"Generated HTML test report: {self._output_root / 'index.html'}"
            )


def _extract_trace_record(result: Any) -> TraceRecord | None:
    trace: SimulationTrace | None = None
    if isinstance(result, SimulationTrace):
        trace = result
    elif isinstance(result, tuple) and result and isinstance(result[0], SimulationTrace):
        trace = result[0]
    elif isinstance(result, list) and result and isinstance(result[0], SimulationTrace):
        trace = result[0]

    if trace is None:
        return None

    return TraceRecord(
        setup_name=trace.setup_name,
        time_sec=_to_float_list(trace.time_sec),
        ref=_to_signal_payload(trace.ref),
        meas=_to_signal_payload(trace.meas),
        control=_to_float_list(trace.control),
        disturbance=_to_float_list(trace.disturbance),
        kpis=_to_json_dict(trace.kpis),
    )


def _to_signal_payload(value: Any) -> list[float] | dict[str, list[float]]:
    if isinstance(value, dict):
        return {str(key): _to_float_list(series) for key, series in sorted(value.items())}
    return _to_float_list(value)


def _to_float_list(value: Any) -> list[float]:
    return np.asarray(value, dtype=float).tolist()


def _to_json_dict(value: dict[str, Any]) -> dict[str, Any]:
    return {str(key): _to_json_value(raw_value) for key, raw_value in value.items()}


def _to_json_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _to_json_value(raw_value) for key, raw_value in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_json_value(item) for item in value]
    if isinstance(value, np.bool_):
        return bool(value)
    if isinstance(value, (np.integer, np.floating)):
        return value.item()
    if isinstance(value, (bool, int, float, str)) or value is None:
        return value
    return str(value)
