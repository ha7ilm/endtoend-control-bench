"""MotorSpeed digital trial 1: uncompensated baseline (C(z)=1)."""

import argparse

from controlclient.examples.dt._digital_tf import DiscreteTransferController
from controlclient.examples.dt._motorspeed_digital_trial import run_motorspeed_digital_trial


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
    controller = DiscreteTransferController([1.0], [1.0], control_limit=1e6)
    run_motorspeed_digital_trial(
        controller=controller,
        description="MotorSpeed digital baseline C(z)=1",
        why=(
            "Baseline from motorspeed_digital.m: closed-loop response without additional "
            "compensation before discrete PID design."
        ),
        setup=args.setup,
    )


if __name__ == "__main__":
    main()
