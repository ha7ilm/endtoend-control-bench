import numpy as np

from controlserver.config import get_setup_config
from controlserver.session import run_feedback_loop
from controlserver.setups import create_setup
from controlserver.setups.base import SimulationConfig


def _clamp(value: float, limit: float) -> float:
    return float(np.clip(value, -abs(limit), abs(limit)))


def make_invertedpendulum_pid_controller(
    kp: float,
    ki: float,
    kd: float,
    dt: float,
    *,
    control_limit: float = 10000.0,
):
    integral_error = 0.0
    previous_error = 0.0
    first_sample = True

    def controller(controller_input: dict):
        nonlocal integral_error, previous_error, first_sample

        ref = controller_input["ref"]
        meas = controller_input["meas"]
        error = float(ref["phi_angle"]) - float(meas["phi_angle"])
        derivative = 0.0 if first_sample else (error - previous_error) / dt
        first_sample = False

        control = kp * error + ki * integral_error + kd * derivative
        control = _clamp(control, control_limit)

        integral_error += error * dt
        previous_error = error
        return {
            "type": "controller_output",
            "control": control,
        }

    return controller


def _run_pid_trial(kp: float, ki: float, kd: float):
    setup = create_setup("invertedpendulum_ct")
    setup.initial_state = lambda: np.array([0.0, 0.0, 0.1, 0.0], dtype=float)  # type: ignore[method-assign]
    config = SimulationConfig.from_dict(get_setup_config("invertedpendulum_ct"))
    controller = make_invertedpendulum_pid_controller(kp=kp, ki=ki, kd=kd, dt=config.dt)
    return run_feedback_loop(setup, config, controller), config


def test_invertedpendulum_tex_ct_pid_trials_have_finite_signals():
    trials = [
        (1.0, 1.0, 1.0),
        (100.0, 1.0, 1.0),
        (100.0, 1.0, 20.0),
    ]

    for kp, ki, kd in trials:
        trace, _config = _run_pid_trial(kp=kp, ki=ki, kd=kd)
        assert isinstance(trace.meas, dict)
        assert np.all(np.isfinite(trace.meas["x_cart"]))
        assert np.all(np.isfinite(trace.meas["phi_angle"]))
        assert np.all(np.isfinite(trace.control))


def test_invertedpendulum_tex_ct_trial3_keeps_phi_residual_small():
    trial2, _ = _run_pid_trial(kp=100.0, ki=1.0, kd=1.0)
    trial3, _ = _run_pid_trial(kp=100.0, ki=1.0, kd=20.0)

    assert isinstance(trial2.meas, dict)
    assert isinstance(trial3.meas, dict)
    phi_residual_trial2 = float(np.abs(trial2.meas["phi_angle"][-1]))
    phi_residual_trial3 = float(np.abs(trial3.meas["phi_angle"][-1]))

    assert phi_residual_trial2 < 1e-4
    assert phi_residual_trial3 < 1e-4
    assert phi_residual_trial3 <= phi_residual_trial2 * 10.0
