"""Inverted pendulum digital trial 1: baseline LQR with Q=C'C, R=1."""

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
        q_cart=1.0,
        q_phi=1.0,
        r=1.0,
    )
    run_invertedpendulum_digital_trial(
        controller=controller,
        description="InvertedPendulum digital LQR baseline (Q=C'C, R=1)",
        why=(
            "Baseline digital LQR from invertedpendulum_digital.m before Q reweighting "
            "and precompensation."
        ),
        setup=args.setup,
    )


if __name__ == "__main__":
    main()
