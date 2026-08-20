"""Suspension digital trial 2: observer + pole-placement (place) state feedback."""

from controlclient.examples.dt._suspension_digital_trial import run_suspension_digital_place_trial


def main() -> None:
    run_suspension_digital_place_trial(
        description="Suspension digital observer + place() state feedback",
        why=(
            "Implements the suspension_digital.m pole-placement workflow with an observer, "
            "using the same scalar measured output (X1-X2) available in this app."
        ),
    )


if __name__ == "__main__":
    main()
