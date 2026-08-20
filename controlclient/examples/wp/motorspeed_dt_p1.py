"""WP PID(P=1, I=0, D=0) controller example for motorspeed_dt."""

import math

from controlclient.machine import MachineClient

Kp, Ki, Kd = 1.0, 0.0, 0.0


def main() -> None:
    with MachineClient(
        setup="motorspeed_dt",
        description="WP PID(P=1, I=0, D=0) controller for motorspeed_dt",
        why="Minimal proportional trial used to verify automatic MachineClient run logging.",
    ) as machine:
        integral_sum = 0.0
        prev_error = 0.0
        while True:
            ctl_input = machine.read()
            if ctl_input["done"]:
                print(ctl_input["kpis"])
                break

            error = float(ctl_input["ref"]) - float(ctl_input["meas"])
            integral_sum += error
            derivative = error - prev_error
            prev_error = error
            control = Kp * error + Ki * integral_sum + Kd * derivative
            if not math.isfinite(control):
                raise ValueError("Computed control must be finite.")
            machine.write({"control": control})


if __name__ == "__main__":
    main()
