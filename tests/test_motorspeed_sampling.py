import numpy as np
from control.matlab import feedback, step, tf

from controlserver.config import get_setup_config
from controlserver.session import run_feedback_loop
from controlserver.setups import create_setup
from controlserver.setups.base import SimulationConfig


def make_proportional_controller(kp: float):
    def controller(controller_input: dict):
        error = controller_input["ref"] - controller_input["meas"]
        return {
            "type": "controller_output",
            "control": kp * error,
        }

    return controller


def run_with_dt(dt: float | None = None):
    setup = create_setup("motorspeed_dt")
    cfg = get_setup_config("motorspeed_dt")
    if dt is not None:
        cfg["dt"] = dt
    config = SimulationConfig.from_dict(cfg)

    controller = make_proportional_controller(kp=100.0)
    return run_feedback_loop(setup, config, controller), config


def test_sampling_time_converges_below_ten_ms():
    trace_10ms, _ = run_with_dt(0.01)
    trace_5ms, _ = run_with_dt(0.005)
    trace_2ms, _ = run_with_dt(0.002)

    y_2ms_on_10ms = np.interp(trace_10ms.time_sec, trace_2ms.time_sec, trace_2ms.meas)
    y_2ms_on_5ms = np.interp(trace_5ms.time_sec, trace_2ms.time_sec, trace_2ms.meas)

    mae_10ms = float(np.mean(np.abs(trace_10ms.meas - y_2ms_on_10ms)))
    mae_5ms = float(np.mean(np.abs(trace_5ms.meas - y_2ms_on_5ms)))

    assert mae_10ms < 0.03
    assert mae_5ms < 0.01

def test_sampled_feedback_matches_transfer_function_response():
    trace, config = run_with_dt(0.01)

    J = 0.01
    b = 0.1
    K = 0.01
    R = 1.0
    L = 0.5

    kp = 100.0

    s = tf("s")
    p_motor = K / ((J * s + b) * (L * s + R) + K**2)
    c = tf([kp], [1])
    sys_cl = feedback(c * p_motor, 1)

    continuous_time = np.arange(0.0, config.horizon_sec + config.dt, config.dt)
    y_cont, t_cont = step(sys_cl, continuous_time)

    step_delay = config.warmup_samples * config.dt
    shifted_time = np.clip(trace.time_sec - step_delay, 0.0, None)
    aligned_continuous = np.interp(shifted_time, t_cont, y_cont)

    mae = float(np.mean(np.abs(trace.meas - aligned_continuous)))
    max_err = float(np.max(np.abs(trace.meas - aligned_continuous)))

    assert mae < 0.005
    assert max_err < 0.05
