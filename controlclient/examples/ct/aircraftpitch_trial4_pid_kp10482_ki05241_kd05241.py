"""Aircraft pitch trial 4 from AircraftPitch.tex.

PID control: Kp=1.0482, Ki=0.5241, Kd=0.5241
"""

from controlclient.examples.ct._aircraftpitch_trial import run_aircraftpitch_trial


def main() -> None:
    run_aircraftpitch_trial(
        kp=1.0482,
        ki=0.5241,
        kd=0.5241,
        description="AircraftPitch PID(1.0482,0.5241,0.5241)",
        why=(
            "First PID trial from AircraftPitch.tex after adding derivative action "
            "to reduce oscillation."
        ),
        dt=0.01,
    )


if __name__ == "__main__":
    main()
