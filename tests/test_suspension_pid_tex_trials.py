import numpy as np
import pytest

from controlserver.config import get_setup_config
from controlserver.session import run_feedback_loop
from controlserver.setups import create_setup
from controlserver.setups.base import SimulationConfig


def _clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


def make_suspension_pid_controller(
    kp: float,
    ki: float,
    kd: float,
    dt: float,
    *,
    derivative_alpha: float = 0.95,
    integral_limit: float = 1.0,
    control_limit: float = 30000.0,
):
    integral_error = 0.0
    previous_error = 0.0
    derivative_filtered = 0.0
    first_sample = True

    def controller(controller_input: dict):
        nonlocal integral_error, previous_error, derivative_filtered, first_sample

        error = controller_input["ref"] - controller_input["meas"]
        raw_derivative = 0.0 if first_sample else (error - previous_error) / dt
        first_sample = False

        derivative_filtered = (
            derivative_alpha * derivative_filtered
            + (1.0 - derivative_alpha) * raw_derivative
        )
        integral_error = _clamp(
            integral_error + error * dt,
            -integral_limit,
            integral_limit,
        )

        control = kp * error + ki * integral_error + kd * derivative_filtered
        control = _clamp(control, -control_limit, control_limit)
        previous_error = error

        return {
            "type": "controller_output",
            "control": control,
        }

    return controller


@pytest.mark.parametrize(
    ("kp", "ki", "kd"),
    [
        (832100.0, 624075.0, 208025.0),
        (1664200.0, 1248150.0, 416050.0),
    ],
)
def test_suspension_tex_pid_trials_run_with_finite_outputs(kp: float, ki: float, kd: float):
    setup = create_setup("suspension_ct")
    config = SimulationConfig.from_dict(get_setup_config("suspension_ct"))
    controller = make_suspension_pid_controller(kp=kp, ki=ki, kd=kd, dt=config.dt)

    trace = run_feedback_loop(setup, config, controller)

    assert trace.setup_name == "suspension_ct"
    assert len(trace.time_sec) == len(trace.ref) == len(trace.meas) == len(trace.control)
    assert len(trace.disturbance) == len(trace.time_sec)

    assert np.all(np.isfinite(trace.time_sec))
    assert np.all(np.isfinite(trace.ref))
    assert np.all(np.isfinite(trace.meas))
    assert np.all(np.isfinite(trace.control))
    assert np.all(np.isfinite(trace.disturbance))

    assert np.all(trace.ref == 0.0)

    disturbance_expected = np.zeros_like(trace.disturbance)
    disturbance_expected[config.warmup_samples :] = config.step_ref
    assert np.allclose(trace.disturbance, disturbance_expected)

    kpis = trace.kpis
    for key in (
        "overshoot_pct",
        "rise_time_sec",
        "settling_time_sec",
        "steady_state_error_pct",
        "settled_within_horizon",
        "simulation_horizon_sec",
    ):
        assert key in kpis

    for key in (
        "overshoot_pct",
        "rise_time_sec",
        "settling_time_sec",
        "steady_state_error_pct",
        "simulation_horizon_sec",
    ):
        assert np.isfinite(float(kpis[key]))

    assert float(kpis["overshoot_pct"]) >= 0.0
    assert 0.0 <= float(kpis["settling_time_sec"]) <= config.horizon_sec

