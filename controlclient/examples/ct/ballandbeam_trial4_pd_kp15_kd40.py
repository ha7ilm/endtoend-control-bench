"""Ball and beam trial 4 from BallAndBeam.tex.

PD control: Kp=15, Kd=40
"""

from controlclient.examples.ct._ballandbeam_trial import run_ballandbeam_trial


def main() -> None:
    run_ballandbeam_trial(
        kp=15.0,
        ki=0.0,
        kd=40.0,
        description="BallAndBeam final PD trial Kp=15 Kd=40",
        why=(
            "Final BallAndBeam.tex trial with tuned proportional and derivative "
            "gains chosen to satisfy settling-time and overshoot requirements."
        ),
    )


if __name__ == "__main__":
    main()
