"""Shared helper for MotorPosition.tex controller trials."""

from __future__ import annotations

from controlclient.machine import MachineClient


def run_motorposition_trial(
    kp: float,
    ki: float,
    kd: float,
    description: str,
    why: str,
    dt: float = 0.001,
) -> None:
    integral_error = 0.0
    prev_error = 0.0
    first_sample = True

    with MachineClient(setup="motorposition_ct", description=description, why=why) as machine:
        while True:
            ctl_input = machine.read()
            if ctl_input["done"]:
                print(ctl_input["kpis"])
                break

            error = ctl_input["ref"] - ctl_input["meas"]
            derivative_error = 0.0 if first_sample else (error - prev_error) / dt
            first_sample = False

            armature_voltage = kp * error + ki * integral_error + kd * derivative_error
            machine.write({"control": armature_voltage})

            integral_error += error * dt
            prev_error = error
