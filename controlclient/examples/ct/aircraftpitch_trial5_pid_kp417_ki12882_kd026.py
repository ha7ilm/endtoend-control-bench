"""Aircraft pitch trial 5 from AircraftPitch.tex.

PID control: Kp=4.17, Ki=1.2882, Kd=0.26
"""

from controlclient.examples.ct._aircraftpitch_trial import run_aircraftpitch_trial


def main() -> None:
    run_aircraftpitch_trial(
        kp=4.17,
        ki=1.2882,
        kd=0.26,
        description="AircraftPitch PID(4.17,1.2882,0.26)",
        why=(
            "Second tuned PID trial from AircraftPitch.tex using faster transient "
            "settings with more robustness."
        ),
        dt=0.01,
    )


if __name__ == "__main__":
    main()
