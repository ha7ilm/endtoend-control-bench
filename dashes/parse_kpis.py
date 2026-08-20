"""Deterministic KPI parsing and evaluation utilities.

Evaluates feasibility (meets_design_spec) per setup based on setup specifications,
and computes optimization objectives (compute_objective) per setup.
"""

from __future__ import annotations

import math
from typing import Any


# ---------------------------------------------------------------------------
# Setup-specific constraint registries
# ---------------------------------------------------------------------------

def _get_scalar(kpis: dict, key: str) -> float:
    """Extract a scalar KPI value, returning NaN if missing or non-finite."""
    v = kpis.get(key)
    if v is None:
        return float("nan")
    try:
        f = float(v)
    except (TypeError, ValueError):
        return float("nan")
    return f if math.isfinite(f) else float("nan")


def _get_channel(kpis: dict, channel: str, key: str) -> float:
    """Extract a multi-channel KPI value, returning NaN if missing."""
    channels = kpis.get("channels")
    if not isinstance(channels, dict):
        return float("nan")
    ch = channels.get(channel)
    if not isinstance(ch, dict):
        return float("nan")
    return _get_scalar(ch, key)


# Each entry: (description_string, extractor_callable)
# extractor returns (value, limit) where constraint is value < limit.
_SCALAR_CONSTRAINTS: dict[str, list[tuple[str, str, float]]] = {
    "aircraftpitch_dt": [
        ("overshoot_pct < 10", "overshoot_pct", 10),
        ("rise_time_sec < 2", "rise_time_sec", 2),
        ("settling_time_sec < 10", "settling_time_sec", 10),
        ("steady_state_error_pct < 2", "steady_state_error_pct", 2),
    ],
    "ballandbeam_dt": [
        ("settling_time_sec < 3", "settling_time_sec", 3),
        ("overshoot_pct < 5", "overshoot_pct", 5),
    ],
    "ballandbeam_dt_nl_act_mg996r": [
        ("settling_time_sec < 3", "settling_time_sec", 3),
        ("overshoot_pct < 8", "overshoot_pct", 8),
    ],
    "cruisecontrol_dt": [
        ("rise_time_sec < 5", "rise_time_sec", 5),
        ("overshoot_pct < 10", "overshoot_pct", 10),
        ("steady_state_error_pct < 2", "steady_state_error_pct", 2),
    ],
    "cruisecontrol_dt_lim_hondajazz": [
        ("rise_time_sec < 5", "rise_time_sec", 5),
        ("overshoot_pct < 10", "overshoot_pct", 10),
        ("steady_state_error_pct < 2", "steady_state_error_pct", 2),
    ],
    "motorspeed_dt": [
        ("settling_time_sec < 2", "settling_time_sec", 2),
        ("overshoot_pct < 5", "overshoot_pct", 5),
        ("steady_state_error_pct < 1", "steady_state_error_pct", 1),
    ],
    "motorspeed_dt_lim_maxonre30": [
        ("settling_time_sec < 0.5", "settling_time_sec", 0.5),
        ("overshoot_pct < 5", "overshoot_pct", 5),
        ("steady_state_error_pct < 1", "steady_state_error_pct", 1),
    ],
}

_INVPEND_CONSTRAINTS_BASE: list[tuple[str, str, str, float]] = [
    ("x_cart.settling_time_sec < 5", "x_cart", "settling_time_sec", 5),
    ("phi_angle.settling_time_sec < 5", "phi_angle", "settling_time_sec", 5),
    # rise_time_sec placeholder — overridden per variant
    ("phi_angle.max_abs_rad < 0.35", "phi_angle", "max_abs_rad", 0.35),
    ("x_cart.steady_state_error_pct < 2", "x_cart", "steady_state_error_pct", 2),
    ("phi_angle.steady_state_error_pct < 2", "phi_angle", "steady_state_error_pct", 2),
]


