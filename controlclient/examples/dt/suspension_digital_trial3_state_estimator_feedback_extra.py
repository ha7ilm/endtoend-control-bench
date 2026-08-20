"""Suspension digital trial 3: extra observer + LQR variant."""

from controlclient.examples.dt._suspension_digital_trial import run_suspension_digital_trial


def main() -> None:
    run_suspension_digital_trial(
        description="Suspension digital observer + LQR state feedback (extra)",
        why=(
            "Extra comparison controller: observer-based augmented-state LQR design. "
            "Kept to compare against the place()-based suspension_dt digital controller."
        ),
    )


if __name__ == "__main__":
    main()
