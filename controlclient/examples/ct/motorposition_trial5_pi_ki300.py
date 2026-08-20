"""Motor position trial 5 from MotorPosition.tex.

PI control: Kp=21, Ki=300
"""

from controlclient.examples.ct._motorposition_trial import run_motorposition_trial


def main() -> None:
    run_motorposition_trial(
        kp=21.0,
        ki=300.0,
        kd=0.0,
        description="PI(21,300) controller",
        why=(
            "The Ki=100 PI run removes steady-state disturbance error, and now we increase "
            "Ki to 300 to speed error decay."
        ),
        dt=0.001,
    )


if __name__ == "__main__":
    main()
