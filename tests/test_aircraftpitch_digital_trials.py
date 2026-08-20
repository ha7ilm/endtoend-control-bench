import numpy as np

from controlclient.examples.dt._aircraftpitch_digital_trial import (
    AircraftPitchDigitalLqrController,
)
from controlserver.config import get_setup_config
from controlserver.session import run_feedback_loop
from controlserver.setups import create_setup
from controlserver.setups.base import SimulationConfig


def _run_controller(controller: AircraftPitchDigitalLqrController):
    setup = create_setup("aircraftpitch_dt")
    config = SimulationConfig.from_dict(get_setup_config("aircraftpitch_dt"))

    def controller_step(controller_input: dict):
        control = controller.step(
            ref=controller_input["ref"],
            meas=controller_input["meas"],
        )
        return {
            "type": "controller_output",
            "control": control,
        }

    return run_feedback_loop(setup, config, controller_step)


def test_aircraftpitch_digital_baseline_runs_with_finite_outputs():
    trace = _run_controller(
        AircraftPitchDigitalLqrController(
            dt=0.01,
            p=50.0,
            r=1.0,
        )
    )

    assert trace.setup_name == "aircraftpitch_dt"
    assert np.all(np.isfinite(trace.meas))
    assert np.all(np.isfinite(trace.control))


def test_aircraftpitch_digital_baseline_responds_to_step_reference():
    trace = _run_controller(
        AircraftPitchDigitalLqrController(
            dt=0.01,
            p=50.0,
            r=1.0,
        )
    )

    # Baseline DLQR should move to a non-zero steady value without Nbar.
    assert float(trace.meas[-1]) > 0.0
    assert float(np.max(trace.meas)) > 0.0
    assert float(trace.meas[-1]) < 0.2


def test_aircraftpitch_precompensator_reduces_steady_state_error():
    baseline_trace = _run_controller(
        AircraftPitchDigitalLqrController(
            dt=0.01,
            p=50.0,
            r=1.0,
        )
    )
    precomp_trace = _run_controller(
        AircraftPitchDigitalLqrController(
            dt=0.01,
            p=50.0,
            r=1.0,
            nbar=6.95,
        )
    )

    assert float(precomp_trace.kpis["steady_state_error_pct"]) < float(
        baseline_trace.kpis["steady_state_error_pct"]
    )
