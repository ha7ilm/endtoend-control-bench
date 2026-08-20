"""Motor position trial 9 from MotorPosition.tex.

PID control: Kp=21, Ki=500, Kd=0.25
"""

from controlclient.examples.ct._motorposition_trial import run_motorposition_trial


def main() -> None:
    run_motorposition_trial(
        kp=21.0,
        ki=500.0,
        kd=0.25,
        description="PID(21,500,0.25) controller",
        why=(
            "We test a larger derivative gain Kd=0.25 to compare against Kd=0.15 and "
            "confirm whether extra derivative action helps or hurts the transient."
        ),
        dt=0.001,
    )


if __name__ == "__main__":
    main()
