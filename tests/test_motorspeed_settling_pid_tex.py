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


def test_pid_from_motorspeed_tex_settles_within_simulation_horizon():
    setup = create_setup("motorspeed_ct")
    config = SimulationConfig.from_dict(get_setup_config("motorspeed_ct"))

    # PID gains used in MotorSpeed.tex tutorial progression.
    controller = make_pid_controller(kp=100.0, ki=200.0, kd=10.0, dt=config.dt)

    trace = run_feedback_loop(setup, config, controller)

    settled = bool(trace.kpis["settled_within_horizon"])
    rise_time = float(trace.kpis["rise_time_sec"])
    settling_time = float(trace.kpis["settling_time_sec"])

    assert settled, (
        "MotorSpeed PID (Kp=100, Ki=200, Kd=10) did not settle within simulation horizon. "
        f"Computed settling time: {settling_time:.4f}s, horizon: {config.horizon_sec:.4f}s"
    )
    assert rise_time <= config.horizon_sec
    assert settling_time < config.horizon_sec
