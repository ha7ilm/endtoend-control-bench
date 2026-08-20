from __future__ import annotations

import importlib
import pkgutil
from dataclasses import dataclass
from typing import Iterable

import pytest


@dataclass(frozen=True)
class _ModuleReasons:
    by_test: dict[str, str]
    by_nodeid: dict[str, str]


class ReasonRegistry:
    """Loads and resolves report reason text from tests/report_gen/*_report.py files."""

    def __init__(self) -> None:
        self._by_module: dict[str, _ModuleReasons] = {}
        self._load_reason_modules()

    def _load_reason_modules(self) -> None:
        package = importlib.import_module("report_gen")
        for module_info in pkgutil.iter_modules(package.__path__):
            name = module_info.name
            if not name.endswith("_report"):
                continue

            module = importlib.import_module(f"report_gen.{name}")
            test_module = str(getattr(module, "TEST_MODULE", "")).strip()
            if not test_module:
                raise RuntimeError(
                    f"Reason module report_gen.{name} is missing TEST_MODULE."
                )

            by_test = dict(getattr(module, "REASONS_BY_TEST", {}))
            by_nodeid = dict(getattr(module, "REASONS_BY_NODEID", {}))
            if not by_test and not by_nodeid:
                raise RuntimeError(
                    f"Reason module report_gen.{name} must define REASONS_BY_TEST or REASONS_BY_NODEID."
                )

            self._by_module[test_module] = _ModuleReasons(
                by_test=by_test,
                by_nodeid=by_nodeid,
            )

    def resolve(self, nodeid: str, module_path: str, test_name: str) -> str:
        module_reasons = self._by_module.get(module_path)
        if module_reasons is None:
            raise KeyError(module_path)

        reason = module_reasons.by_nodeid.get(nodeid)
        if reason:
            return reason

        reason = module_reasons.by_test.get(test_name)
        if reason:
            return reason

        raise KeyError(nodeid)

    @staticmethod
    def test_name_for_item(item: pytest.Item) -> str:
        original_name = getattr(item, "originalname", None)
        if isinstance(original_name, str) and original_name:
            return original_name

        name = item.name
        if "[" in name:
            return name.split("[", 1)[0]
        return name

    def missing_reason_nodeids(self, items: Iterable[pytest.Item]) -> list[str]:
        missing: list[str] = []
        for item in items:
            module_path = str(item.location[0]).replace("\\", "/")
            test_name = self.test_name_for_item(item)
            try:
                self.resolve(item.nodeid, module_path, test_name)
            except KeyError:
                missing.append(item.nodeid)
        return missing
