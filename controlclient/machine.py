"""Compatibility wrapper for local repo imports."""

from __future__ import annotations

import sys
from pathlib import Path

try:
    from urletra.controlclient.machine import MachineClient
except ModuleNotFoundError:
    src_root = Path(__file__).resolve().parents[1] / "src"
    src_root_str = str(src_root)
    if src_root_str not in sys.path:
        sys.path.insert(0, src_root_str)
    from urletra.controlclient.machine import MachineClient

__all__ = ["MachineClient"]
