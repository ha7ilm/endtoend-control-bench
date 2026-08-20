"""Aircraft pitch trial 1 from AircraftPitch.tex.

Proportional control: Kp=2
"""

from controlclient.examples.ct._aircraftpitch_trial import run_aircraftpitch_trial


def main() -> None:
    run_aircraftpitch_trial(
        kp=2.0,
        ki=0.0,
        kd=0.0,
        description="AircraftPitch P(2) baseline",
        why=(
            "Baseline proportional trial from AircraftPitch.tex before automated "
            "PID tuning refinements."
        ),
        dt=0.01,
    )


if __name__ == "__main__":
    main()
