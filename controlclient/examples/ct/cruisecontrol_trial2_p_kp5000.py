"""Cruise control trial 2 from CruiseControl.tex.

Proportional control: Kp=5000
"""

from controlclient.examples.ct._cruisecontrol_trial import run_cruisecontrol_trial


def main() -> None:
    run_cruisecontrol_trial(
        kp=5000.0,
        ki=0.0,
        kd=0.0,
        description="P(5000) controller",
        why=(
            "CruiseControl.tex increases Kp to 5000 to reduce rise time and steady-state "
            "error, then flags the response as unrealistically aggressive."
        ),
        dt=0.1,
    )


if __name__ == "__main__":
    main()
