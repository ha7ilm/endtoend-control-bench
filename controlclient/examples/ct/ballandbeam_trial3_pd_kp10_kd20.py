"""Ball and beam trial 3 from BallAndBeam.tex.

PD control: Kp=10, Kd=20
"""

from controlclient.examples.ct._ballandbeam_trial import run_ballandbeam_trial


def main() -> None:
    run_ballandbeam_trial(
        kp=10.0,
        ki=0.0,
        kd=20.0,
        description="BallAndBeam PD trial Kp=10 Kd=20",
        why=(
            "BallAndBeam.tex next increases derivative gain to Kd=20 to reduce "
            "overshoot and improve damping compared with Kd=10."
        ),
    )


if __name__ == "__main__":
    main()
