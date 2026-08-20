"""Motor position trial 8 from MotorPosition.tex.

PID control: Kp=21, Ki=500, Kd=0.15
"""

from controlclient.examples.ct._motorposition_trial import run_motorposition_trial


def main() -> None:
    run_motorposition_trial(
        kp=21.0,
        ki=500.0,
        kd=0.15,
        description="PID(21,500,0.15) controller",
        why=(
            "With Kd=0.05 as baseline, we raise Kd to 0.15 to improve damping while "
            "preserving zero steady-state error under disturbance."
        ),
        dt=0.001,
    )


if __name__ == "__main__":
    main()
