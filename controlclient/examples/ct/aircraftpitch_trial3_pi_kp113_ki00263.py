"""Aircraft pitch trial 3 from AircraftPitch.tex.

PI control: Kp=1.13, Ki=0.0263
"""

from controlclient.examples.ct._aircraftpitch_trial import run_aircraftpitch_trial


def main() -> None:
    run_aircraftpitch_trial(
        kp=1.13,
        ki=0.0263,
        kd=0.0,
        description="AircraftPitch PI(1.13,0.0263)",
        why=(
            "PI trial from AircraftPitch.tex after P-only tuning to reduce average "
            "tracking error."
        ),
        dt=0.01,
    )


if __name__ == "__main__":
    main()
