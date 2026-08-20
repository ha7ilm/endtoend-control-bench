"""Ball and beam trial 2 from BallAndBeam.tex.

PD control: Kp=10, Kd=10
"""

from controlclient.examples.ct._ballandbeam_trial import run_ballandbeam_trial


def main() -> None:
    run_ballandbeam_trial(
        kp=10.0,
        ki=0.0,
        kd=10.0,
        description="BallAndBeam PD trial Kp=10 Kd=10",
        why=(
            "Second trial from BallAndBeam.tex adds derivative action while keeping "
            "Kp=10 to stabilize the response before refining overshoot/settling."
        ),
    )


if __name__ == "__main__":
    main()
