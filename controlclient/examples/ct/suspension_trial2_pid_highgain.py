"""Suspension trial 2 from Suspension.tex.

High-gain PID: Kp=1664200, Ki=1248150, Kd=416050
"""

from controlclient.examples.ct._suspension_trial import run_suspension_trial


def main() -> None:
    run_suspension_trial(
        kp=1664200.0,
        ki=1248150.0,
        kd=416050.0,
        description="PID high-gain (1664200,1248150,416050)",
        why=(
            "Second Suspension.tex trial doubles all three PID gains from the initial "
            "set to improve disturbance rejection performance."
        ),
    )


if __name__ == "__main__":
    main()

