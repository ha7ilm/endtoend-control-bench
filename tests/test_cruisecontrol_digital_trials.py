from controlclient.examples.dt._digital_tf import DiscreteTransferController
from controlserver.config import get_setup_config
from controlserver.session import run_feedback_loop
from controlserver.setups import create_setup
from controlserver.setups.base import SimulationConfig


def _run_controller(controller: DiscreteTransferController):
    setup = create_setup("cruisecontrol_dt")
    config = SimulationConfig.from_dict(get_setup_config("cruisecontrol_dt"))

    def controller_step(controller_input: dict):
        error = controller_input["ref"] - controller_input["meas"]
        return {
            "type": "controller_output",
            "control": controller.step(error),
        }

    return run_feedback_loop(setup, config, controller_step), config


def test_lag_compensator_reduces_steady_state_error_vs_gain_only():
    gain_only_trace, _ = _run_controller(DiscreteTransferController([451.1104], [1.0]))
    lag_trace, _ = _run_controller(
        DiscreteTransferController.from_zpk(
            zeros_z=[0.999],
            poles_z=[0.9998],
            gain=2.4454e3 * 0.2,
        )
    )

    assert float(lag_trace.kpis["steady_state_error_pct"]) < 3.0
    assert float(gain_only_trace.kpis["steady_state_error_pct"]) > float(
        lag_trace.kpis["steady_state_error_pct"]
    )
