import numpy as np

from controlclient.examples.dt._invertedpendulum_digital_trial import (
    InvertedPendulumDigitalLqrController,
)
from controlserver.config import get_setup_config
from controlserver.session import run_feedback_loop
from controlserver.setups import create_setup
from controlserver.setups.base import SimulationConfig

CHANNEL_KPI_KEYS = {
    "overshoot_pct",
    "rise_time_sec",
    "settling_time_sec",
    "steady_state_error_pct",
    "settled_within_horizon",
    "simulation_horizon_sec",
}


def _run_controller(
    controller: InvertedPendulumDigitalLqrController,
    *,
    setup_name: str = "invertedpendulum_dt",
):
    setup = create_setup(setup_name)
    config = SimulationConfig.from_dict(get_setup_config(setup_name))

    def controller_step(controller_input: dict):
        control = controller.step(
            ref=controller_input["ref"],
            meas=controller_input["meas"],
        )
        return {
            "type": "controller_output",
            "control": control,
        }

    return run_feedback_loop(setup, config, controller_step), config


def _channel_kpis(trace, channel: str) -> dict[str, float | bool]:
    channels = trace.kpis.get("channels")
    assert isinstance(channels, dict)
    assert channel in channels
    channel_kpis = channels[channel]
    assert isinstance(channel_kpis, dict)
    return channel_kpis


def _assert_common_channel_kpis(channel_kpis: dict[str, float | bool]) -> None:
    assert CHANNEL_KPI_KEYS.issubset(channel_kpis)
    assert np.isfinite(float(channel_kpis["overshoot_pct"]))
    assert np.isfinite(float(channel_kpis["rise_time_sec"]))
    assert np.isfinite(float(channel_kpis["settling_time_sec"]))
    assert np.isfinite(float(channel_kpis["steady_state_error_pct"]))
    assert isinstance(channel_kpis["settled_within_horizon"], bool)
    assert np.isfinite(float(channel_kpis["simulation_horizon_sec"]))


def test_invertedpendulum_digital_baseline_runs_with_dict_signals():
    trace, _ = _run_controller(
        InvertedPendulumDigitalLqrController(
            dt=0.01,
            q_cart=1.0,
            q_phi=1.0,
            r=1.0,
        )
    )

    assert isinstance(trace.ref, dict)
    assert isinstance(trace.meas, dict)
    assert set(trace.ref) == {"x_cart", "phi_angle"}
    assert set(trace.meas) == {"x_cart", "phi_angle"}
    assert np.all(np.isfinite(trace.meas["x_cart"]))
    assert np.all(np.isfinite(trace.meas["phi_angle"]))
    assert np.all(np.isfinite(trace.control))
    assert np.any(np.abs(trace.control) > 1e-8)

    x_kpis = _channel_kpis(trace, "x_cart")
    phi_kpis = _channel_kpis(trace, "phi_angle")
    _assert_common_channel_kpis(x_kpis)
    _assert_common_channel_kpis(phi_kpis)
    assert "max_abs_rad" in phi_kpis
    assert np.isfinite(float(phi_kpis["max_abs_rad"]))
    assert float(phi_kpis["max_abs_rad"]) >= 0.0


def test_invertedpendulum_precompensator_reduces_cart_steady_state_error():
    tuned_no_nbar, _ = _run_controller(
        InvertedPendulumDigitalLqrController(
            dt=0.01,
            q_cart=5000.0,
            q_phi=100.0,
            r=1.0,
        )
    )
    tuned_with_nbar, _ = _run_controller(
        InvertedPendulumDigitalLqrController(
            dt=0.01,
            q_cart=5000.0,
            q_phi=100.0,
            r=1.0,
            nbar=-61.55,
        )
    )

    assert np.any(np.abs(tuned_no_nbar.control) > 1e-8)
    assert float(_channel_kpis(tuned_with_nbar, "x_cart")["steady_state_error_pct"]) < float(
        _channel_kpis(tuned_no_nbar, "x_cart")["steady_state_error_pct"]
    )


def test_invertedpendulum_observer_controller_tracks_and_is_finite():
    observer_trace, _ = _run_controller(
        InvertedPendulumDigitalLqrController(
            dt=0.01,
            q_cart=5000.0,
            q_phi=100.0,
            r=1.0,
            nbar=-61.55,
            use_observer=True,
            observer_poles=(-0.2, -0.21, -0.22, -0.23),
        )
    )

    assert isinstance(observer_trace.meas, dict)
    assert np.all(np.isfinite(observer_trace.meas["x_cart"]))
    assert np.all(np.isfinite(observer_trace.meas["phi_angle"]))
    assert np.all(np.isfinite(observer_trace.control))
    x_kpis = _channel_kpis(observer_trace, "x_cart")
    phi_kpis = _channel_kpis(observer_trace, "phi_angle")
    assert float(x_kpis["steady_state_error_pct"]) < 2.0
    assert float(x_kpis["settling_time_sec"]) < 5.0
    assert np.isfinite(float(phi_kpis["max_abs_rad"]))


def test_invertedpendulum_dt_nl_baseline_is_finite():
    trace, _ = _run_controller(
        InvertedPendulumDigitalLqrController(
            dt=0.01,
            q_cart=1.0,
            q_phi=1.0,
            r=1.0,
        ),
        setup_name="invertedpendulum_dt_nl",
    )

    assert trace.setup_name == "invertedpendulum_dt_nl"
    assert isinstance(trace.meas, dict)
    assert np.all(np.isfinite(trace.meas["x_cart"]))
    assert np.all(np.isfinite(trace.meas["phi_angle"]))
    assert np.all(np.isfinite(trace.control))
    assert np.isfinite(float(_channel_kpis(trace, "phi_angle")["max_abs_rad"]))


def test_invertedpendulum_dt_nl_quanserip02_baseline_is_finite():
    trace, _ = _run_controller(
        InvertedPendulumDigitalLqrController(
            dt=0.01,
            q_cart=1.0,
            q_phi=1.0,
            r=1.0,
        ),
        setup_name="invertedpendulum_dt_nl_quanserip02",
    )

    assert trace.setup_name == "invertedpendulum_dt_nl_quanserip02"
    assert isinstance(trace.meas, dict)
    assert np.all(np.isfinite(trace.meas["x_cart"]))
    assert np.all(np.isfinite(trace.meas["phi_angle"]))
    assert np.all(np.isfinite(trace.control))
    assert np.isfinite(float(_channel_kpis(trace, "phi_angle")["max_abs_rad"]))


def test_invertedpendulum_dt_nl_lim_quanserip02_baseline_is_finite():
    trace, _ = _run_controller(
        InvertedPendulumDigitalLqrController(
            dt=0.01,
            q_cart=1.0,
            q_phi=1.0,
            r=1.0,
        ),
        setup_name="invertedpendulum_dt_nl_lim_quanserip02",
    )

    assert trace.setup_name == "invertedpendulum_dt_nl_lim_quanserip02"
    assert isinstance(trace.meas, dict)
    assert np.all(np.isfinite(trace.meas["x_cart"]))
    assert np.all(np.isfinite(trace.meas["phi_angle"]))
    assert np.all(np.isfinite(trace.control))
    assert np.isfinite(float(_channel_kpis(trace, "phi_angle")["max_abs_rad"]))
