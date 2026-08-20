"""Shared helper for BallAndBeam.tex controller trials."""

from __future__ import annotations

import numpy as np

from controlclient.machine import MachineClient


def run_ballandbeam_trial(
    kp: float,
    ki: float,
    kd: float,
    description: str,
    why: str,
    *,
    dt: float = 0.02,
    control_limit: float = 1e6,
) -> None:
    integral_error = 0.0
    prev_error = 0.0
    first_sample = True

    with MachineClient(setup="ballandbeam_ct", description=description, why=why) as machine:
        while True:
            ctl_input = machine.read()
            if ctl_input["done"]:
                print(ctl_input["kpis"])
                break

            error = ctl_input["ref"] - ctl_input["meas"]
            derivative_error = 0.0 if first_sample else (error - prev_error) / dt
            first_sample = False

            gear_angle = kp * error + ki * integral_error + kd * derivative_error
            if not np.isfinite(gear_angle):
                gear_angle = 0.0
            gear_angle = float(np.clip(gear_angle, -abs(control_limit), abs(control_limit)))

            machine.write({"control": gear_angle})

            integral_error += error * dt
            prev_error = error
