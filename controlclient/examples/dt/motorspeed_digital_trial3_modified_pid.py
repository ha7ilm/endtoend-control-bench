"""MotorSpeed digital trial 3: modified PID with gain 0.8 and division by (z+0.82)."""

import argparse

import numpy as np

from controlclient.examples.dt._digital_tf import DiscreteTransferController, pid_tustin_coefficients
from controlclient.examples.dt._motorspeed_digital_trial import run_motorspeed_digital_trial


TS = 0.05


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--setup",
        default="motorspeed_dt",
        help="Setup variant name to target (default: %(default)s).",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    # dC = c2d(PID, Ts, 'tustin'); dC = dC/(z+0.82); use loop gain 0.8.
    b_pid_q, a_pid_q = pid_tustin_coefficients(kp=100.0, ki=200.0, kd=10.0, dt=TS)

    # Divide by (z+0.82): in q=z^-1 this is q/(1+0.82q).
    b_q = 0.8 * np.concatenate((np.array([0.0], dtype=float), b_pid_q))
    a_q = np.convolve(a_pid_q, np.array([1.0, 0.82], dtype=float))

    controller = DiscreteTransferController(b_q, a_q, control_limit=1e6)
    run_motorspeed_digital_trial(
        controller=controller,
        description="MotorSpeed digital modified PID with gain 0.8",
        why=(
            "Final controller in motorspeed_digital.m: Tustin PID divided by (z+0.82) and "
            "scaled by loop gain 0.8 to restore stability and satisfy design targets."
        ),
        setup=args.setup,
    )


if __name__ == "__main__":
    main()
