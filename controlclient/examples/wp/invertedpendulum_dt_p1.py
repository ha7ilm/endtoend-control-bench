"""WP PID(P=1, I=0, D=0) controller example for invertedpendulum_dt."""

import math
from typing import Any, Mapping

from controlclient.machine import MachineClient

Kp, Ki, Kd = 1.0, 0.0, 0.0


def _x_cart_error(ctl_input: Mapping[str, Any]) -> float:
    ref = ctl_input["ref"]
    meas = ctl_input["meas"]

    if not isinstance(ref, Mapping) or not isinstance(meas, Mapping):
        raise ValueError("Inverted pendulum ref/meas must both be maps.")
    if "x_cart" not in ref or "x_cart" not in meas:
        raise ValueError("Inverted pendulum ref/meas must contain 'x_cart'.")

    return float(ref["x_cart"]) - float(meas["x_cart"])


def main() -> None:
    with MachineClient(
        setup="invertedpendulum_dt",
        description="WP PID(P=1, I=0, D=0) controller for invertedpendulum_dt",
        why="Minimal proportional trial used to verify automatic MachineClient run logging.",
    ) as machine:
        integral_sum = 0.0
        prev_error = 0.0
        while True:
            ctl_input = machine.read()
            if ctl_input["done"]:
                print(ctl_input["kpis"])
                break

            error = _x_cart_error(ctl_input)
            integral_sum += error
            derivative = error - prev_error
            prev_error = error
            control = Kp * error + Ki * integral_sum + Kd * derivative
            if not math.isfinite(control):
                raise ValueError("Computed control must be finite.")
            machine.write({"control": control})


if __name__ == "__main__":
    main()
