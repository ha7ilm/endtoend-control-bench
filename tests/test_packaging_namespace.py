from __future__ import annotations

import importlib
import sys
from pathlib import Path


def _with_src_on_path() -> None:
    src_root = Path(__file__).resolve().parents[1] / "src"
    src_root_str = str(src_root)
    if src_root_str not in sys.path:
        sys.path.insert(0, src_root_str)


def test_urletra_namespace_exposes_controlclient():
    _with_src_on_path()
    urletra = importlib.import_module("urletra")

    assert hasattr(urletra, "controlclient")


def test_urletra_controlclient_exports_machine_client():
    _with_src_on_path()
    module = importlib.import_module("urletra.controlclient")

    assert hasattr(module, "MachineClient")
