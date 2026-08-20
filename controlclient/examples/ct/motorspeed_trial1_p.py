"""Motor speed trial 1 proportional controller from MotorSpeed.tex.

Kp=100
"""

from controlclient.machine import MachineClient


def main() -> None:
    kp = 100.0

    with MachineClient(
        setup="motorspeed_ct",
        description="P(100) controller",
        why=(
            "Proportional-only baseline from MotorSpeed.tex; we are measuring "
            "steady-state error and overshoot before introducing integral and derivative terms."
        ),
    ) as machine:
        while True:
            ctl_input = machine.read()
            if ctl_input["done"]:
                print(ctl_input["kpis"])
                break

            error = ctl_input["ref"] - ctl_input["meas"]
            machine.write({"control": kp * error})


if __name__ == "__main__":
    main()
