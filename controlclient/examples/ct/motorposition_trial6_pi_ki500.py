"""Motor position trial 6 from MotorPosition.tex.

PI control: Kp=21, Ki=500
"""

from controlclient.examples.ct._motorposition_trial import run_motorposition_trial


def main() -> None:
    run_motorposition_trial(
        kp=21.0,
        ki=500.0,
        kd=0.0,
        description="PI(21,500) controller",
        why=(
            "We push integral gain to Ki=500 because MotorPosition.tex shows faster "
            "disturbance rejection before adding derivative damping."
        ),
        dt=0.001,
    )


if __name__ == "__main__":
    main()
