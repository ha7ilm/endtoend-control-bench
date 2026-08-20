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


def test_pi_from_cruisecontrol_tex_trial4_meets_specs():
    setup = create_setup("cruisecontrol_ct")
    config = SimulationConfig.from_dict(get_setup_config("cruisecontrol_ct"))

    # CruiseControl.tex tuned PI gains: Kp=800, Ki=40.
    controller = make_pid_controller(kp=800.0, ki=40.0, kd=0.0, dt=config.dt)

    trace = run_feedback_loop(setup, config, controller)

    assert trace.setup_name == "cruisecontrol_ct"
    assert len(trace.time_sec) == len(trace.ref) == len(trace.meas) == len(trace.control)

    rise_time = float(trace.kpis["rise_time_sec"])
    overshoot = float(trace.kpis["overshoot_pct"])
    steady_state_error = float(trace.kpis["steady_state_error_pct"])
    settled = bool(trace.kpis["settled_within_horizon"])

    # Specs in CruiseControl.tex: rise < 5s, overshoot < 10%, ss error < 2%.
    assert rise_time < 5.0
    assert overshoot < 10.0
    assert steady_state_error < 2.0
    assert settled
