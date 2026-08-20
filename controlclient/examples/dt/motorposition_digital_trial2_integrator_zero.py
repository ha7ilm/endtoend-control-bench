"""MotorPosition digital trial 2: add integrator pole at 1 and zero at 0.95."""

from controlclient.examples.dt._digital_tf import DiscreteTransferController
from controlclient.examples.dt._motorposition_digital_trial import run_motorposition_digital_trial


def main() -> None:
    controller = DiscreteTransferController.from_zpk(
        zeros_z=[0.95],
        poles_z=[1.0],
        gain=1.0,
        control_limit=5e4,
    )
    run_motorposition_digital_trial(
        controller=controller,
        description="MotorPosition digital C(z)=(z-0.95)/(z-1)",
        why=(
            "Intermediate compensator stage from motorposition_digital.m after adding "
            "integral action and a zero near z=1."
        ),
    )


if __name__ == "__main__":
    main()
