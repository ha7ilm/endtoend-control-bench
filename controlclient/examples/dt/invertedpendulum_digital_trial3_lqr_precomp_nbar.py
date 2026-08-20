"""Inverted pendulum digital trial 3: tuned LQR plus precompensation Nbar=-61.55."""

import argparse

from controlclient.examples.dt._invertedpendulum_digital_trial import (
    InvertedPendulumDigitalLqrController,
    run_invertedpendulum_digital_trial,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--setup",
        default="invertedpendulum_dt",
        help="Setup variant name to target (default: %(default)s).",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    controller = InvertedPendulumDigitalLqrController(
        dt=0.01,
        q_cart=5000.0,
        q_phi=100.0,
        r=1.0,
        nbar=-61.55,
    )
    run_invertedpendulum_digital_trial(
        controller=controller,
        description="InvertedPendulum digital LQR tuned Q + Nbar",
        why=(
            "Third digital trial from invertedpendulum_digital.m introduces the "
            "precompensator Nbar=-61.55 to remove cart-position steady-state error."
        ),
        setup=args.setup,
    )


if __name__ == "__main__":
    main()
