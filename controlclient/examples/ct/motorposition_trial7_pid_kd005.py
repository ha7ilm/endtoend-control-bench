"""Motor position trial 7 from MotorPosition.tex.

PID control: Kp=21, Ki=500, Kd=0.05
"""

from controlclient.examples.ct._motorposition_trial import run_motorposition_trial


def main() -> None:
    run_motorposition_trial(
        kp=21.0,
        ki=500.0,
        kd=0.05,
        description="PID(21,500,0.05) controller",
        why=(
            "After choosing PI(21,500), we add a small derivative term Kd=0.05 to start "
            "reducing overshoot and settling time."
        ),
        dt=0.001,
    )


if __name__ == "__main__":
    main()
