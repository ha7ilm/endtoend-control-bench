"""Motor position trial 3 from MotorPosition.tex.

Proportional control: Kp=21
"""

from controlclient.examples.ct._motorposition_trial import run_motorposition_trial


def main() -> None:
    run_motorposition_trial(
        kp=21.0,
        ki=0.0,
        kd=0.0,
        description="P(21) controller",
        why=(
            "We continue the proportional sweep at Kp=21 to further shrink disturbance error "
            "and establish the limit of proportional-only control."
        ),
        dt=0.001,
    )


if __name__ == "__main__":
    main()
