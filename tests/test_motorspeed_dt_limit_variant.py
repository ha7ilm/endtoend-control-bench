import numpy as np

from controlserver.config import get_setup_config
from controlserver.setups import create_setup


def _step_once(setup_name: str, control: float) -> np.ndarray:
    setup = create_setup(setup_name)
    dt = float(get_setup_config(setup_name)["dt"])
    state = setup.initial_state()
    return setup.integrate_one_step(state, control, 0.0, dt)


def test_motorspeed_dt_lim_clamps_to_pm_24_volts():
    limited_hi = _step_once("motorspeed_dt_lim", 1e6)
    expected_hi = _step_once("motorspeed_dt", 24.0)
    assert np.allclose(limited_hi, expected_hi, rtol=1e-12, atol=1e-12)

    limited_lo = _step_once("motorspeed_dt_lim", -1e6)
    expected_lo = _step_once("motorspeed_dt", -24.0)
    assert np.allclose(limited_lo, expected_lo, rtol=1e-12, atol=1e-12)


def test_existing_motorspeed_variants_remain_unclamped():
    for setup_name in ("motorspeed_dt", "motorspeed_ct"):
        at_24 = _step_once(setup_name, 24.0)
        at_25 = _step_once(setup_name, 25.0)
        assert float(at_25[1]) > float(at_24[1])


def test_motorspeed_dt_lim_maxonre30_clamps_to_pm_36_volts():
    limited_hi = _step_once("motorspeed_dt_lim_maxonre30", 1e6)
    expected_hi = _step_once("motorspeed_dt_lim_maxonre30", 36.0)
    assert np.allclose(limited_hi, expected_hi, rtol=1e-12, atol=1e-12)

    limited_lo = _step_once("motorspeed_dt_lim_maxonre30", -1e6)
    expected_lo = _step_once("motorspeed_dt_lim_maxonre30", -36.0)
    assert np.allclose(limited_lo, expected_lo, rtol=1e-12, atol=1e-12)


def test_motorspeed_dt_lim_maxonre30_uses_expected_model_parameters():
    setup = create_setup("motorspeed_dt_lim_maxonre30")
    assert float(setup.J) == float(8.331e-5)
    assert float(setup.b) == float(4.6899385838143515e-6)
    assert float(setup.K) == float(0.0398)
    assert float(setup.R) == float(1.43)
    assert float(setup.L) == float(0.281e-3)
    assert float(setup.actuator_voltage_limit_volts) == float(36.0)
