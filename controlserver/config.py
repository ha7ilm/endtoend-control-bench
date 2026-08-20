"""Configuration for feedback loop server setups."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from .setup_variants import get_setup_variant_spec

RESULTS_ROOT = Path("results/current_run/sim")

def get_setup_config(setup_name: str) -> dict:
    """Return a copy of the setup-specific simulation configuration."""
    return deepcopy(get_setup_variant_spec(setup_name).config)


def get_setup_signal_metadata(setup_name: str) -> dict[str, dict[str, str]]:
    """Return validated display metadata for setup signals."""
    config = get_setup_config(setup_name)
    signals = config.get("signals")
    if not isinstance(signals, dict):
        raise ValueError(f"Setup '{setup_name}' is missing signals metadata.")

    validated: dict[str, dict[str, str]] = {}
    for key in ("ref", "meas", "control"):
        spec: Any = signals.get(key)
        if not isinstance(spec, dict):
            raise ValueError(f"Setup '{setup_name}' signal '{key}' metadata must be a map.")

        display_name = spec.get("display_name")
        unit = spec.get("unit")
        if not isinstance(display_name, str) or not display_name:
            raise ValueError(
                f"Setup '{setup_name}' signal '{key}' requires non-empty display_name."
            )
        if not isinstance(unit, str) or not unit:
            raise ValueError(f"Setup '{setup_name}' signal '{key}' requires non-empty unit.")

        validated[key] = {
            "display_name": display_name,
            "unit": unit,
        }

    return validated
