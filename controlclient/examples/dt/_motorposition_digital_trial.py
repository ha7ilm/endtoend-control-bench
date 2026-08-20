"""Shared helpers for MotorPosition digital controller examples."""

from __future__ import annotations

from controlclient.examples.dt._digital_tf import DiscreteTransferController
from controlclient.machine import MachineClient


def run_motorposition_digital_trial(
    controller: DiscreteTransferController,
    description: str,
    why: str,
) -> None:
    with MachineClient(setup="motorposition_dt", description=description, why=why) as machine:
        while True:
            ctl_input = machine.read()
            if ctl_input["done"]:
                print(ctl_input["kpis"])
                break

            error = ctl_input["ref"] - ctl_input["meas"]
            machine.write({"control": controller.step(error)})
