"""Shared helper for Suspension.tex controller trials."""

from __future__ import annotations

from controlclient.machine import MachineClient


def _clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


def run_suspension_trial(
    kp: float,
    ki: float,
    kd: float,
    description: str,
    why: str,
    *,
    dt: float = 0.0005,
    derivative_alpha: float = 0.95,
    integral_limit: float = 1.0,
    control_limit: float = 30000.0,
) -> None:
    integral_error = 0.0
    prev_error = 0.0
    derivative_filtered = 0.0
    first_sample = True

    with MachineClient(setup="suspension_ct", description=description, why=why) as machine:
        while True:
            ctl_input = machine.read()
            if ctl_input["done"]:
                print(ctl_input["kpis"])
                break

            error = ctl_input["ref"] - ctl_input["meas"]
            raw_derivative = 0.0 if first_sample else (error - prev_error) / dt
            first_sample = False

            derivative_filtered = (
                derivative_alpha * derivative_filtered
                + (1.0 - derivative_alpha) * raw_derivative
            )
            integral_error = _clamp(
                integral_error + error * dt,
                -integral_limit,
                integral_limit,
            )

            actuator_force = (
                kp * error + ki * integral_error + kd * derivative_filtered
            )
            actuator_force = _clamp(actuator_force, -control_limit, control_limit)

            machine.write({"control": actuator_force})
            prev_error = error
