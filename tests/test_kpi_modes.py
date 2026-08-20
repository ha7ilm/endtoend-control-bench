import numpy as np
import pytest

from controlserver.setups import create_setup
from controlserver.setups.base import SimulationConfig


def test_step_mode_is_default_for_tracking_setups():
    setup = create_setup("motorspeed_dt")
    assert setup.kpi_mode() == "step"


def test_step_mode_kpis_follow_reference_step_semantics():
    setup = create_setup("motorspeed_dt")
    config = SimulationConfig(
        dt=0.1,
        horizon_sec=0.8,
        warmup_samples=0,
        step_ref=1.0,
    )

    time_sec = np.arange(8, dtype=float) * config.dt
    ref = np.array([0.0, 0.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0], dtype=float)
    meas = np.array([0.0, 0.0, 0.0, 0.6, 1.0, 1.05, 1.0, 1.0], dtype=float)

    kpis = setup.compute_kpis(time_sec=time_sec, ref=ref, meas=meas, config=config)

    assert np.isclose(kpis["overshoot_pct"], 5.0, atol=1e-9)
    assert np.isclose(kpis["settling_time_sec"], 0.4, atol=1e-9)
    assert np.isclose(kpis["steady_state_error_pct"], 0.0, atol=1e-9)
    assert bool(kpis["settled_within_horizon"])
    assert float(kpis["rise_time_sec"]) > 0.0


def test_step_mode_target_band_not_final_sample_band():
    setup = create_setup("motorspeed_dt")
    config = SimulationConfig(
        dt=0.1,
        horizon_sec=1.0,
        warmup_samples=0,
        step_ref=1.0,
    )

    time_sec = np.arange(10, dtype=float) * config.dt
    ref = np.array([0.0, 0.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0], dtype=float)
    meas = np.array([0.0, 0.0, 0.0, 0.25, 0.5, 0.7, 0.83, 0.9, 0.95, 0.97], dtype=float)

    kpis = setup.compute_kpis(time_sec=time_sec, ref=ref, meas=meas, config=config)

    assert np.isclose(kpis["settling_time_sec"], config.horizon_sec, atol=1e-9)
    assert not bool(kpis["settled_within_horizon"])
    assert float(kpis["steady_state_error_pct"]) > 0.0


def test_step_mode_matches_python_control_for_stable_step_trace():
    control = pytest.importorskip("control")

    setup = create_setup("motorspeed_dt")
    config = SimulationConfig(
        dt=0.01,
        horizon_sec=4.0,
        warmup_samples=0,
        step_ref=1.0,
    )

    time_sec = np.arange(int(config.horizon_sec / config.dt), dtype=float) * config.dt
    ref = np.ones_like(time_sec)
    meas = 1.0 - np.exp(-time_sec)

    kpis = setup.compute_kpis(time_sec=time_sec, ref=ref, meas=meas, config=config)
    info = control.step_info(
        meas,
        timepts=time_sec,
        final_output=1.0,
        SettlingTimeThreshold=0.02,
        RiseTimeLimits=(0.1, 0.9),
    )

    assert np.isclose(kpis["rise_time_sec"], float(info["RiseTime"]), atol=2.0 * config.dt)
    assert np.isclose(
        kpis["settling_time_sec"],
        float(info["SettlingTime"]),
        atol=2.0 * config.dt,
    )


def test_disturbance_mode_uses_warmup_event_and_zero_target():
    setup = create_setup("suspension_dt")
    assert setup.kpi_mode() == "disturbance"

    config = SimulationConfig(
        dt=0.05,
        horizon_sec=0.5,
        warmup_samples=2,
        step_ref=0.1,
    )

    time_sec = np.arange(10, dtype=float) * config.dt
    ref = np.zeros(10, dtype=float)
    meas = np.array(
        [0.0, 0.0, 0.006, 0.003, 0.0015, 0.0005, 0.0002, 0.0, 0.0, 0.0],
        dtype=float,
    )

    kpis = setup.compute_kpis(time_sec=time_sec, ref=ref, meas=meas, config=config)

    assert np.isclose(kpis["overshoot_pct"], 6.0, atol=1e-9)
    assert np.isclose(kpis["settling_time_sec"], 0.1, atol=1e-9)
    assert np.isclose(kpis["steady_state_error_pct"], 0.0, atol=1e-9)
    assert np.isclose(kpis["rise_time_sec"], 0.0, atol=1e-9)
    assert bool(kpis["settled_within_horizon"])


def test_suspension_disturbance_starts_after_warmup_samples():
    setup = create_setup("suspension_dt")
    config = SimulationConfig(
        dt=0.05,
        horizon_sec=5.0,
        warmup_samples=2,
        step_ref=0.1,
    )

    disturbance = [setup.disturbance_for_step(i, config) for i in range(7)]
    assert disturbance == [0.0, 0.0, 0.1, 0.1, 0.1, 0.1, 0.1]
