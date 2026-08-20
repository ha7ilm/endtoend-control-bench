"""BallAndBeam digital trial 2: proportional controller Kp=100."""

import argparse

from controlclient.examples.dt._ballandbeam_digital_trial import run_ballandbeam_digital_trial
from controlclient.examples.dt._digital_tf import DiscreteTransferController


TS = 0.02


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--setup",
        default="ballandbeam_dt",
        help="Setup variant name to target (default: %(default)s).",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    controller = DiscreteTransferController([100.0], [1.0], control_limit=1e6)
    run_ballandbeam_digital_trial(
        controller=controller,
        description=f"BallAndBeam digital proportional trial Kp=100 (Ts={TS:.2f}s)",
        why=(
            "Proportional-only digital trial from ballandbeam_digital.m to verify "
            "that increasing Kp alone is insufficient for robust stabilization."
        ),
        setup=args.setup,
    )


if __name__ == "__main__":
    main()
