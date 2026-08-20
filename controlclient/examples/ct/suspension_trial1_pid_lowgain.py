"""Suspension trial 1 from Suspension.tex.

Low-gain PID: Kp=832100, Ki=624075, Kd=208025
"""

from controlclient.examples.ct._suspension_trial import run_suspension_trial


def main() -> None:
    run_suspension_trial(
        kp=832100.0,
        ki=624075.0,
        kd=208025.0,
        description="PID low-gain (832100,624075,208025)",
        why=(
            "Initial PID gains from the Suspension.tex MATLAB code block, evaluated "
            "against a 0.1 m road-step disturbance."
        ),
    )


if __name__ == "__main__":
    main()

