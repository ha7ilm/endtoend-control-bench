"""CruiseControl digital trial 1: gain-only design from cruisecontrol_digital.m."""

import argparse

from controlclient.examples.dt._cruisecontrol_digital_trial import run_cruisecontrol_digital_trial
from controlclient.examples.dt._digital_tf import DiscreteTransferController


GAIN = 451.1104


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
    controller = DiscreteTransferController([GAIN], [1.0], control_limit=2e5)
    run_cruisecontrol_digital_trial(
        controller=controller,
        description="CruiseControl digital gain-only controller K=451.1104",
        why=(
            "Initial digital root-locus gain selected in cruisecontrol_digital.m before "
            "adding lag compensation for steady-state error reduction."
        ),
        setup=args.setup,
    )


if __name__ == "__main__":
    main()
