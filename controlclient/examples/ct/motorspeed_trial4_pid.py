"""Motor speed trial 4 PID controller from MotorSpeed.tex.

Kp=100, Ki=200, Kd=10
"""

from controlclient.machine import MachineClient


def main() -> None:
    kp = 100.0
    ki = 200.0
    kd = 10.0
    dt = 0.001  # motorspeed_ct setup dt from controlserver/config.py

    integral_error = 0.0
    prev_error = 0.0
    first_sample = True

    with MachineClient(
        setup="motorspeed_ct",
        description="PID(100,200,10) controller",
        why=(
            "After raising Ki, overshoot became too large, so we increase Kd to 10 to add "
            "damping and reduce overshoot while keeping fast settling."
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
