"""Cruise control trial 1 from CruiseControl.tex.

Proportional control: Kp=100
"""

from controlclient.examples.ct._cruisecontrol_trial import run_cruisecontrol_trial


def main() -> None:
    run_cruisecontrol_trial(
        kp=100.0,
        ki=0.0,
        kd=0.0,
        description="P(100) controller",
        why=(
            "This is the proportional baseline from CruiseControl.tex used to assess "
            "rise time and steady-state error before increasing gains."
        ),
        dt=0.1,
    )


if __name__ == "__main__":
    main()
