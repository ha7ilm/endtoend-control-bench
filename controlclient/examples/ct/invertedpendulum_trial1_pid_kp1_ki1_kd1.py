"""Inverted pendulum trial 1 from InvertedPendulum.tex.

PID control: Kp=1, Ki=1, Kd=1
"""

from controlclient.examples.ct._invertedpendulum_trial import run_invertedpendulum_trial


def main() -> None:
    run_invertedpendulum_trial(
        kp=1.0,
        ki=1.0,
        kd=1.0,
        description="InvertedPendulum PID(1,1,1) baseline",
        why=(
            "Initial PID gains from InvertedPendulum.tex used as the unstable/rough "
            "baseline before aggressive proportional and derivative tuning."
        ),
    )


if __name__ == "__main__":
    main()

