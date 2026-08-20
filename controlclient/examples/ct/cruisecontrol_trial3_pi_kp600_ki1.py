"""Cruise control trial 3 from CruiseControl.tex.

PI control: Kp=600, Ki=1
"""

from controlclient.examples.ct._cruisecontrol_trial import run_cruisecontrol_trial


def main() -> None:
    run_cruisecontrol_trial(
        kp=600.0,
        ki=1.0,
        kd=0.0,
        description="PI(600,1) controller",
        why=(
            "CruiseControl.tex next adds integral action with Kp=600 and Ki=1 "
            "to remove steady-state error while moderating proportional aggressiveness."
        ),
        dt=0.1,
    )


if __name__ == "__main__":
    main()
