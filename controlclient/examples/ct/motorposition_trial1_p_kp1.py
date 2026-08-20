"""Motor position trial 1 from MotorPosition.tex.

Proportional control: Kp=1
"""

from controlclient.examples.ct._motorposition_trial import run_motorposition_trial


def main() -> None:
    run_motorposition_trial(
        kp=1.0,
        ki=0.0,
        kd=0.0,
        description="P(1) controller",
        why=(
            "This is the proportional baseline from MotorPosition.tex to observe the "
            "step and disturbance responses before increasing gain."
        ),
        dt=0.001,
    )


if __name__ == "__main__":
    main()
