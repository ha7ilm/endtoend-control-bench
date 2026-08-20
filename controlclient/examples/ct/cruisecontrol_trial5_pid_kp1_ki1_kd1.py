"""Cruise control trial 5 from CruiseControl.tex.

PID control: Kp=1, Ki=1, Kd=1
"""

from controlclient.examples.ct._cruisecontrol_trial import run_cruisecontrol_trial


def main() -> None:
    run_cruisecontrol_trial(
        kp=1.0,
        ki=1.0,
        kd=1.0,
        description="PID(1,1,1) controller",
        why=(
            "CruiseControl.tex includes this nominal PID initialization before "
            "manual trial-and-error tuning of Kp, Ki, and Kd."
        ),
        dt=0.1,
    )


if __name__ == "__main__":
    main()
