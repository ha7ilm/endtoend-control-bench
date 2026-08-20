"""Motor position trial 4 from MotorPosition.tex.

PI control: Kp=21, Ki=100
"""

from controlclient.examples.ct._motorposition_trial import run_motorposition_trial


def main() -> None:
    run_motorposition_trial(
        kp=21.0,
        ki=100.0,
        kd=0.0,
        description="PI(21,100) controller",
        why=(
            "Proportional control leaves disturbance steady-state error, so we add integral "
            "action with Ki=100 to drive that error to zero."
        ),
        dt=0.001,
    )


if __name__ == "__main__":
    main()
