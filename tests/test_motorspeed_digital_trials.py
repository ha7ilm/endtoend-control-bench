import numpy as np

from controlclient.examples.dt._digital_tf import DiscreteTransferController, pid_tustin_coefficients
from controlserver.config import get_setup_config
from controlserver.session import run_feedback_loop
from controlserver.setups import create_setup
from controlserver.setups.base import SimulationConfig


def _run_controller(
    controller: DiscreteTransferController,
    setup_name: str = "motorspeed_dt",
):
    setup = create_setup(setup_name)
    config = SimulationConfig.from_dict(get_setup_config(setup_name))

    def controller_step(controller_input: dict):
        error = controller_input["ref"] - controller_input["meas"]
        return {
            "type": "controller_output",
            "control": controller.step(error),
        }

    return run_feedback_loop(setup, config, controller_step), config


def test_modified_digital_pid_meets_motorspeed_specs():
    b_pid_q, a_pid_q = pid_tustin_coefficients(kp=100.0, ki=200.0, kd=10.0, dt=0.05)
    b_q = 0.8 * np.concatenate((np.array([0.0], dtype=float), b_pid_q))
    a_q = np.convolve(a_pid_q, np.array([1.0, 0.82], dtype=float))
    trace, _config = _run_controller(DiscreteTransferController(b_q, a_q, control_limit=1e6))

    assert bool(trace.kpis["settled_within_horizon"])
    assert float(trace.kpis["overshoot_pct"]) < 5.0
    assert float(trace.kpis["steady_state_error_pct"]) < 1.0


def test_modified_controller_improves_on_raw_tustin_pid():
    b_pid_q, a_pid_q = pid_tustin_coefficients(kp=100.0, ki=200.0, kd=10.0, dt=0.05)
    raw_trace, _ = _run_controller(DiscreteTransferController(b_pid_q, a_pid_q, control_limit=2e6))

    b_mod_q = 0.8 * np.concatenate((np.array([0.0], dtype=float), b_pid_q))
    a_mod_q = np.convolve(a_pid_q, np.array([1.0, 0.82], dtype=float))
    mod_trace, _ = _run_controller(DiscreteTransferController(b_mod_q, a_mod_q, control_limit=1e6))

    assert float(mod_trace.kpis["steady_state_error_pct"]) < float(
        raw_trace.kpis["steady_state_error_pct"]
    )


def test_gpt_maxonre30_pi_meets_motorspeed_specs():
    setup_name = "motorspeed_dt_lim_maxonre30"
    dt = float(get_setup_config(setup_name)["dt"])
    b_q, a_q = pid_tustin_coefficients(kp=1.5, ki=5.0, kd=0.0, dt=dt)
    trace, _ = _run_controller(
        DiscreteTransferController(b_q, a_q, control_limit=36.0),
        setup_name=setup_name,
    )

    assert bool(trace.kpis["settled_within_horizon"])
    assert float(trace.kpis["settling_time_sec"]) < 2.0
    assert float(trace.kpis["overshoot_pct"]) < 5.0
    assert float(trace.kpis["steady_state_error_pct"]) < 1.0
