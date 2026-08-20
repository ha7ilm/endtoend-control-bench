import numpy as np
import pytest

from controlclient.examples.dt._suspension_digital_trial import (
    SuspensionEstimatorController,
    SuspensionPlaceEstimatorController,
)
from controlserver.config import get_setup_config
from controlserver.session import run_feedback_loop
from controlserver.setups import create_setup
from controlserver.setups.base import SimulationConfig


@pytest.mark.parametrize(
    "controller_factory",
    [
        SuspensionPlaceEstimatorController,
        SuspensionEstimatorController,
    ],
)
def test_observer_based_suspension_controller_has_finite_signals_and_recovery(controller_factory):
    setup = create_setup("suspension_dt")
    config = SimulationConfig.from_dict(get_setup_config("suspension_dt"))
    controller = controller_factory()

    def controller_step(controller_input: dict):
        control = controller.step(
            ref=controller_input["ref"],
            meas=controller_input["meas"],
        )
        return {
            "type": "controller_output",
            "control": control,
        }

    trace = run_feedback_loop(setup, config, controller_step)

    assert np.all(np.isfinite(trace.meas))
    assert np.all(np.isfinite(trace.control))
    assert np.max(np.abs(trace.control)) < 2.0e5

    peak_abs_meas = float(np.max(np.abs(trace.meas)))
    final_abs_meas = float(np.abs(trace.meas[-1]))
    assert peak_abs_meas > 0.0
    assert final_abs_meas < peak_abs_meas
