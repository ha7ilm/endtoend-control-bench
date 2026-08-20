"""Aircraft pitch digital trial 1: baseline DLQR (p=50, R=1)."""

from controlclient.examples.dt._aircraftpitch_digital_trial import (
    AircraftPitchDigitalLqrController,
    run_aircraftpitch_digital_trial,
)


def main() -> None:
    controller = AircraftPitchDigitalLqrController(
        dt=0.01,
        p=50.0,
        r=1.0,
    )
    run_aircraftpitch_digital_trial(
        controller=controller,
        description="AircraftPitch digital DLQR baseline (p=50, R=1)",
        why=(
            "Baseline digital LQR from aircraftpitch_digital.m before "
            "precompensator scaling."
        ),
    )


if __name__ == "__main__":
    main()
