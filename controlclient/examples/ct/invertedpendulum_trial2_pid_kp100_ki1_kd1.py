"""Inverted pendulum trial 2 from InvertedPendulum.tex.

PID control: Kp=100, Ki=1, Kd=1
"""

from controlclient.examples.ct._invertedpendulum_trial import run_invertedpendulum_trial


def main() -> None:
    run_invertedpendulum_trial(
        kp=100.0,
        ki=1.0,
        kd=1.0,
        description="InvertedPendulum PID(100,1,1)",
        why=(
            "Second trial from InvertedPendulum.tex raises proportional action to 100 "
            "to stabilize response and speed recovery before derivative retuning."
        ),
    )


if __name__ == "__main__":
    main()

