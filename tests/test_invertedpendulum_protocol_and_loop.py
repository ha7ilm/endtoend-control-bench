import numpy as np

from controlserver.config import get_setup_config
from controlserver.session import run_feedback_loop
from controlserver.setups import create_setup
from controlserver.setups.base import SimulationConfig


def test_invertedpendulum_run_feedback_loop_uses_dict_ref_and_meas():
    setup = create_setup("invertedpendulum_dt")
    config = SimulationConfig.from_dict(get_setup_config("invertedpendulum_dt"))

    first_input: dict | None = None

    def controller_step(controller_input: dict):
        nonlocal first_input
        if first_input is None:
            first_input = controller_input

        ref = controller_input["ref"]
        meas = controller_input["meas"]
        force = 40.0 * (ref["x_cart"] - meas["x_cart"]) - 12.0 * meas["phi_angle"]
        return {
            "type": "controller_output",
            "control": force,
        }

    trace = run_feedback_loop(setup, config, controller_step)

    assert first_input is not None
    assert isinstance(first_input["ref"], dict)
    assert isinstance(first_input["meas"], dict)
    assert set(first_input["ref"]) == {"x_cart", "phi_angle"}
    assert set(first_input["meas"]) == {"x_cart", "phi_angle"}

    assert isinstance(trace.ref, dict)
    assert isinstance(trace.meas, dict)
    assert set(trace.ref) == {"x_cart", "phi_angle"}
    assert set(trace.meas) == {"x_cart", "phi_angle"}

    assert len(trace.ref["x_cart"]) == len(trace.time_sec)
    assert len(trace.ref["phi_angle"]) == len(trace.time_sec)
    assert len(trace.meas["x_cart"]) == len(trace.time_sec)
    assert len(trace.meas["phi_angle"]) == len(trace.time_sec)

    assert np.all(np.isfinite(trace.ref["x_cart"]))
    assert np.all(np.isfinite(trace.ref["phi_angle"]))
    assert np.all(np.isfinite(trace.meas["x_cart"]))
    assert np.all(np.isfinite(trace.meas["phi_angle"]))
    assert np.all(np.isfinite(trace.control))
    assert np.all(np.isfinite(trace.disturbance))

    channels = trace.kpis.get("channels")
    assert isinstance(channels, dict)
    assert set(channels) == {"x_cart", "phi_angle"}
    assert isinstance(channels["x_cart"], dict)
    assert isinstance(channels["phi_angle"], dict)
    assert "max_abs_rad" in channels["phi_angle"]
    assert np.isfinite(float(channels["phi_angle"]["max_abs_rad"]))
