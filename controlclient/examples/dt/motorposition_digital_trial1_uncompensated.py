"""MotorPosition digital trial 1: uncompensated baseline (C(z)=1)."""

from controlclient.examples.dt._digital_tf import DiscreteTransferController
from controlclient.examples.dt._motorposition_digital_trial import run_motorposition_digital_trial


def main() -> None:
    controller = DiscreteTransferController([1.0], [1.0], control_limit=5e4)
    run_motorposition_digital_trial(
        controller=controller,
        description="MotorPosition digital baseline C(z)=1",
        why=(
            "Baseline from motorposition_digital.m prior to root-locus compensator design."
        ),
    )


if __name__ == "__main__":
    main()
