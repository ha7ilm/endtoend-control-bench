"""Motor speed trial 2 PID controller from MotorSpeed.tex.

Kp=75, Ki=1, Kd=1
"""

from controlclient.machine import MachineClient


def main() -> None:
    kp = 75.0
    ki = 1.0
    kd = 1.0
    dt = 0.001  # motorspeed_ct setup dt from controlserver/config.py

    integral_error = 0.0
    prev_error = 0.0
    first_sample = True

    with MachineClient(
        setup="motorspeed_ct",
        description="PID(75,1,1) controller",
        why=(
            "The proportional-only trial could not satisfy all requirements, so now we add "
            "small Ki and Kd to remove steady-state error and evaluate initial damping."
        ),
    ) as machine:
        while True:
            ctl_input = machine.read()
            if ctl_input["done"]:
                print(ctl_input["kpis"])
                break

            error = ctl_input["ref"] - ctl_input["meas"]

            derivative_error = 0.0 if first_sample else (error - prev_error) / dt
            first_sample = False

            armature_voltage = (
                kp * error + ki * integral_error + kd * derivative_error
            )

            machine.write({"control": armature_voltage})

            integral_error += error * dt
            prev_error = error


if __name__ == "__main__":
    main()
