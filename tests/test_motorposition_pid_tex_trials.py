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


def test_pid_from_motorposition_tex_trial8_settles_within_horizon():
    setup = create_setup("motorposition_ct")
    config = SimulationConfig.from_dict(get_setup_config("motorposition_ct"))

    # Final recommended gains from MotorPosition.tex: Kp=21, Ki=500, Kd=0.15.
    controller = make_pid_controller(kp=21.0, ki=500.0, kd=0.15, dt=config.dt)

    trace = run_feedback_loop(setup, config, controller)

    assert trace.setup_name == "motorposition_ct"
    assert len(trace.time_sec) == len(trace.ref) == len(trace.meas) == len(trace.control)

    settled = bool(trace.kpis["settled_within_horizon"])
    overshoot = float(trace.kpis["overshoot_pct"])
    rise_time = float(trace.kpis["rise_time_sec"])
    settling_time = float(trace.kpis["settling_time_sec"])

    assert settled
    assert overshoot < 16.0
    assert rise_time <= config.horizon_sec
    assert settling_time <= config.horizon_sec
