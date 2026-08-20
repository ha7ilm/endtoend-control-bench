import numpy as np

from controlserver.config import get_setup_config
from controlserver.setups import create_setup


def _step_once(setup_name: str, control: float) -> np.ndarray:
    setup = create_setup(setup_name)
    dt = float(get_setup_config(setup_name)["dt"])
    state = setup.initial_state()
    return setup.integrate_one_step(state, control, 0.0, dt)


def test_cruisecontrol_dt_lim_hondajazz_clamps_to_iso_asymmetric_limits():
    limited_hi = _step_once("cruisecontrol_dt_lim_hondajazz", 1e6)
    expected_hi = _step_once("cruisecontrol_dt_lim_hondajazz", 2480.0)
    assert np.allclose(limited_hi, expected_hi, rtol=1e-12, atol=1e-12)

    limited_lo = _step_once("cruisecontrol_dt_lim_hondajazz", -1e6)
    expected_lo = _step_once("cruisecontrol_dt_lim_hondajazz", -4340.0)
    assert np.allclose(limited_lo, expected_lo, rtol=1e-12, atol=1e-12)


def test_existing_cruisecontrol_variants_remain_unclamped():
    for setup_name in ("cruisecontrol_dt", "cruisecontrol_ct"):
        at_2480 = _step_once(setup_name, 2480.0)
        at_5000 = _step_once(setup_name, 5000.0)
        assert float(at_5000[0]) > float(at_2480[0])


def test_cruisecontrol_dt_lim_hondajazz_uses_expected_model_parameters():
    setup = create_setup("cruisecontrol_dt_lim_hondajazz")
    assert float(setup.m) == float(1240.0)
    assert float(setup.b) == float(50.0)
    assert float(setup.traction_force_max_n) == float(2480.0)
    assert float(setup.traction_force_min_n) == float(-4340.0)
