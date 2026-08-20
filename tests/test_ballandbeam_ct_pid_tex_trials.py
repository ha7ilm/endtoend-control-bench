import numpy as np

from controlserver.config import get_setup_config
from controlserver.session import run_feedback_loop
from controlserver.setups import create_setup
from controlserver.setups.base import SimulationConfig


def make_pid_controller(kp: float, ki: float, kd: float, dt: float):
    integral_error = 0.0
    previous_error = 0.0
    first_sample = True

    def controller(controller_input: dict):
        nonlocal integral_error, previous_error, first_sample

        error = controller_input["ref"] - controller_input["meas"]
        derivative = 0.0 if first_sample else (error - previous_error) / dt
        first_sample = False

        control = kp * error + ki * integral_error + kd * derivative

        integral_error += error * dt
        previous_error = error

        return {
            "type": "controller_output",
            "control": control,
        }

    return controller


def _run_pid_trial(kp: float, ki: float, kd: float):
    setup = create_setup("ballandbeam_ct")
    config = SimulationConfig.from_dict(get_setup_config("ballandbeam_ct"))
    controller = make_pid_controller(kp=kp, ki=ki, kd=kd, dt=config.dt)
    return run_feedback_loop(setup, config, controller)


def test_ballandbeam_tex_ct_pid_trials_have_finite_signals():
    trials = [
        (1.0, 0.0, 0.0),
        (10.0, 0.0, 10.0),
        (10.0, 0.0, 20.0),
        (15.0, 0.0, 40.0),
    ]

    for kp, ki, kd in trials:
        trace = _run_pid_trial(kp=kp, ki=ki, kd=kd)
        assert trace.setup_name == "ballandbeam_ct"
        assert np.all(np.isfinite(trace.meas))
        assert np.all(np.isfinite(trace.control))


def test_ballandbeam_tex_ct_pd_trials_improve_baseline_characteristics():
    p_only = _run_pid_trial(kp=1.0, ki=0.0, kd=0.0)
    pd_10_10 = _run_pid_trial(kp=10.0, ki=0.0, kd=10.0)
    pd_10_20 = _run_pid_trial(kp=10.0, ki=0.0, kd=20.0)

    assert float(pd_10_10.kpis["steady_state_error_pct"]) < float(
        p_only.kpis["steady_state_error_pct"]
    )
    assert float(pd_10_20.kpis["overshoot_pct"]) <= float(pd_10_10.kpis["overshoot_pct"])
