"""Aircraft pitch trial 2 from AircraftPitch.tex.

Proportional control: Kp=1.1269
"""

from controlclient.examples.ct._aircraftpitch_trial import run_aircraftpitch_trial


def main() -> None:
    run_aircraftpitch_trial(
        kp=1.1269,
        ki=0.0,
        kd=0.0,
        description="AircraftPitch tuned P(1.1269)",
        why=(
            "Automated tuning P-only update from AircraftPitch.tex; improves rise-time "
            "but still leaves slow settling."
        ),
        dt=0.01,
    )


if __name__ == "__main__":
    main()
