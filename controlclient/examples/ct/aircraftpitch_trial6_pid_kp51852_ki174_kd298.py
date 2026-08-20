"""Aircraft pitch trial 6 from AircraftPitch.tex.

PID control: Kp=5.1852, Ki=1.74, Kd=2.98
"""

from controlclient.examples.ct._aircraftpitch_trial import run_aircraftpitch_trial


def main() -> None:
    run_aircraftpitch_trial(
        kp=5.1852,
        ki=1.74,
        kd=2.98,
        description="AircraftPitch PID(5.1852,1.74,2.98)",
        why=(
            "Final PID gains from AircraftPitch.tex reported to meet overshoot, rise, "
            "settling, and steady-state requirements."
        ),
        dt=0.01,
    )


if __name__ == "__main__":
    main()
