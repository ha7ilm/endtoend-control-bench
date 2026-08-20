"""Shared helper for InvertedPendulum.tex PID controller trials."""

from __future__ import annotations

from typing import Any, Mapping

import numpy as np

from controlclient.machine import MachineClient


def _as_signal_map(value: Any, field: str) -> dict[str, float]:
    if not isinstance(value, Mapping):
        raise ValueError(f"Inverted pendulum '{field}' must be a map with x_cart/phi_angle keys.")

    try:
        x = float(value["x_cart"])
        phi = float(value["phi_angle"])
    except KeyError as exc:
        raise ValueError(
            f"Inverted pendulum '{field}' must contain keys 'x_cart' and 'phi_angle'."
        ) from exc

    if not np.isfinite(x) or not np.isfinite(phi):
        raise ValueError(f"Inverted pendulum '{field}' values must be finite.")
    return {"x_cart": x, "phi_angle": phi}


def run_invertedpendulum_trial(
    kp: float,
    ki: float,
    kd: float,
    description: str,
    why: str,
    *,
    dt: float = 0.01,
    control_limit: float = 10000.0,
) -> None:
    integral_error = 0.0
    prev_error = 0.0
    first_sample = True

    with MachineClient(setup="invertedpendulum_ct", description=description, why=why) as machine:
        while True:
            ctl_input = machine.read()
            if ctl_input["done"]:
                print(ctl_input["kpis"])
                break

            ref = _as_signal_map(ctl_input["ref"], "ref")
            meas = _as_signal_map(ctl_input["meas"], "meas")

            # The PID sequence from InvertedPendulum.tex is designed around phi regulation.
            error = ref["phi_angle"] - meas["phi_angle"]
            derivative_error = 0.0 if first_sample else (error - prev_error) / dt
            first_sample = False

            force = kp * error + ki * integral_error + kd * derivative_error
            if not np.isfinite(force):
                force = 0.0
            force = float(np.clip(force, -abs(control_limit), abs(control_limit)))

            machine.write({"control": force})

            integral_error += error * dt
            prev_error = error

