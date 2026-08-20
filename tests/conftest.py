"""Pytest configuration for local package imports."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

TESTS_DIR = Path(__file__).resolve().parent
if str(TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_DIR))


def pytest_addoption(parser) -> None:
    parser.addoption(
        "--report",
        action="store_true",
        default=False,
        help="Generate HTML test report under results/current_run/tests/.",
    )


def pytest_configure(config) -> None:
    if not config.getoption("--report"):
        return

    from report_gen.plugin import ReportPlugin

    config.pluginmanager.register(ReportPlugin(config), "urletra-report-plugin")
