"""Cruise control trial 4 from CruiseControl.tex.

PI control: Kp=800, Ki=40
"""

from controlclient.examples.ct._cruisecontrol_trial import run_cruisecontrol_trial


def main() -> None:
    run_cruisecontrol_trial(
        kp=800.0,
        ki=40.0,
        kd=0.0,
        description="PI(800,40) controller",
        why=(
            "After tuning PI gains, CruiseControl.tex presents Kp=800 and Ki=40 "
            "as a satisfactory closed-loop step response."
        ),
        dt=0.1,
    )


if __name__ == "__main__":
    main()
