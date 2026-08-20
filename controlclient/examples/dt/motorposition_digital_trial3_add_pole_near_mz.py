"""MotorPosition digital trial 3: add pole near z=-0.98."""

from controlclient.examples.dt._digital_tf import DiscreteTransferController
from controlclient.examples.dt._motorposition_digital_trial import run_motorposition_digital_trial


def main() -> None:
    controller = DiscreteTransferController.from_zpk(
        zeros_z=[0.95],
        poles_z=[1.0, -0.98],
        gain=1.0,
        control_limit=5e4,
    )
    run_motorposition_digital_trial(
        controller=controller,
        description="MotorPosition digital add pole near -0.98",
        why=(
            "Intermediate root-locus step from motorposition_digital.m: add a pole near "
            "the plant zero around z=-0.98."
        ),
    )


if __name__ == "__main__":
    main()
