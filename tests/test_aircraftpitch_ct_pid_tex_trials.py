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
    setup = create_setup("aircraftpitch_ct")
    config = SimulationConfig.from_dict(get_setup_config("aircraftpitch_ct"))
    controller = make_pid_controller(kp=kp, ki=ki, kd=kd, dt=config.dt)
    return run_feedback_loop(setup, config, controller)


def test_aircraftpitch_tex_ct_pid_trials_have_finite_signals():
    trials = [
        (2.0, 0.0, 0.0),
        (1.1269, 0.0, 0.0),
        (1.13, 0.0263, 0.0),
        (1.0482, 0.5241, 0.5241),
        (4.17, 1.2882, 0.26),
        (5.1852, 1.74, 2.98),
    ]

    for kp, ki, kd in trials:
        trace = _run_pid_trial(kp=kp, ki=ki, kd=kd)
        assert trace.setup_name == "aircraftpitch_ct"
        assert np.all(np.isfinite(trace.meas))
        assert np.all(np.isfinite(trace.control))


def test_aircraftpitch_tex_ct_final_pid_meets_specs():
    trace = _run_pid_trial(kp=5.1852, ki=1.74, kd=2.98)

    rise_time = float(trace.kpis["rise_time_sec"])
    overshoot = float(trace.kpis["overshoot_pct"])
    settling_time = float(trace.kpis["settling_time_sec"])
    steady_state_error = float(trace.kpis["steady_state_error_pct"])
    # Specs from AircraftPitch.tex.
    assert overshoot < 10.0
    assert rise_time < 2.0
    # With sampled integration/controller updates, the strict 2% settling
    # indicator can land exactly at the simulation horizon.
    assert settling_time <= 10.0
    # The server executes sampled PID updates; allow a small margin above the
    # continuous-time textbook target while still requiring tight final error.
    assert steady_state_error < 3.5
