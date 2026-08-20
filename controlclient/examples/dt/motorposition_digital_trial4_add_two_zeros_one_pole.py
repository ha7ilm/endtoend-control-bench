"""MotorPosition digital trial 4: add two zeros at 0.8 and one pole at 0.6."""

from controlclient.examples.dt._digital_tf import DiscreteTransferController
from controlclient.examples.dt._motorposition_digital_trial import run_motorposition_digital_trial


def main() -> None:
    controller = DiscreteTransferController.from_zpk(
        zeros_z=[0.95, 0.8, 0.8],
        poles_z=[1.0, -0.98, 0.6],
        gain=1.0,
        control_limit=5e4,
    )
    run_motorposition_digital_trial(
        controller=controller,
        description="MotorPosition digital staged compensator before loop gain",
        why=(
            "Intermediate compensator from motorposition_digital.m after adding two zeros "
            "at z=0.8 and one pole at z=0.6."
        ),
    )


if __name__ == "__main__":
    main()
