"""BallAndBeam digital trial 1: open-loop plant step response."""

import argparse

from controlclient.machine import MachineClient


TS = 0.02


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--setup",
        default="ballandbeam_dt",
        help="Setup variant name to target (default: %(default)s).",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    with MachineClient(
        setup=args.setup,
        description=f"BallAndBeam digital open-loop plant step (Ts={TS:.2f}s)",
        why=(
            "Open-loop plant step from ballandbeam_digital.m: apply the reference "
            "directly as the gear-angle command before closing the loop."
        ),
    ) as machine:
        while True:
            ctl_input = machine.read()
            if ctl_input["done"]:
                print(ctl_input["kpis"])
                break

            # MATLAB trial 1 uses step(0.25 * ball_d, 5): fixed input to plant.
            machine.write({"control": ctl_input["ref"]})


if __name__ == "__main__":
    main()
