"""MotorSpeed digital GPT trial: Maxon RE30-specific PI that meets CTMS step specs."""

import argparse

from controlclient.examples.dt._digital_tf import DiscreteTransferController, pid_tustin_coefficients
from controlclient.examples.dt._motorspeed_digital_trial import run_motorspeed_digital_trial
from controlserver.config import get_setup_config


SETUP_NAME = "motorspeed_dt_lim_maxonre30"
KP = 1.5
KI = 5.0
KD = 0.0
CONTROL_LIMIT_VOLTS = 36.0


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--setup",
        default=SETUP_NAME,
        help=(
            "Setup variant name to target. This controller is tuned only for "
            f"{SETUP_NAME} (default: %(default)s)."
        ),
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    if args.setup != SETUP_NAME:
        raise SystemExit(
            f"{__name__} supports only --setup {SETUP_NAME}; got {args.setup!r}."
        )

    dt = float(get_setup_config(SETUP_NAME)["dt"])
    b_q, a_q = pid_tustin_coefficients(kp=KP, ki=KI, kd=KD, dt=dt)
    controller = DiscreteTransferController(
        b_q,
        a_q,
        control_limit=CONTROL_LIMIT_VOLTS,
    )
    run_motorspeed_digital_trial(
        controller=controller,
        description=(
            "MotorSpeed Maxon RE30 PI tuned for spec compliance "
            f"(Kp={KP}, Ki={KI}, Kd={KD}, Ts={dt})"
        ),
        why=(
            "Variant-specific PI tuning for motorspeed_dt_lim_maxonre30 with 1 ms sampling "
            "and ±36 V actuation to satisfy settling-time, overshoot, and steady-state-error "
            "design specs."
        ),
        setup=SETUP_NAME,
    )


if __name__ == "__main__":
    main()
