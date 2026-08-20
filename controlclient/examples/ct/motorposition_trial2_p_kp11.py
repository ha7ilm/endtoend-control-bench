"""Motor position trial 2 from MotorPosition.tex.

Proportional control: Kp=11
"""

from controlclient.examples.ct._motorposition_trial import run_motorposition_trial


def main() -> None:
    run_motorposition_trial(
        kp=11.0,
        ki=0.0,
        kd=0.0,
        description="P(11) controller",
        why=(
            "After the Kp=1 baseline, we raise Kp to 11 to reduce disturbance-induced "
            "steady-state error and compare transient behavior."
        ),
        dt=0.001,
    )


if __name__ == "__main__":
    main()
