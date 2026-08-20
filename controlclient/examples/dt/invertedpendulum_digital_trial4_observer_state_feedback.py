"""Inverted pendulum digital trial 4: observer-based state-feedback."""

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
        use_observer=True,
        observer_poles=(-0.2, -0.21, -0.22, -0.23),
    )
    run_invertedpendulum_digital_trial(
        controller=controller,
        description="InvertedPendulum digital observer-based state feedback",
        why=(
            "Final digital trial from invertedpendulum_digital.m with observer poles "
            "[-0.2, -0.21, -0.22, -0.23] and tuned LQR + Nbar."
        ),
        setup=args.setup,
    )


if __name__ == "__main__":
    main()