def _invpend_constraints(rise_limit: float) -> list[tuple[str, str, str, float]]:
    return [
        *_INVPEND_CONSTRAINTS_BASE,
        (f"x_cart.rise_time_sec < {rise_limit}", "x_cart", "rise_time_sec", rise_limit),
    ]


_INVPEND_SETUPS: dict[str, float] = {
    "invertedpendulum_dt": 0.5,
    "invertedpendulum_dt_nl_lim_quanserip02": 0.8,
}

_ALL_KNOWN_SETUPS = set(_SCALAR_CONSTRAINTS) | set(_INVPEND_SETUPS)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def failed_constraints(setup_name: str, kpis: dict[str, Any]) -> list[str]:
    """Return list of violated constraint descriptions. Empty means feasible."""
    if setup_name not in _ALL_KNOWN_SETUPS:
        raise ValueError(f"Unknown setup: {setup_name!r}")
    if not isinstance(kpis, dict):
        raise TypeError(f"kpis must be a dict, got {type(kpis).__name__}")

    failures: list[str] = []

    if setup_name in _SCALAR_CONSTRAINTS:
        for desc, key, limit in _SCALAR_CONSTRAINTS[setup_name]:
            val = _get_scalar(kpis, key)
            if not (val < limit):  # NaN fails this check
                failures.append(desc)
    else:
        # Inverted pendulum variant
        constraints = _invpend_constraints(_INVPEND_SETUPS[setup_name])
        for desc, channel, key, limit in constraints:
            val = _get_channel(kpis, channel, key)
            if not (val < limit):
                failures.append(desc)

    return failures


def meets_design_spec(setup_name: str, kpis: dict[str, Any]) -> bool:
    """Check if KPIs meet all design constraints for the given setup."""
    return len(failed_constraints(setup_name, kpis)) == 0


# ---------------------------------------------------------------------------
# Objective computation
# ---------------------------------------------------------------------------

_OBJECTIVE_GROUP_OS_3ST = {
    "aircraftpitch_dt",
    "ballandbeam_dt",
    "ballandbeam_dt_nl_act_mg996r",
    "motorspeed_dt",
    "motorspeed_dt_lim_maxonre30",
}

_OBJECTIVE_GROUP_OS_2RT = {
    "cruisecontrol_dt",
    "cruisecontrol_dt_lim_hondajazz",
}


def explain_constraints(
    setup_name: str, kpis: dict[str, Any],
) -> list[tuple[str, float, float, bool]]:
    """Return detailed constraint results: (description, actual_value, limit, passed).

    For multi-channel setups the description includes the channel prefix
    (e.g. ``x_cart.settling_time_sec < 5``).  ``actual_value`` is NaN when
    the KPI key is missing.
    """
    if setup_name not in _ALL_KNOWN_SETUPS:
        raise ValueError(f"Unknown setup: {setup_name!r}")
    if not isinstance(kpis, dict):
        raise TypeError(f"kpis must be a dict, got {type(kpis).__name__}")

    results: list[tuple[str, float, float, bool]] = []
    if setup_name in _SCALAR_CONSTRAINTS:
        for desc, key, limit in _SCALAR_CONSTRAINTS[setup_name]:
            val = _get_scalar(kpis, key)
            results.append((desc, val, limit, val < limit))
    else:
        constraints = _invpend_constraints(_INVPEND_SETUPS[setup_name])
        for desc, channel, key, limit in constraints:
            val = _get_channel(kpis, channel, key)
            results.append((desc, val, limit, val < limit))
    return results


