"""Ball and beam trial 1 from BallAndBeam.tex.

Proportional control: Kp=1
"""

from controlclient.examples.ct._ballandbeam_trial import run_ballandbeam_trial


def main() -> None:
    run_ballandbeam_trial(
        kp=1.0,
        ki=0.0,
        kd=0.0,
        description="BallAndBeam P-only baseline Kp=1",
        why=(
            "Initial proportional trial from BallAndBeam.tex to establish that a "
            "single proportional gain does not stabilize the double-integrator plant."
        ),
    )


if __name__ == "__main__":
    main()
