"""MotorPosition digital trial 5: final compensator with loop gain 800."""

from controlclient.examples.dt._digital_tf import DiscreteTransferController
from controlclient.examples.dt._motorposition_digital_trial import run_motorposition_digital_trial


def main() -> None:
    controller = DiscreteTransferController.from_zpk(
        zeros_z=[0.95, 0.8, 0.8],
        poles_z=[1.0, -0.98, 0.6],
        gain=800.0,
        control_limit=5e4,
    )
    run_motorposition_digital_trial(
        controller=controller,
        description="MotorPosition digital final compensator (gain 800)",
        why=(
            "Final controller synthesized from motorposition_digital.m root-locus stages: "
            "C(z)=800*(z-0.95)*(z-0.8)^2/((z-1)*(z+0.98)*(z-0.6))."
        ),
    )


if __name__ == "__main__":
    main()
