"""BallAndBeam digital trial 4: PD controller Kp=1000, Kd=10."""

import argparse

import numpy as np

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
    kp = 1000.0
    kd = 10.0

    # C(z) = ((Kp+Kd) z^2 - (Kp+2Kd) z + Kd) / (z^2 + z)
    # Implemented in q = z^-1 as:
    # C(q) = ((Kp+Kd) - (Kp+2Kd) q + Kd q^2) / (1 + q)
    b_q = np.array([kp + kd, -(kp + 2.0 * kd), kd], dtype=float)
    a_q = np.array([1.0, 1.0], dtype=float)

    controller = DiscreteTransferController(b_q, a_q, control_limit=1e6)
    run_ballandbeam_digital_trial(
        controller=controller,
        description=f"BallAndBeam digital final PD trial Kp=1000 Kd=10 (Ts={TS:.2f}s)",
        why=(
            "Final digital trial from ballandbeam_digital.m increases Kp to 1000 "
            "with Kd=10 to meet settling-time and overshoot targets."
        ),
        setup=args.setup,
    )


if __name__ == "__main__":
    main()
