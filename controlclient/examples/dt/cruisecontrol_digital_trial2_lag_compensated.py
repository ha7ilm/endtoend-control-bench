"""CruiseControl digital trial 2: lag-compensated design from cruisecontrol_digital.m."""

import argparse

from controlclient.examples.dt._cruisecontrol_digital_trial import run_cruisecontrol_digital_trial
from controlclient.examples.dt._digital_tf import DiscreteTransferController


LOOP_GAIN = 2.4454e3
KD = 0.2


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--setup",
        default="cruisecontrol_dt",
        help="Setup variant name to target (default: %(default)s).",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    controller = DiscreteTransferController.from_zpk(
        zeros_z=[0.999],
        poles_z=[0.9998],
        gain=LOOP_GAIN * KD,
        control_limit=2e5,
    )
    run_cruisecontrol_digital_trial(
        controller=controller,
        description="CruiseControl digital lag-compensated controller",
        why=(
            "Final digital lag compensator from cruisecontrol_digital.m: "
            "K*0.2*(z-0.999)/(z-0.9998), with K=2445.4."
        ),
        setup=args.setup,
    )


if __name__ == "__main__":
    main()
