"""Inverted pendulum trial 3 from InvertedPendulum.tex.

PID control: Kp=100, Ki=1, Kd=20
"""

from controlclient.examples.ct._invertedpendulum_trial import run_invertedpendulum_trial


def main() -> None:
    run_invertedpendulum_trial(
        kp=100.0,
        ki=1.0,
        kd=20.0,
        description="InvertedPendulum PID(100,1,20)",
        why=(
            "Final PID trial from InvertedPendulum.tex increases derivative gain to 20 "
            "to reduce overshoot while keeping the faster proportional response."
        ),
    )


if __name__ == "__main__":
    main()

