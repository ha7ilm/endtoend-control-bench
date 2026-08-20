"""Suspension digital trial 1: open-loop baseline (zero control force)."""

from controlclient.machine import MachineClient


def main() -> None:
    with MachineClient(
        setup="suspension_dt",
        description="Suspension digital baseline u=0",
        why=(
            "Baseline disturbance response before applying the digital state-space controller "
            "described in suspension_digital.m."
        ),
    ) as machine:
        while True:
            ctl_input = machine.read()
            if ctl_input["done"]:
                print(ctl_input["kpis"])
                break

            machine.write({"control": 0.0})


if __name__ == "__main__":
    main()
