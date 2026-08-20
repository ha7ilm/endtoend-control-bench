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


def run_with_dt(dt: float):
    setup = create_setup("cruisecontrol_dt")
    cfg = get_setup_config("cruisecontrol_dt")
    base_delay_sec = float(cfg["warmup_samples"]) * float(cfg["dt"])
    cfg["dt"] = dt
    cfg["warmup_samples"] = int(round(base_delay_sec / dt))
    config = SimulationConfig.from_dict(cfg)

    controller = make_proportional_controller(kp=800.0)
    return run_feedback_loop(setup, config, controller), config


def test_sampling_time_converges_below_one_hundred_ms():
    trace_100ms, _ = run_with_dt(0.1)
    trace_50ms, _ = run_with_dt(0.05)
    trace_20ms, _ = run_with_dt(0.02)

    y_20ms_on_100ms = np.interp(trace_100ms.time_sec, trace_20ms.time_sec, trace_20ms.meas)
    y_20ms_on_50ms = np.interp(trace_50ms.time_sec, trace_20ms.time_sec, trace_20ms.meas)

    mae_100ms = float(np.mean(np.abs(trace_100ms.meas - y_20ms_on_100ms)))
    mae_50ms = float(np.mean(np.abs(trace_50ms.meas - y_20ms_on_50ms)))

    assert mae_100ms < 0.08
    assert mae_50ms < 0.01

def test_sampled_feedback_matches_transfer_function_response():
    trace, config = run_with_dt(0.02)

    m = 1000.0
    b = 50.0
    kp = 800.0

    s = tf("s")
    p_cruise = 1 / (m * s + b)
    c = tf([kp], [1])
    sys_cl = feedback(c * p_cruise, 1)

    continuous_time = np.arange(0.0, config.horizon_sec + config.dt, config.dt)
    y_cont, t_cont = step(config.step_ref * sys_cl, continuous_time)

    step_delay = config.warmup_samples * config.dt
    shifted_time = np.clip(trace.time_sec - step_delay, 0.0, None)
    aligned_continuous = np.interp(shifted_time, t_cont, y_cont)

    mae = float(np.mean(np.abs(trace.meas - aligned_continuous)))
    max_err = float(np.max(np.abs(trace.meas - aligned_continuous)))

    assert mae < 0.01
    assert max_err < 0.05
