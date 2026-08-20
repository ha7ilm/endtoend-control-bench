"""Aircraft pitch digital trial 2: DLQR with precompensation Nbar=6.95."""

from controlclient.examples.dt._aircraftpitch_digital_trial import (
    AircraftPitchDigitalLqrController,
    run_aircraftpitch_digital_trial,
)


def main() -> None:
    controller = AircraftPitchDigitalLqrController(
        dt=0.01,
        p=50.0,
        r=1.0,
        nbar=6.95,
    )
    run_aircraftpitch_digital_trial(
        controller=controller,
        description="AircraftPitch digital DLQR with precompensation Nbar=6.95",
        why=(
            "Digital aircraft pitch trial from aircraftpitch_digital.m that adds "
            "Nbar=6.95 to remove steady-state error."
        ),
    )


if __name__ == "__main__":
    main()