def explain_objective(
    setup_name: str, kpis: dict[str, Any],
) -> tuple[list[tuple[str, float, float]], float]:
    """Return objective breakdown as ``(terms, total)``.

    Each term is ``(label, value, weight)``.  ``total`` is the weighted sum
    (``inf`` when any value is non-finite).
    """
    if setup_name not in _ALL_KNOWN_SETUPS:
        raise ValueError(f"Unknown setup: {setup_name!r}")
    if not isinstance(kpis, dict):
        raise TypeError(f"kpis must be a dict, got {type(kpis).__name__}")

    if setup_name in _OBJECTIVE_GROUP_OS_3ST:
        terms = [
            ("overshoot_pct", _get_scalar(kpis, "overshoot_pct"), 1.0),
            ("settling_time_sec", _get_scalar(kpis, "settling_time_sec"), 3.0),
        ]
    elif setup_name in _OBJECTIVE_GROUP_OS_2RT:
        terms = [
            ("overshoot_pct", _get_scalar(kpis, "overshoot_pct"), 1.0),
            ("rise_time_sec", _get_scalar(kpis, "rise_time_sec"), 2.0),
        ]
    else:
        terms = [
            ("x_cart.settling_time_sec", _get_channel(kpis, "x_cart", "settling_time_sec"), 1.0),
            ("x_cart.steady_state_error_pct", _get_channel(kpis, "x_cart", "steady_state_error_pct"), 2.0),
            ("phi_angle.settling_time_sec", _get_channel(kpis, "phi_angle", "settling_time_sec"), 1.0),
            ("phi_angle.steady_state_error_pct", _get_channel(kpis, "phi_angle", "steady_state_error_pct"), 2.0),
        ]

    total = sum(v * w for _, v, w in terms)
    if not math.isfinite(total):
        total = float("inf")
    return terms, total


def compute_objective(setup_name: str, kpis: dict[str, Any]) -> float:
    """Compute the optimization objective for a setup. Returns inf on missing data."""
    if setup_name not in _ALL_KNOWN_SETUPS:
        raise ValueError(f"Unknown setup: {setup_name!r}")
    if not isinstance(kpis, dict):
        raise TypeError(f"kpis must be a dict, got {type(kpis).__name__}")

    if setup_name in _OBJECTIVE_GROUP_OS_3ST:
        os_pct = _get_scalar(kpis, "overshoot_pct")
        st = _get_scalar(kpis, "settling_time_sec")
        if not (math.isfinite(os_pct) and math.isfinite(st)):
            return float("inf")
        return os_pct + 3 * st

    if setup_name in _OBJECTIVE_GROUP_OS_2RT:
        os_pct = _get_scalar(kpis, "overshoot_pct")
        rt = _get_scalar(kpis, "rise_time_sec")
        if not (math.isfinite(os_pct) and math.isfinite(rt)):
            return float("inf")
        return os_pct + 2 * rt

    # Inverted pendulum
    x_st = _get_channel(kpis, "x_cart", "settling_time_sec")
    x_sse = _get_channel(kpis, "x_cart", "steady_state_error_pct")
    p_st = _get_channel(kpis, "phi_angle", "settling_time_sec")
    p_sse = _get_channel(kpis, "phi_angle", "steady_state_error_pct")
    vals = [x_st, x_sse, p_st, p_sse]
    if not all(math.isfinite(v) for v in vals):
        return float("inf")
    return x_st + 2 * x_sse + p_st + 2 * p_sse


# ---------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------

def format_objective(value: float) -> str:
    """Format objective with adaptive precision. Trims trailing zeros, keeps >= 1 decimal."""
    if not math.isfinite(value):
        return "inf"
    abs_val = abs(value)
    if abs_val < 1:
        decimals = 4
    elif abs_val < 10:
        decimals = 3
    elif abs_val < 100:
        decimals = 2
    else:
        decimals = 1
    formatted = f"{value:.{decimals}f}"
    # Trim trailing zeros but keep at least 1 decimal digit
    if "." in formatted:
        integer_part, frac_part = formatted.split(".")
        frac_part = frac_part.rstrip("0")
        if not frac_part:
            frac_part = "0"
        formatted = f"{integer_part}.{frac_part}"
    return formatted
