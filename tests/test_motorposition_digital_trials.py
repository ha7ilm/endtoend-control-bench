from controlclient.examples.dt._digital_tf import DiscreteTransferController
from controlserver.config import get_setup_config
from controlserver.session import run_feedback_loop
from controlserver.setups import create_setup
from controlserver.setups.base import SimulationConfig


def _run_controller(controller: DiscreteTransferController):
    setup = create_setup("motorposition_dt")
    config = SimulationConfig.from_dict(get_setup_config("motorposition_dt"))

    def controller_step(controller_input: dict):
        error = controller_input["ref"] - controller_input["meas"]
        return {
            "type": "controller_output",
            "control": controller.step(error),
        }

    return run_feedback_loop(setup, config, controller_step), config


def test_final_root_locus_compensator_meets_digital_specs():
    final_controller = DiscreteTransferController.from_zpk(
        zeros_z=[0.95, 0.8, 0.8],
        poles_z=[1.0, -0.98, 0.6],
        gain=800.0,
        control_limit=5e4,
    )
    trace, _config = _run_controller(final_controller)

    assert bool(trace.kpis["settled_within_horizon"])
    assert float(trace.kpis["overshoot_pct"]) < 16.0
    assert float(trace.kpis["settling_time_sec"]) < 0.04


def test_final_compensator_reduces_ss_error_vs_uncompensated():
    uncomp_trace, _ = _run_controller(DiscreteTransferController([1.0], [1.0], control_limit=5e4))
    final_trace, _ = _run_controller(
        DiscreteTransferController.from_zpk(
            zeros_z=[0.95, 0.8, 0.8],
            poles_z=[1.0, -0.98, 0.6],
            gain=800.0,
            control_limit=5e4,
        )
    )

    assert float(final_trace.kpis["steady_state_error_pct"]) < float(
        uncomp_trace.kpis["steady_state_error_pct"]
    )
