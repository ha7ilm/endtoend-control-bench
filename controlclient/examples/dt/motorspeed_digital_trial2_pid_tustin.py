"""MotorSpeed digital trial 2: direct Tustin PID from motorspeed_digital.m."""

import argparse

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
    b_q, a_q = pid_tustin_coefficients(kp=100.0, ki=200.0, kd=10.0, dt=TS)
    controller = DiscreteTransferController(b_q, a_q, control_limit=2e6)
    run_motorspeed_digital_trial(
        controller=controller,
        description="MotorSpeed digital Tustin PID Kp=100 Ki=200 Kd=10",
        why=(
            "Direct Tustin discretization of the continuous PID in motorspeed_digital.m; "
            "this is the intermediate comparison controller before adding (z+0.82)^-1."
        ),
        setup=args.setup,
    )


if __name__ == "__main__":
    main()
